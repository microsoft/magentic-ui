"""
Script Executor - Direct Playwright script execution without LLM.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import WebSocket
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page

from ....tools.playwright.replay_engine import (
    PlaywrightReplayEngine,
    ActionResult,
    ReplayResult,
)
from ....tools.playwright.browser.vnc_docker_playwright_browser import (
    VncDockerPlaywrightBrowser,
)
from ...datamodel import Message, Run, RunStatus
from ...datamodel.types import MessageConfig


class ScriptExecutor:
    """
    Executes Playwright scripts directly without LLM involvement.

    This provides fast script replay by directly executing saved actions
    using the Playwright API.
    """

    def __init__(
        self,
        workspace_root: Path,
        inside_docker: bool = False,
        run_without_docker: bool = False,
    ):
        self.workspace_root = workspace_root
        self.inside_docker = inside_docker
        self.run_without_docker = run_without_docker
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._playwright = None
        self._docker_browser = None
        self._websocket: Optional[WebSocket] = None
        self._is_running = False
        self._should_stop = False

    async def _send_message(self, message: Dict[str, Any]) -> bool:
        """Send message to WebSocket client.

        Returns:
            True if message sent successfully, False if connection lost.
        """
        if self._websocket:
            try:
                await self._websocket.send_json(message)
                return True
            except Exception as e:
                # Connection lost - signal stop
                logger.warning(f"WebSocket send failed (connection lost): {e}")
                self._should_stop = True
                return False
        return False

    async def _start_browser(
        self,
        headless: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> tuple[Browser, Page, Optional[int]]:
        """Start browser instance and return browser, page, and vnc_port."""
        vnc_port = None

        if self.run_without_docker:
            # Use local browser
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await self._browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            self._page = await context.new_page()
        else:
            # Use Docker VNC browser for live view
            bind_dir = self.workspace_root / "script_execution"
            bind_dir.mkdir(parents=True, exist_ok=True)

            self._docker_browser = VncDockerPlaywrightBrowser(
                bind_dir=bind_dir,
                inside_docker=self.inside_docker,
            )
            # Call _start() to initialize the browser (this is the internal method)
            await self._docker_browser._start()

            # Get browser context from the docker browser (already set up by _start)
            context = self._docker_browser.browser_context
            # Set viewport on the context
            self._page = context.pages[0] if context.pages else await context.new_page()
            await self._page.set_viewport_size({"width": viewport_width, "height": viewport_height})
            vnc_port = self._docker_browser._novnc_port

        return self._browser, self._page, vnc_port

    async def _stop_browser(self) -> None:
        """Stop browser instance."""
        try:
            if self._docker_browser:
                # Docker browser handles its own cleanup via _close
                await self._docker_browser._close()
                self._docker_browser = None
            else:
                # Local browser - close manually
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")

    def _create_run(
        self,
        db: Any,
        session_id: int,
        task: str,
    ) -> Optional[int]:
        """Create a Run for tracking script execution."""
        try:
            # Use dict for task to ensure JSON serialization
            run = Run(
                session_id=session_id,
                status=RunStatus.ACTIVE,
                task={"source": "user", "content": task, "message_type": "text"},
            )
            response = db.upsert(run)
            if response.status and response.data:
                run_data = response.data
                if isinstance(run_data, dict):
                    return run_data.get("id")
                return getattr(run_data, "id", None)
        except Exception as e:
            logger.warning(f"Failed to create run: {e}")
        return None

    def _update_run_status(
        self,
        db: Any,
        run_id: int,
        status: RunStatus,
    ) -> None:
        """Update the status of a Run."""
        try:
            # Get existing run
            response = db.get(Run, filters={"id": run_id})
            if response.status and response.data:
                run_data = response.data[0]
                # Preserve all existing fields including timestamps
                created_at = run_data.get("created_at") if isinstance(run_data, dict) else getattr(run_data, "created_at", None)
                user_id = run_data.get("user_id") if isinstance(run_data, dict) else getattr(run_data, "user_id", None)
                # Create updated run object preserving original fields
                run = Run(
                    id=run_id,
                    session_id=run_data.get("session_id") if isinstance(run_data, dict) else run_data.session_id,
                    status=status,
                    task=run_data.get("task") if isinstance(run_data, dict) else run_data.task,
                    created_at=created_at,
                    user_id=user_id,
                )
                db.upsert(run)
        except Exception as e:
            logger.warning(f"Failed to update run status: {e}")

    def _save_message_to_session(
        self,
        db: Any,
        session_id: int,
        user_id: str,
        source: str,
        content: str,
        run_id: Optional[int] = None,
        message_type: str = "script_execution",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a message to the session."""
        try:
            config: Dict[str, Any] = {
                "source": source,
                "content": content,
                "message_type": message_type,
            }
            if metadata:
                config["metadata"] = metadata
            message = Message(
                user_id=user_id,
                session_id=session_id,
                run_id=run_id,
                config=config,
            )
            db.upsert(message)
        except Exception as e:
            logger.warning(f"Failed to save message to session: {e}")

    async def execute_script(
        self,
        websocket: WebSocket,
        script_data: Dict[str, Any],
        session_id: Optional[int] = None,
        db: Any = None,
        user_id: Optional[str] = None,
    ) -> ReplayResult:
        """
        Execute a script and stream progress via WebSocket.

        Args:
            websocket: WebSocket connection for progress updates
            script_data: Script data containing task, start_url, actions, etc.
            session_id: Optional session ID for tracking
            db: Database connection for saving messages
            user_id: User ID for message ownership

        Returns:
            ReplayResult with execution details
        """
        self._websocket = websocket
        self._is_running = True
        self._should_stop = False
        self._db = db
        self._session_id = session_id
        self._user_id = user_id

        task = script_data.get("task", "Execute Script")
        start_url = script_data.get("start_url", "")
        actions = script_data.get("actions", [])
        viewport_width = script_data.get("viewport_width", 1280)
        viewport_height = script_data.get("viewport_height", 720)

        vnc_port = None
        result = None
        run_id = None

        try:
            # Create a Run to track this script execution
            if session_id and db:
                run_id = self._create_run(
                    db=db,
                    session_id=session_id,
                    task=f"Execute script: {task}",
                )
                logger.info(f"Created run {run_id} for script execution in session {session_id}")

            # Save initial user message to session (the task/request)
            if session_id and db and user_id:
                self._save_message_to_session(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    source="user",
                    content=f"Execute script: {task}\nStart URL: {start_url}",
                    run_id=run_id,
                    message_type="text",
                )

            # Notify start
            await self._send_message({
                "type": "script_execution_start",
                "data": {
                    "task": task,
                    "total_actions": len(actions),
                    "start_url": start_url,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Start browser
            await self._send_message({
                "type": "script_status",
                "status": "starting_browser",
                "message": "Starting browser...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            _, page, vnc_port = await self._start_browser(
                headless=False,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )

            # Send VNC port if available
            if vnc_port:
                await self._send_message({
                    "type": "vnc_info",
                    "data": {
                        "vnc_port": vnc_port,
                        "vnc_url": f"http://localhost:{vnc_port}/vnc.html",
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            await self._send_message({
                "type": "script_status",
                "status": "browser_ready",
                "message": "Browser ready, starting execution...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Create replay engine with callbacks
            def on_action_start(index: int, description: str):
                if self._should_stop:
                    return
                asyncio.create_task(self._send_message({
                    "type": "action_start",
                    "data": {
                        "action_index": index,
                        "description": description,
                        "total_actions": len(actions),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))

            def on_action_complete(action_result: ActionResult):
                if self._should_stop:
                    return
                # Encode screenshot if present
                screenshot_base64 = None
                if action_result.screenshot:
                    screenshot_base64 = base64.b64encode(action_result.screenshot).decode()

                asyncio.create_task(self._send_message({
                    "type": "action_complete",
                    "data": {
                        "action_index": action_result.action_index,
                        "action_type": action_result.action_type,
                        "description": action_result.description,
                        "status": action_result.status.value,
                        "error": action_result.error,
                        "screenshot": screenshot_base64,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))

            def should_stop_check() -> bool:
                """Check if execution should be stopped."""
                return self._should_stop

            engine = PlaywrightReplayEngine(
                on_action_start=on_action_start,
                on_action_complete=on_action_complete,
                should_stop=should_stop_check,
            )

            # Execute script
            result = await engine.replay(
                page=page,
                actions=actions,
                start_url=start_url,
                stop_on_error=True,
            )

            # Capture final screenshot
            final_screenshot = None
            try:
                screenshot_bytes = await page.screenshot()
                final_screenshot = base64.b64encode(screenshot_bytes).decode()
            except Exception:
                pass

            # Send completion
            await self._send_message({
                "type": "script_execution_complete",
                "data": {
                    "success": result.success,
                    "total_actions": result.total_actions,
                    "completed_actions": result.completed_actions,
                    "failed_action_index": result.failed_action_index,
                    "error": result.error,
                    "final_screenshot": final_screenshot,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Save completion message to session with structured data
            if session_id and db and user_id:
                # Build structured content for rich display
                script_result_data = {
                    "task": task,
                    "start_url": start_url,
                    "success": result.success,
                    "total_actions": result.total_actions,
                    "completed_actions": result.completed_actions,
                    "error": result.error,
                    "actions": [
                        {
                            "action_type": a.get("action_type", ""),
                            "description": a.get("description", ""),
                            "selector": a.get("selector"),
                        }
                        for a in actions
                    ],
                    "final_screenshot": final_screenshot,
                }
                self._save_message_to_session(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    source="ScriptExecutor",
                    content=json.dumps(script_result_data),
                    run_id=run_id,
                    message_type="text",
                    metadata={"type": "script_execution_result"},
                )

            # Update Run status
            if run_id and db:
                final_status = RunStatus.COMPLETE if result.success else RunStatus.ERROR
                self._update_run_status(db=db, run_id=run_id, status=final_status)

            return result

        except Exception as e:
            logger.error(f"Script execution error: {e}")
            await self._send_message({
                "type": "script_execution_error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Save error message to session
            if session_id and db and user_id:
                self._save_message_to_session(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    source="ScriptExecutor",
                    content=f"Script execution error: {str(e)}",
                    run_id=run_id,
                    message_type="script_execution",
                )

            # Update Run status to ERROR
            if run_id and db:
                self._update_run_status(db=db, run_id=run_id, status=RunStatus.ERROR)

            return ReplayResult(
                success=False,
                total_actions=len(actions),
                completed_actions=0,
                error=str(e),
            )

        finally:
            self._is_running = False
            # Keep browser open for a bit so user can see final state
            await asyncio.sleep(2)
            await self._stop_browser()

    async def stop(self) -> None:
        """Stop current execution."""
        self._should_stop = True
        await self._stop_browser()

    @property
    def is_running(self) -> bool:
        return self._is_running
