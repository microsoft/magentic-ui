"""WebSocket connection manager for the magentic-ui agent runtime.

Stream lifecycle:
- start_stream() owns the full lifecycle: waits for any previous stream to
  finish, then launches a new background task (_execute_stream).
- stop_run() uses asyncio task cancellation (task.cancel()) to interrupt the
  agent at whatever await it's suspended on, waits for cleanup, then notifies
  the frontend. This ensures no race between stop and restart.
- disconnect() starts a grace period for reconnection (e.g., page refresh).
  If no reconnect within timeout, calls stop_run().
- _execute_stream's finally block closes the team manager once the agent
  stream reaches a terminal state. Subsequent turns reload from DB.

Pause/Resume design:
- TeamManager owns a single asyncio.Queue per run
- Agent yields input_request via normal message path, then awaits on queue
- Connection layer routes messages to unblock the agent
- Input timeout (1 hour) triggers stop with timeout message
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from fastapi import WebSocket, WebSocketDisconnect

from ....agents.web_surfer.fara._types import StreamUpdate
from loguru import logger

from ...database import DatabaseManager
from ...datamodel import Message, MessageConfig, Run, RunStatus
from ...teammanager import TeamManager
from ...utils.utils import construct_task

from ....magentic_ui_config import MagenticUIConfig
from ....approval import (
    AGENT_INPUT_SESSION_AUTO_APPROVE,
    ApprovalDecision,
    ApprovalSource,
)
from ....sandbox._path_normalizer import extract_dir_basename
from ....tools.playwright.browser import BrowserSlotPoolFullError
from ._pool_full import handle_pool_full, maybe_retry_after_pool_full
from ._continuation_response import (
    normalize_continuation_decision,
    save_continuation_response,
)

if TYPE_CHECKING:
    from ....tools.playwright.browser.quicksand_browser_manager import (
        QuicksandBrowserManager,
    )


def _truncate_for_log(obj: Any, max_len: int = 50) -> Any:
    """Recursively truncate long strings (e.g., base64 images) for logging."""
    if isinstance(obj, str):
        return obj[:max_len] + "...[truncated]" if len(obj) > max_len else obj
    if isinstance(obj, dict):
        return {k: _truncate_for_log(v, max_len) for k, v in obj.items()}  # type: ignore[misc]
    if isinstance(obj, list):
        return [_truncate_for_log(item, max_len) for item in obj]  # type: ignore[misc]
    return obj


_SENSITIVE_LOG_KEYS = {"password", "token", "api_key", "secret"}


def _scrub_for_log(obj: Any) -> Any:
    """Recursively redact known-sensitive values (e.g. VNC password) for log output."""
    if isinstance(obj, dict):
        items = cast(Dict[str, Any], obj).items()
        return {
            k: "***REDACTED***"
            if k.lower() in _SENSITIVE_LOG_KEYS
            else _scrub_for_log(v)
            for k, v in items
        }
    if isinstance(obj, list):
        items_list = cast(List[Any], obj)
        return [_scrub_for_log(item) for item in items_list]
    return obj


def _normalize_mount_dirs(raw: Any) -> list[str] | None:
    """Filter ``mount_dirs`` value to non-blank string entries; ``None`` for non-list."""
    if not isinstance(raw, list):
        return None
    items = cast(list[Any], raw)
    return [item for item in items if isinstance(item, str) and item.strip()]


def _mounted_folder_metadata(mount_dirs: list[str] | None) -> Optional[Dict[str, str]]:
    """Build mounted folder metadata from start-task settings."""
    folder_path = next((item for item in mount_dirs or [] if item), None)
    if folder_path is None:
        return None
    folder_name = extract_dir_basename(folder_path) or folder_path
    return {"name": folder_name, "path": folder_path}


def _user_message_metadata(
    attached_files_json: str,
    mount_dirs: list[str] | None,
) -> Dict[str, Any]:
    """Build metadata for saved and broadcast user messages."""
    metadata: Dict[str, Any] = {"attached_files": attached_files_json}
    mounted_folder = _mounted_folder_metadata(mount_dirs)
    if mounted_folder is not None:
        metadata["mounted_folder"] = mounted_folder
    return metadata


def _find_browser_agent(agent: Any) -> Any | None:
    """Return a sub-agent exposing ``current_browser_address()``, or None.

    Looks at the top-level agent first, then iterates an ``_agent_registry``
    (e.g. OmniAgent's delegate tools). Caller owns the cross-layer reach;
    nothing about browser addresses is exposed via TeamManager.
    """
    if hasattr(agent, "current_browser_address"):
        return agent
    registry = getattr(agent, "_agent_registry", None)
    if registry is None:
        return None
    for entry in registry:
        wrapped = getattr(entry, "agent", None)
        if wrapped is not None and hasattr(wrapped, "current_browser_address"):
            return wrapped
    return None


class WebSocketManager:
    """
    Manages WebSocket connections and message streaming for team task execution.

    Args:
        db_manager: Database manager instance.
        app_dir: Host-side workspace root directory.
        config: Magentic UI configuration.
        quicksand_manager: Optional Quicksand browser manager.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        app_dir: Path,
        config: MagenticUIConfig,
        quicksand_manager: "QuicksandBrowserManager | None" = None,
    ) -> None:
        self.db_manager = db_manager
        self.app_dir = app_dir
        self.config = config
        self._quicksand_manager = quicksand_manager

        self._connections: Dict[int, WebSocket] = {}
        self._closed_connections: set[int] = set()
        self._team_managers: Dict[int, TeamManager] = {}
        self._stream_tasks: Dict[int, asyncio.Task[None]] = {}
        self._grace_tasks: Dict[int, asyncio.Task[None]] = {}
        self._stopping_runs: set[int] = set()  # idempotency guard for stop_run

    async def connect(
        self,
        websocket: WebSocket,
        run_id: int,
        subprotocol: str | None = None,
    ) -> bool:
        """Accept WebSocket connection, optionally echoing an agreed subprotocol."""
        try:
            await websocket.accept(subprotocol=subprotocol)
            self._connections[run_id] = websocket
            self._closed_connections.discard(run_id)
            # Cancel grace period — client reconnected
            old_task = self._grace_tasks.pop(run_id, None)
            if old_task and not old_task.done():
                old_task.cancel()
            # Page refresh wipes chatStore, including the per-slot VNC
            # password. Re-emit browser_address from the live slot so the
            # noVNC viewer survives reconnect. Slot remains the single
            # source of truth; nothing is cached.
            await self._reemit_browser_address(run_id)
            return True
        except Exception as e:
            logger.error(f"Connection error for run {run_id}: {e}")
            return False

    async def _reemit_browser_address(self, run_id: int) -> None:
        """Send a fresh browser_address frame if a live slot is bound."""
        team_manager = self._team_managers.get(run_id)
        if team_manager is None or team_manager.agent is None:
            return
        agent = _find_browser_agent(team_manager.agent)
        if agent is None:
            return
        addr = agent.current_browser_address()
        if addr is None:
            return
        await self._send_message(
            run_id,
            {
                "type": "message",
                "data": {
                    "source": addr.get("source", "web_surfer"),
                    "content": [],
                    "metadata": addr,
                },
            },
        )

    async def start_stream(
        self,
        run_id: int,
        task: str,
        files: Optional[List[Dict[str, Any]]] = None,
        settings_config: Optional[Dict[str, Any]] = None,
        echo_user_message: bool = True,
    ) -> None:
        """Start streaming task execution.

        Owns the full stream lifecycle: if a previous stream is still shutting
        down for this run_id, waits for it to finish before starting a new one.

        Args:
            run_id: ID of the run
            task: Task string to execute
            files: Optional file attachments from the frontend start message.
            settings_config: Optional config override from frontend.
                If non-empty, shallow-merged on top of self.config
                (frontend top-level keys replace CLI values, including nested dicts).
                If empty or None, self.config (CLI --config file) is used as-is.
            echo_user_message: When False, suppress sending the task as a
                user message. Use when the caller has already echoed a reply.
        """
        # Wait for any previous stream to finish cleanup (e.g., after stop)
        old_task = self._stream_tasks.get(run_id)
        if old_task and not old_task.done():
            logger.info(f"Awaiting previous stream cleanup for run {run_id}")
            try:
                await asyncio.wait_for(old_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Previous stream for run {run_id} didn't finish in 30s, "
                    "force-cancelling"
                )
                old_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await old_task
            except Exception as e:
                # Old task crashed — that's fine, we just need it to be done
                logger.warning(
                    f"Previous stream for run {run_id} raised {type(e).__name__}: {e}"
                )

        # Launch new stream task
        self._stream_tasks[run_id] = asyncio.create_task(
            self._execute_stream(
                run_id,
                task,
                files=files,
                settings_config=settings_config,
                echo_user_message=echo_user_message,
            )
        )

    async def _execute_stream(
        self,
        run_id: int,
        task: str,
        files: Optional[List[Dict[str, Any]]] = None,
        settings_config: Optional[Dict[str, Any]] = None,
        echo_user_message: bool = True,
    ) -> None:
        """Internal: run the agent stream with full cleanup on exit.

        The entire body is wrapped in try/finally so that _stream_tasks
        cleanup always runs — even if the connection guard raises early.
        """
        team_manager: Optional[TeamManager] = None
        agent_task = task  # Task string sent to agent (may include file references)
        attached_files_json = json.dumps([])  # Metadata for DB/WS storage
        try:
            if run_id not in self._connections or run_id in self._closed_connections:
                raise ValueError(f"No active connection for run {run_id}")

            # Frontend may send settings_config with overrides (e.g. mount_dirs)
            effective_settings = settings_config or {}

            # Wait for quicksand VM if it's booting in the background
            if self._quicksand_manager is not None:
                from ..deps import wait_for_quicksand

                quicksand = await wait_for_quicksand()
                if quicksand is None:
                    logger.warning("Quicksand configured but failed to start")
            else:
                quicksand = None

            # Create team manager if needed
            if run_id not in self._team_managers:
                team_manager = TeamManager(
                    app_dir=self.app_dir,
                    config=self.config,
                    quicksand_manager=quicksand,
                    db_manager=self.db_manager,
                )
                self._team_managers[run_id] = team_manager
            else:
                team_manager = self._team_managers[run_id]

            # Get run from database first — needed below to scope uploaded-file
            # path validation to this run's directory (not the shared
            # files/user root, which would let a malicious WS payload reference
            # other runs' files).
            run = await self._get_run(run_id)
            if run is None:
                raise ValueError(f"Run {run_id} not found in database")

            # Reset uploaded-file infos at the start of every task. The
            # TeamManager is reused across tasks for the same run_id, so
            # without this reset the next task's end-of-run summary would
            # incorrectly include the previous task's uploads.
            team_manager.set_uploaded_file_infos([], run=run)

            # Process file attachments: augment task string and register uploaded names
            if files:
                valid_files = [f for f in files if isinstance(f, dict)]
                if len(valid_files) != len(files):
                    logger.warning(
                        "Run %s: Ignoring %d invalid file entries (expected dicts)",
                        run_id,
                        len(files) - len(valid_files),
                    )
                if valid_files:
                    result = construct_task(task, valid_files)
                    agent_task = result["agent_task"]
                    attached_files_json = result["attached_files_json"]
                    # Record full uploaded-file info so the end-of-run
                    # summary can list them under "Files you uploaded".
                    # Pass `run` so validation is scoped to this run's dir.
                    team_manager.set_uploaded_file_infos(
                        result["attached_files"], run=run
                    )

            # Update run status — store clean task content (no file references)
            run.task = MessageConfig(content=task, source="user").model_dump()
            run.status = RunStatus.ACTIVE
            self.db_manager.upsert(run)
            await self._update_run_status(run_id, RunStatus.ACTIVE)

            raw_mount_dirs = effective_settings.get("mount_dirs")
            mount_dirs = _normalize_mount_dirs(raw_mount_dirs)
            if raw_mount_dirs is not None and mount_dirs is None:
                logger.warning(
                    "mount_dirs has invalid type {}, ignoring (run_id={})",
                    type(raw_mount_dirs).__name__,
                    run_id,
                )

            # Send and persist the user message — unless the caller already
            # echoed a reply in its place.
            if echo_user_message:
                user_message_metadata = _user_message_metadata(
                    attached_files_json, mount_dirs
                )
                await self._send_message(
                    run_id,
                    {
                        "type": "message",
                        "data": {
                            "source": "user",
                            "content": task,
                            "metadata": user_message_metadata,
                        },
                    },
                )

                await self._save_message(
                    run_id,
                    {
                        "source": "user",
                        "content": task,
                        "type": "user_message",
                        "metadata": user_message_metadata,
                    },
                )

            logger.info(
                "mount_dirs from settings_config: {!r}",
                mount_dirs,
            )

            # Stream agent responses
            logger.debug(f"Starting to stream agent responses for run {run_id}")
            update_count = 0
            async for update in team_manager.run_stream(
                task=agent_task, run=run, mount_dirs=mount_dirs
            ):
                update_count += 1
                logger.debug(
                    f"Received update #{update_count}: text={update.text[:100] if update.text else 'None'}"
                )
                props: Dict[str, Any] = update.additional_properties or {}

                # Transient agent_state signal: forward to the WS and do not
                # persist — the next persistent message clears it.
                if props.get("type") == "agent_state":
                    await self._send_message(
                        run_id,
                        {
                            "type": "agent_state",
                            "state": props.get("state"),
                            "source": props.get("source", "unknown_agent"),
                        },
                    )
                    continue

                # Handle system messages (e.g., status updates like "paused", "complete", "error")
                if props.get("type") == "system":
                    status_str: str = props.get("status", "")
                    content: str | None = props.get("content")
                    logger.info(f"System message for run {run_id}: status={status_str}")

                    # Map status string to RunStatus enum
                    status_map: dict[str, RunStatus] = {
                        "paused": RunStatus.PAUSED,
                        "awaiting_input": RunStatus.AWAITING_INPUT,
                        "complete": RunStatus.COMPLETE,
                        "error": RunStatus.ERROR,
                        "stopped": RunStatus.STOPPED,
                    }
                    run_status = status_map.get(status_str)
                    if run_status:
                        await self._update_run_status(
                            run_id, run_status, content=content
                        )
                    else:
                        # Unknown status - just send as-is without DB update
                        logger.warning(f"Unknown system status: {status_str}")
                        await self._send_message(
                            run_id,
                            {
                                "type": "system",
                                "status": status_str,
                            },
                        )

                    await self._save_message(run_id, self._update_to_dict(update))
                    continue  # Skip normal message formatting

                # Handle input_request specially - frontend expects type: "input_request" at top level
                if props.get("type") == "input_request":
                    logger.info(
                        f"Input request detected for run {run_id}, sending input_request message"
                    )
                    # Note: DB status already set to PAUSED by preceding system message

                    msg: dict[str, Any] = {
                        "type": "input_request",
                        "input_type": props.get("input_type", "text_input"),
                    }
                    if props.get("content"):
                        msg["content"] = props["content"]
                    # Forward approval-specific fields
                    for key in ("tool", "tool_args", "category", "reason"):
                        if props.get(key) is not None:
                            msg[key] = props[key]
                    await self._send_message(run_id, msg)
                    await self._save_message(run_id, self._update_to_dict(update))
                    continue  # Skip normal message formatting

                # Handle file generated/modified messages
                if props.get("type") == "file":
                    raw_files = props.get("files", "[]")
                    try:
                        files_list = json.loads(raw_files)
                    except (TypeError, json.JSONDecodeError) as e:
                        logger.warning(
                            f"Failed to parse 'files' payload for run {run_id}: {e}. "
                            f"Raw value: {_truncate_for_log(raw_files)}"
                        )
                        files_list = []

                    file_msg: dict[str, Any] = {
                        "type": "file",
                        "files": files_list,
                    }
                    # Forward the summary flag so the frontend can render the
                    # end-of-run aggregated message under a header.
                    if props.get("summary"):
                        file_msg["summary"] = True
                    # Forward the uploaded-file list (only present on the
                    # summary message) so the frontend can show a separate
                    # "Files you uploaded" section.
                    raw_uploaded = props.get("uploaded_files")
                    if isinstance(raw_uploaded, str):
                        try:
                            uploaded_list = json.loads(raw_uploaded)
                        except (TypeError, json.JSONDecodeError) as e:
                            logger.warning(
                                f"Failed to parse 'uploaded_files' for run {run_id}: {e}. "
                                f"Raw value: {_truncate_for_log(raw_uploaded)}"
                            )
                            uploaded_list = []
                        if uploaded_list:
                            file_msg["uploaded_files"] = uploaded_list
                    await self._send_message(run_id, file_msg)
                    await self._save_message(run_id, self._update_to_dict(update))
                    continue

                formatted = self._format_response_update(update)
                # Lazy: only run the scrub/truncate work when DEBUG is enabled.
                logger.opt(lazy=True).debug(
                    "Formatted message: {}",
                    lambda: _truncate_for_log(_scrub_for_log(formatted)),
                )
                await self._send_message(run_id, formatted)
                await self._save_message(run_id, self._update_to_dict(update))

            # Stream completed normally - mark run as complete if still active
            logger.debug(f"Stream completed with {update_count} updates")
            run = await self._get_run(run_id)
            if run is None or run.status == RunStatus.ACTIVE:
                await self._update_run_status(run_id, RunStatus.COMPLETE)

        except asyncio.TimeoutError as e:
            # Input timeout from agent - stop the run with timeout message
            timeout_msg = (
                str(e)
                if str(e)
                else "MagenticLite timed out while waiting for your input."
            )
            logger.warning(f"Input timeout for run {run_id}: {timeout_msg}")
            await self._update_run_status(
                run_id, RunStatus.STOPPED, content=timeout_msg
            )
            await self._save_message(
                run_id,
                {
                    "source": "system",
                    "content": [{"type": "text", "text": timeout_msg}],
                    "metadata": {
                        "source": "system",
                        "type": "system",
                        "status": "stopped",
                    },
                },
            )

        except asyncio.CancelledError:
            # task.cancel() was called (stop_run) — stop_run handles status/message
            logger.info(f"Run {run_id} cancelled")

        except BrowserSlotPoolFullError as e:
            logger.info(f"Live browser pool full for run {run_id}: {e}")
            await handle_pool_full(self, run_id, str(e))

        except Exception as e:
            logger.error(f"Stream error for run {run_id}: {e}")
            traceback.print_exc()
            await self._handle_stream_error(run_id, e)

        finally:
            # Close the team manager once the stream truly ends. Skip if
            # stop_run owns cleanup, or if the stream is suspended waiting
            # on user input.
            self._stream_tasks.pop(run_id, None)
            if (
                run_id in self._team_managers
                and run_id not in self._stopping_runs
                and not await self._run_is_mid_input(run_id)
            ):
                tm = self._team_managers.pop(run_id)
                try:
                    await tm.close()
                except Exception:
                    logger.exception(
                        f"Error closing team manager for run {run_id} after stream end"
                    )

    def _format_response_update(self, update: StreamUpdate) -> Dict[str, Any]:
        """Format StreamUpdate for WebSocket transmission."""
        contents: list[dict[str, Any]] = []

        # Handle text content
        # Note: Frontend expects {"type": "text", "text": ...} not {"type": "text", "content": ...}
        if update.text:
            contents.append({"type": "text", "text": update.text})

        # Extract metadata from additional_properties
        props = update.additional_properties or {}

        # Handle image content from additional_properties
        # Per websocket-messages.md: { type: "image", url: "data:image/png;base64,..." }
        if "image" in props and props["image"]:
            contents.append(
                {
                    "type": "image",
                    "url": props["image"],
                }
            )

        return {
            "type": "message",
            "data": {
                # Agent should set "source" in additional_properties.
                # Fallback to "unknown_agent" makes missing source obvious.
                "source": props.get("source", "unknown_agent"),
                "content": contents,
                "metadata": props,
            },
        }

    def _update_to_dict(self, update: StreamUpdate) -> Dict[str, Any]:
        """Convert StreamUpdate to dict for database storage."""
        props = update.additional_properties or {}

        # Build content array matching _format_response_update
        contents: list[dict[str, Any]] = []
        if update.text:
            contents.append({"type": "text", "text": update.text})
        if "image" in props and props["image"]:
            contents.append(
                {
                    "type": "image",
                    "url": props["image"],
                }
            )

        # Fallback: include metadata "content" string when no other content exists.
        # This ensures input_request and system messages (which carry text in
        # props["content"] rather than update.text) get stored with readable content.
        if not contents and isinstance(props.get("content"), str) and props["content"]:
            contents.append({"type": "text", "text": props["content"]})

        return {
            "source": props.get("source", "unknown_agent"),
            "content": contents,
            "metadata": props,
        }

    async def _save_message(self, run_id: int, message_dict: Dict[str, Any]) -> None:
        """Save a message to the database; strip browser_address passwords."""
        raw_metadata = message_dict.get("metadata")
        if isinstance(raw_metadata, dict):
            metadata = cast(Dict[str, Any], raw_metadata)
            if metadata.get("type") == "browser_address" and "password" in metadata:
                scrubbed = {k: v for k, v in metadata.items() if k != "password"}
                message_dict = {**message_dict, "metadata": scrubbed}
        run = await self._get_run(run_id)
        if run:
            db_message = Message(
                created_at=datetime.now(timezone.utc),
                session_id=run.session_id,
                run_id=run_id,
                config=message_dict,
                user_id=run.user_id,
            )
            self.db_manager.upsert(db_message)

    async def _send_message(self, run_id: int, message: Dict[str, Any]) -> None:
        """Send a message through WebSocket.

        Stamps every outgoing frame with a server-side UTC ISO timestamp so the
        frontend can render consistent times for both live and history messages.
        """
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        logger.debug(
            f"_send_message called for run {run_id}, type={message.get('type')}"
        )
        if run_id in self._closed_connections:
            logger.warning(f"Attempted to send to closed connection: run {run_id}")
            return

        try:
            if run_id in self._connections:
                websocket = self._connections[run_id]
                logger.debug(f"Sending via websocket: {message.get('type')}")
                await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected during send for run {run_id}")
            self._closed_connections.add(run_id)
            self._connections.pop(run_id, None)
        except Exception as e:
            logger.error(f"WebSocket send error for run {run_id}: {e}")
            self._closed_connections.add(run_id)
            self._connections.pop(run_id, None)

    async def _handle_stream_error(self, run_id: int, error: Exception) -> None:
        """Handle stream errors and persist error detail as a Message record."""
        error_text = str(error) or f"{type(error).__name__}: (no message)"
        await self._update_run_status(run_id, RunStatus.ERROR, content=error_text)
        await self._save_message(
            run_id,
            {
                "source": "system",
                "content": [{"type": "text", "text": error_text}],
                "metadata": {"source": "system", "type": "error"},
            },
        )

    async def stop_run(self, run_id: int, reason: str = "Stopped by user") -> None:
        """Stop a running task, wait for cleanup, then notify frontend.

        Uses asyncio task cancellation to interrupt the agent at whatever await
        it's currently suspended on (including mid-LLM calls). The stream task's
        finally block only tears down per-task mounts; the team manager (and its
        agent + browser) is closed here after the stream fully exits.

        Only sends the "stopped" status after the stream is fully cleaned up,
        preventing the race where a user restarts before cleanup finishes.
        """
        logger.info(f"Stopping run {run_id}: {reason}")

        # Idempotency: if another stop_run call is already in progress
        # (e.g., user stop + grace period timeout), skip duplicate work.
        if run_id in self._stopping_runs:
            logger.info(f"Run {run_id} stop already in progress, skipping")
            return
        self._stopping_runs.add(run_id)

        try:
            # Cancel the stream task — injects CancelledError at current await
            stream_task = self._stream_tasks.get(run_id)
            if stream_task and not stream_task.done():
                stream_task.cancel()
                try:
                    await stream_task  # wait for finally block to clean up
                except (asyncio.CancelledError, Exception) as e:
                    # CancelledError is the normal case (task.cancel() worked).
                    # Other exceptions mean the stream crashed around the same time
                    # — either way, the task is done and we can proceed.
                    if not isinstance(e, asyncio.CancelledError):
                        logger.warning(
                            f"Stream task for run {run_id} raised "
                            f"{type(e).__name__} during stop: {e}"
                        )

            # Stream is fully stopped — safe to update DB and notify frontend
            await self._update_run_status(run_id, RunStatus.STOPPED, content=reason)
            await self._save_message(
                run_id,
                {
                    "source": "system",
                    "content": [{"type": "text", "text": reason}],
                    "metadata": {
                        "source": "system",
                        "type": "system",
                        "status": "stopped",
                    },
                },
            )
            team_manager = self._team_managers.pop(run_id, None)
            if team_manager:
                await team_manager.close()
        finally:
            self._stopping_runs.discard(run_id)

    async def disconnect(self, run_id: int, ws: Optional[WebSocket] = None) -> None:
        """Clean up WebSocket connection. Starts a grace period for reconnection.

        The stream task continues in the background, saving messages to DB.
        If no reconnect happens within the grace period, the run is stopped.
        When a new WS connects via connect(), _closed_connections is cleared
        and messages resume flowing to the frontend.
        """
        # Stale disconnect guard: if connect() already replaced the WS,
        # don't touch connections — but still ensure a grace period runs
        # in case _send_message() already marked this run as closed.
        if ws is not None and self._connections.get(run_id) is not ws:
            logger.info(f"Stale disconnect for run {run_id}, skipping WS cleanup")
            if run_id in self._closed_connections:
                self._start_grace_period(run_id)
            return

        logger.info(f"Disconnecting WS for run {run_id}")
        self._closed_connections.add(run_id)

        # Remove WS reference (re-check identity to handle race)
        if ws is None or self._connections.get(run_id) is ws:
            self._connections.pop(run_id, None)

        # Start grace period — stop the run if no reconnect within timeout
        self._start_grace_period(run_id)

    def _start_grace_period(self, run_id: int) -> None:
        """Cancel any existing grace task for this run and start a new one."""
        old_task = self._grace_tasks.pop(run_id, None)
        if old_task and not old_task.done():
            old_task.cancel()
        self._grace_tasks[run_id] = asyncio.create_task(
            self._disconnect_grace_period(run_id)
        )

    async def _run_is_mid_input(self, run_id: int) -> bool:
        """True iff the run is suspended waiting for user input."""
        run = await self._get_run(run_id)
        if run is None:
            return False
        return run.status in (RunStatus.AWAITING_INPUT, RunStatus.PAUSED)

    async def _disconnect_grace_period(
        self, run_id: int, timeout: float = 60.0
    ) -> None:
        """Wait for reconnection, then stop the run if still disconnected."""
        await asyncio.sleep(timeout)
        if run_id not in self._closed_connections:
            self._grace_tasks.pop(run_id, None)
            return  # Reconnected — nothing to do

        # Only stop if the run is still in an active state.
        # If the stream already completed/errored/stopped, don't overwrite.
        run = await self._get_run(run_id)
        if run and run.status in (
            RunStatus.ACTIVE,
            RunStatus.CREATED,
            RunStatus.PAUSED,
            RunStatus.AWAITING_INPUT,
        ):
            logger.info(f"No reconnect for run {run_id} after {timeout}s, stopping")
            await self.stop_run(run_id, "Connection lost")
        elif run is not None:
            # Terminal run: TM was already closed when the stream ended
            # (see _execute_stream finally). Nothing to do here.
            logger.info(
                f"Grace period for run {run_id}: state {run.status.value}, "
                "team manager already closed"
            )
        else:
            # Run gone from DB — close any straggler TM.
            logger.warning(f"Grace period for run {run_id}: run not in DB, closing TM")
            team_manager = self._team_managers.pop(run_id, None)
            if team_manager:
                await team_manager.close()

        # Clean up stale entries
        self._closed_connections.discard(run_id)
        self._grace_tasks.pop(run_id, None)

    async def _get_run(self, run_id: int) -> Optional[Run]:
        """Get run from database."""
        response = self.db_manager.get(Run, filters={"id": run_id}, return_json=False)
        return response.data[0] if response.status and response.data else None

    async def _update_run_status(
        self, run_id: int, status: RunStatus, content: Optional[str] = None
    ) -> None:
        """Update run status in database and notify frontend.

        This is the single source of truth for status changes. It:
        1. Updates the database
        2. Sends a system message to the frontend

        Args:
            run_id: The run ID to update.
            status: The new status.
            content: Optional message content (e.g., error message, stop reason).
        """
        run = await self._get_run(run_id)
        if run:
            run.status = status
            if content and status == RunStatus.ERROR:
                run.error_message = content
            self.db_manager.upsert(run)

        msg: dict[str, Any] = {
            "type": "system",
            "status": status.value if hasattr(status, "value") else str(status),
        }
        if content:
            msg["content"] = content
        await self._send_message(run_id, msg)

    async def _update_run(
        self,
        run_id: int,
        status: RunStatus,
        team_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update run status and result."""
        run = await self._get_run(run_id)
        if run:
            run.status = status
            if team_result:
                run.team_result = team_result
            if error:
                run.error_message = error
            self.db_manager.upsert(run)

    async def cleanup(self) -> None:
        """Clean up all connections on shutdown.

        Stops all active runs immediately (no grace period).
        """
        active_run_ids = set(self._stream_tasks.keys())
        logger.info(
            f"Cleaning up {len(self._connections)} connections, "
            f"{len(active_run_ids)} active runs"
        )

        try:
            for run_id in active_run_ids:
                try:
                    await asyncio.wait_for(
                        self.stop_run(run_id, "Server shutting down"), timeout=5
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout stopping run {run_id}")
                except Exception as e:
                    logger.error(f"Error stopping run {run_id}: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        finally:
            # Cancel all outstanding grace period tasks
            for task in self._grace_tasks.values():
                if not task.done():
                    task.cancel()
            self._grace_tasks.clear()

            # Force-cancel any remaining stream tasks
            for task in self._stream_tasks.values():
                if not task.done():
                    task.cancel()
            self._stream_tasks.clear()

            self._connections.clear()
            self._closed_connections.clear()
            self._stopping_runs.clear()
            # Force-close any remaining team managers (e.g. if stop_run timed out)
            for tm in self._team_managers.values():
                try:
                    await tm.close()
                except Exception:
                    pass
            self._team_managers.clear()

    @property
    def active_connections(self) -> set[int]:
        """Get set of active run IDs."""
        return set(self._connections.keys()) - self._closed_connections

    # --- Pause/Resume/Input handlers ---

    async def _save_approval_response(
        self,
        run_id: int,
        content: str,
        decision: str,
        source: str,
    ) -> None:
        """Broadcast and persist an approval response message."""
        approval_msg: dict[str, Any] = {
            "source": "user",
            "content": content,
            "type": "approval_response",
            "metadata": {
                "type": "approval_response",
                "decision": decision,
                "approval_source": source,
            },
        }
        await self._send_message(
            run_id,
            {"type": "message", "data": approval_msg},
        )
        await self._save_message(run_id, approval_msg)

    async def _set_active_if_awaiting(self, run_id: int) -> None:
        """Set run status to ACTIVE only if currently awaiting input or paused.

        Guards against late/duplicate responses overwriting terminal states.
        """
        run = await self._get_run(run_id)
        if run and run.status in (RunStatus.AWAITING_INPUT, RunStatus.PAUSED):
            await self._update_run_status(run_id, RunStatus.ACTIVE)

    async def _apply_input_files(
        self,
        run_id: int,
        team_manager: TeamManager,
        response: str,
        files: list[dict[str, Any]] | None,
    ) -> tuple[str, str]:
        """Validate mid-session uploads and merge them into the response.

        Returns ``(agent_response, attached_files_json)``. The JSON is
        ``"[]"`` when no valid files were attached, matching the
        start-task wire format.
        """
        attached_files_json = json.dumps([])
        if not files:
            return response, attached_files_json

        valid_files = [f for f in files if isinstance(f, dict)]
        if len(valid_files) != len(files):
            logger.warning(
                "Run %s: ignoring %d invalid file entries on input_response "
                "(expected dicts)",
                run_id,
                len(files) - len(valid_files),
            )
        if not valid_files:
            return response, attached_files_json

        run = await self._get_run(run_id)
        if run is None:
            logger.warning(
                "Run %s: not in DB; ignoring %d file attachment(s) "
                "on input_response (text reply will still be sent)",
                run_id,
                len(valid_files),
            )
            return response, attached_files_json

        safe_refs = team_manager.add_uploaded_files(valid_files, run=run)
        if not safe_refs:
            return response, attached_files_json

        result = construct_task(response, safe_refs)
        return result["agent_task"], result["attached_files_json"]

    async def handle_input_response(
        self,
        run_id: int,
        response: str,
        files: list[dict[str, Any]] | None = None,
    ) -> None:
        """Route a typed user response: approval, pending input request, or mid-run inbox.

        ``files`` are mid-session uploads (issue #291). Files attached to
        an approval-pending input are ignored.
        """
        team_manager = self._team_managers.get(run_id)
        if not team_manager:
            # No TM may mean a pool-full retry — TM was closed while waiting.
            if await maybe_retry_after_pool_full(self, run_id, response):
                return
            logger.warning(f"Received input response for inactive run {run_id}")
            return

        if team_manager.has_pending_approval:
            if files:
                logger.warning(
                    "Run %s: ignoring %d file attachment(s) on approval response "
                    "(approvals do not accept attachments)",
                    run_id,
                    len(files),
                )
            # NL approval: normalize and save as approval_response metadata
            normalized = response.strip().lower().rstrip(".!,")
            if normalized in ("yes", ApprovalDecision.APPROVE):
                decision = ApprovalDecision.APPROVE
            elif normalized in ("no", ApprovalDecision.DENY):
                decision = ApprovalDecision.DENY
            else:
                decision = ApprovalDecision.ALTERNATIVE
            await self._save_approval_response(
                run_id, response, decision, ApprovalSource.USER
            )
            team_manager.provide_input(response)
            await self._set_active_if_awaiting(run_id)
            logger.info(f"Input response handled for run {run_id} (approval)")
            return

        if team_manager.has_pending_continuation:
            decision = normalize_continuation_decision(response)
            sentinel = "yes" if decision == "continue" else "no"
            await save_continuation_response(self, run_id, response, decision)
            team_manager.provide_input(sentinel)
            await self._set_active_if_awaiting(run_id)
            logger.info(
                f"Input response handled for run {run_id} (continuation: {decision})"
            )
            return

        agent_response, attached_files_json = await self._apply_input_files(
            run_id, team_manager, response, files
        )

        await self._send_message(
            run_id,
            {
                "type": "message",
                "data": {
                    "source": "user",
                    "content": response,
                    "metadata": {"attached_files": attached_files_json},
                },
            },
        )
        await self._save_message(
            run_id,
            {
                "source": "user",
                "content": response,
                "type": "user_message",
                "metadata": {"attached_files": attached_files_json},
            },
        )

        if team_manager.has_pending_input:
            # Agent is waiting on an InputRequest — resolve it directly.
            team_manager.provide_input(agent_response)
            await self._set_active_if_awaiting(run_id)
            logger.info(f"Input response handled for run {run_id} (resumed)")
        else:
            # Agent is actively running — queue the message for the next
            # checkpoint instead of dropping it.
            team_manager.queue_user_message(agent_response)
            logger.info(f"Input response handled for run {run_id} (queued)")

    async def handle_approval_response(
        self, run_id: int, decision: str, source: str = "user"
    ) -> None:
        """Handle structured approval response from client.

        Called when the user clicks Approve/Deny buttons or when the
        frontend auto-approves based on session preferences.

        Args:
            run_id: The run to respond to.
            decision: ``"approve"`` or ``"deny"``.
            source: ``"user"`` (manual) or ``"auto_session"`` (session preference).
        """
        team_manager = self._team_managers.get(run_id)
        if team_manager:
            await self._save_approval_response(run_id, decision, decision, source)
            # When source is auto_session, send AGENT_INPUT_SESSION_AUTO_APPROVE
            # so OmniAgent sets approval_status="auto_session" on the tool_call.
            agent_input = (
                AGENT_INPUT_SESSION_AUTO_APPROVE
                if source == ApprovalSource.AUTO_SESSION
                and decision == ApprovalDecision.APPROVE
                else decision
            )
            team_manager.provide_input(agent_input)
            await self._set_active_if_awaiting(run_id)
            logger.info(
                f"Approval response handled for run {run_id}: {decision} ({source})"
            )
        else:
            logger.warning(f"Received approval response for inactive run {run_id}")

    async def handle_continuation_response(self, run_id: int, decision: str) -> None:
        """Handle a Continue/Stop button click on a max-rounds card."""
        team_manager = self._team_managers.get(run_id)
        if not team_manager:
            logger.warning(f"Received continuation response for inactive run {run_id}")
            return
        if not team_manager.has_pending_continuation:
            logger.warning(
                f"Ignoring continuation_response for run {run_id}: "
                f"team is not awaiting a continuation"
            )
            return
        sentinel = "yes" if decision == "continue" else "no"
        await save_continuation_response(self, run_id, decision, decision)
        team_manager.provide_input(sentinel)
        await self._set_active_if_awaiting(run_id)
        logger.info(f"Continuation response handled for run {run_id}: {decision}")

    async def pause_run(self, run_id: int) -> None:
        """Pause the run.

        Sets is_paused flag on agent. Agent's run_stream will yield input_request
        and await on queue at next iteration.
        """
        if (
            run_id in self._connections
            and run_id not in self._closed_connections
            and run_id in self._team_managers
        ):
            team_manager = self._team_managers.get(run_id)
            if team_manager:
                await team_manager.pause_run()
                logger.info(f"Run {run_id} paused")
        else:
            logger.warning(f"Cannot pause run {run_id}: not active")

    async def resume_run(self, run_id: int) -> None:
        """Resume the run.

        Clears is_paused flag. Agent continues after receiving input via queue.
        """
        if (
            run_id in self._connections
            and run_id not in self._closed_connections
            and run_id in self._team_managers
        ):
            team_manager = self._team_managers.get(run_id)
            if team_manager:
                await team_manager.resume_run()
                await self._update_run_status(run_id, RunStatus.ACTIVE)
                logger.info(f"Run {run_id} resumed")
        else:
            logger.warning(f"Cannot resume run {run_id}: not active")
