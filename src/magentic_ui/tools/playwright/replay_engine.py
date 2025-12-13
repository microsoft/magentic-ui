"""
Playwright Replay Engine - Executes saved scripts in the browser.
"""

import asyncio
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from playwright.async_api import Page

from .playwright_controller import PlaywrightController


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ActionResult:
    """Result of a single action execution"""
    action_index: int
    action_type: str
    description: str
    status: ActionStatus
    error: Optional[str] = None
    screenshot: Optional[bytes] = None


@dataclass
class ReplayResult:
    """Result of the entire replay execution"""
    success: bool
    total_actions: int
    completed_actions: int
    failed_action_index: Optional[int] = None
    error: Optional[str] = None
    action_results: List[ActionResult] = field(default_factory=list)


class PlaywrightReplayEngine:
    """
    Engine for replaying saved Playwright scripts.

    This engine takes a script (list of actions) and executes them
    sequentially using the PlaywrightController.
    """

    def __init__(
        self,
        playwright_controller: Optional[PlaywrightController] = None,
        on_action_start: Optional[Callable[[int, str], None]] = None,
        on_action_complete: Optional[Callable[[ActionResult], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ):
        """
        Initialize the replay engine.

        Args:
            playwright_controller: Optional controller to use. If None, creates a new one.
            on_action_start: Callback when an action starts (action_index, description)
            on_action_complete: Callback when an action completes (ActionResult)
            should_stop: Optional callback to check if execution should stop
        """
        self._controller = playwright_controller or PlaywrightController()
        self._on_action_start = on_action_start
        self._on_action_complete = on_action_complete
        self._should_stop_callback = should_stop
        self._is_running = False
        self._should_stop = False

    async def replay(
        self,
        page: Page,
        actions: List[Dict[str, Any]],
        start_url: Optional[str] = None,
        stop_on_error: bool = True,
    ) -> ReplayResult:
        """
        Execute a list of actions on the given page.

        Args:
            page: Playwright Page instance
            actions: List of action dictionaries
            start_url: Optional URL to navigate to before starting
            stop_on_error: Whether to stop execution on first error

        Returns:
            ReplayResult with execution details
        """
        self._is_running = True
        self._should_stop = False

        action_results: List[ActionResult] = []
        completed_count = 0
        failed_index = None
        error_msg = None

        try:
            # Navigate to start URL if provided
            if start_url:
                logger.info(f"Navigating to start URL: {start_url}")
                await self._controller.visit_page(page, start_url)
                await page.wait_for_load_state("networkidle")

            # Execute each action
            for idx, action in enumerate(actions):
                # Check both internal flag and external callback
                if self._should_stop or (self._should_stop_callback and self._should_stop_callback()):
                    logger.info("Replay stopped by user request")
                    break

                description = action.get("description", f"Action {idx + 1}")

                # Notify action start
                if self._on_action_start:
                    self._on_action_start(idx, description)

                logger.info(f"Executing action {idx + 1}/{len(actions)}: {description}")

                result = await self._execute_action(page, idx, action)
                action_results.append(result)

                # Notify action complete
                if self._on_action_complete:
                    self._on_action_complete(result)

                if result.status == ActionStatus.SUCCESS:
                    completed_count += 1
                elif result.status == ActionStatus.FAILED:
                    failed_index = idx
                    error_msg = result.error
                    if stop_on_error:
                        logger.error(f"Action {idx + 1} failed: {result.error}")
                        break

                # Wait after action if specified
                wait_after_raw = action.get("wait_after", 0)
                try:
                    wait_after = int(wait_after_raw) if wait_after_raw else 0
                except (ValueError, TypeError):
                    wait_after = 0
                if wait_after > 0:
                    await asyncio.sleep(wait_after / 1000)

        except Exception as e:
            logger.error(f"Replay execution error: {e}")
            error_msg = str(e)
        finally:
            self._is_running = False

        success = completed_count == len(actions) and failed_index is None

        return ReplayResult(
            success=success,
            total_actions=len(actions),
            completed_actions=completed_count,
            failed_action_index=failed_index,
            error=error_msg,
            action_results=action_results,
        )

    async def replay_with_progress(
        self,
        page: Page,
        actions: List[Dict[str, Any]],
        start_url: Optional[str] = None,
    ) -> AsyncGenerator[ActionResult, None]:
        """
        Execute actions and yield results as they complete.

        This is useful for streaming progress to the frontend.
        """
        self._is_running = True
        self._should_stop = False

        try:
            if start_url:
                await self._controller.visit_page(page, start_url)
                await page.wait_for_load_state("networkidle")

            for idx, action in enumerate(actions):
                # Check both internal flag and external callback
                if self._should_stop or (self._should_stop_callback and self._should_stop_callback()):
                    break

                result = await self._execute_action(page, idx, action)
                yield result

                if result.status == ActionStatus.FAILED:
                    break

                wait_after_raw = action.get("wait_after", 0)
                try:
                    wait_after = int(wait_after_raw) if wait_after_raw else 0
                except (ValueError, TypeError):
                    wait_after = 0
                if wait_after > 0:
                    await asyncio.sleep(wait_after / 1000)

        finally:
            self._is_running = False

    async def _execute_action(
        self,
        page: Page,
        index: int,
        action: Dict[str, Any],
    ) -> ActionResult:
        """Execute a single action and return the result."""
        action_type = action.get("action_type", "").lower()
        selector = action.get("selector", "")
        value = action.get("value", "")
        description = action.get("description", f"Action {index + 1}")

        try:
            if action_type == "goto":
                url = value or selector
                await self._controller.visit_page(page, url)
                await page.wait_for_load_state("networkidle")

            elif action_type == "click":
                await page.locator(selector).click()

            elif action_type == "fill":
                await page.locator(selector).fill(value)

            elif action_type == "type":
                await page.locator(selector).type(value)

            elif action_type == "press":
                await page.keyboard.press(value)

            elif action_type == "select":
                await page.locator(selector).select_option(value)

            elif action_type == "hover":
                await page.locator(selector).hover()

            elif action_type == "scroll":
                if value:
                    await page.evaluate(f"window.scrollBy(0, {value})")
                elif selector:
                    await page.locator(selector).scroll_into_view_if_needed()

            elif action_type == "wait":
                if selector:
                    await page.locator(selector).wait_for()
                else:
                    wait_time = int(value) if value else 1000
                    await asyncio.sleep(wait_time / 1000)

            elif action_type == "screenshot":
                # Screenshot is captured below regardless
                pass

            else:
                logger.warning(f"Unknown action type: {action_type}")
                return ActionResult(
                    action_index=index,
                    action_type=action_type,
                    description=description,
                    status=ActionStatus.SKIPPED,
                    error=f"Unknown action type: {action_type}",
                )

            # Capture screenshot after action
            screenshot = await page.screenshot()

            return ActionResult(
                action_index=index,
                action_type=action_type,
                description=description,
                status=ActionStatus.SUCCESS,
                screenshot=screenshot,
            )

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            # Try to capture screenshot even on failure
            screenshot = None
            try:
                screenshot = await page.screenshot()
            except Exception:
                pass

            return ActionResult(
                action_index=index,
                action_type=action_type,
                description=description,
                status=ActionStatus.FAILED,
                error=str(e),
                screenshot=screenshot,
            )

    def stop(self):
        """Request to stop the current replay."""
        self._should_stop = True

    @property
    def is_running(self) -> bool:
        """Check if a replay is currently running."""
        return self._is_running
