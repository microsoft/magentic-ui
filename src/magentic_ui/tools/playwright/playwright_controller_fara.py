import asyncio
import base64
import os
import logging
import functools
from typing import Any, Callable, Optional, Tuple, Union, TypeVar, Awaitable
from urllib.parse import urlsplit

from playwright._impl._errors import Error as PlaywrightError
from playwright._impl._errors import TimeoutError, TargetClosedError
from playwright.async_api import Download, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .utils.webpage_text_utils import WebpageTextUtilsPlaywright

# Adapted from Magentic-UI
# Some of the Code for clicking coordinates and keypresses adapted from https://github.com/openai/openai-cua-sample-app/blob/main/computers/base_playwright.py
# Copyright 2025 OpenAI - MIT License
CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _redact_url_for_log(url: str) -> str:
    """Strip query and fragment from a URL for safe logging.

    Query strings frequently carry tokens, session IDs, emails, or signed
    URL parameters. Keeping only scheme+host+path preserves enough context
    for diagnostics without leaking credentials into logs.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable url>"
    if not parts.scheme and not parts.netloc:
        # Not a real URL (e.g. "about:blank" or a relative fragment); keep as-is.
        return url
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def handle_target_closed(max_retries: int = 2, timeout_secs: int = 30):
    """
    Decorator to handle TargetClosedError and tunnel connection errors by attempting to recover the page.

    Args:
        max_retries: Maximum number of retry attempts
        timeout_secs: Timeout for page operations during recovery
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract the page object - assume it's the first argument after self
            logger = args[0].logger
            page = None
            if len(args) >= 2 and hasattr(
                args[1], "url"
            ):  # Check if second arg looks like a Page
                page = args[1]

            retries = 0
            last_error = None

            while retries <= max_retries:
                try:
                    return await func(*args, **kwargs)
                except (TargetClosedError, PlaywrightError) as e:
                    # Check if this is a tunnel connection error
                    is_tunnel_error = "net::ERR_TUNNEL_CONNECTION_FAILED" in str(e)
                    is_target_closed = isinstance(
                        e, TargetClosedError
                    ) or "Target page, context or browser has been closed" in str(e)

                    if not (is_tunnel_error or is_target_closed):
                        # Not an error we handle, re-raise
                        raise e

                    last_error = e
                    retries += 1

                    if retries > max_retries:
                        raise e

                    if page is None:
                        # Can't recover without page reference
                        raise e

                    error_type = (
                        "tunnel connection" if is_tunnel_error else "target closed"
                    )
                    logger.warning(
                        f"{error_type} error in {func.__name__}, attempting recovery (retry {retries}/{max_retries})"
                    )

                    try:
                        # Attempt to recover the page
                        await _recover_page(page, timeout_secs, logger)
                        # Small delay before retry
                        await asyncio.sleep(0.5)
                    except Exception as recovery_error:
                        logger.error(f"Page recovery failed: {recovery_error}")
                        # If recovery fails, raise the original error
                        raise e from recovery_error

            # This shouldn't be reached, but just in case
            raise last_error

        return wrapper

    return decorator


async def _recover_page(page: Page, timeout_secs: int = 30, logger=None) -> None:
    """
    Attempt to recover a closed page by reloading it.

    Args:
        page: The Playwright page object to recover
        timeout_secs: Timeout for recovery operations
    """
    logger = logger or logging.getLogger("playwright_controller")
    try:
        # First, try to check if the page is still responsive
        await page.evaluate("1", timeout=1000)
        # If we get here, the page is actually fine
        return
    except Exception:
        # Page is indeed problematic, attempt recovery
        pass

    try:
        # Stop any ongoing navigation
        await page.evaluate("window.stop()", timeout=2000)
    except Exception:
        # Ignore errors from window.stop()
        pass

    try:
        # Try to reload the page
        await page.reload(timeout=timeout_secs * 1000)
        await page.wait_for_load_state("load", timeout=timeout_secs * 1000)
        logger.info("playwright_controller._recover_page(): Page recovery successful")
    except Exception as e:
        logger.error(f"playwright_controller._recover_page(): Page reload failed: {e}")

        # Try alternative recovery: navigate to current URL
        try:
            current_url = page.url
            if current_url and current_url != "about:blank":
                await page.goto(current_url, timeout=timeout_secs * 1000)
                await page.wait_for_load_state("load", timeout=timeout_secs * 1000)
                logger.info(
                    "playwright_controller._recover_page(): Page recovery via goto successful"
                )
            else:
                raise Exception(
                    "playwright_controller._recover_page(): No valid URL to navigate to"
                )
        except Exception as goto_error:
            raise Exception(
                f"playwright_controller._recover_page(): All recovery methods failed. Reload error: {e}, Goto error: {goto_error}"
            )


# Enhanced version that can handle browser context recreation
def handle_target_closed_with_context(max_retries: int = 2, timeout_secs: int = 30):
    """
    Enhanced decorator that can also handle browser context recreation.
    Use this for critical operations where you have access to the browser context.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = args[0].logger
            page = None
            if len(args) >= 2 and hasattr(args[1], "url"):
                page = args[1]

            retries = 0
            last_error = None

            while retries <= max_retries:
                try:
                    return await func(*args, **kwargs)
                except (TargetClosedError, PlaywrightError) as e:
                    # Check if this is a tunnel connection error
                    is_tunnel_error = "net::ERR_TUNNEL_CONNECTION_FAILED" in str(e)
                    is_target_closed = isinstance(
                        e, TargetClosedError
                    ) or "Target page, context or browser has been closed" in str(e)

                    if not (is_tunnel_error or is_target_closed):
                        # Not an error we handle, re-raise
                        raise e

                    last_error = e
                    retries += 1

                    if retries > max_retries:
                        raise e

                    if page is None:
                        raise e

                    error_type = (
                        "tunnel connection" if is_tunnel_error else "target closed"
                    )
                    logger.warning(
                        f"playwright_controller.handle_target_closed_with_context(): {error_type} error in {func.__name__}, attempting enhanced recovery (retry {retries}/{max_retries})"
                    )

                    try:
                        # Check if the browser context is still alive
                        context = page.context
                        browser = context.browser

                        if browser and not browser.is_connected():
                            # Browser connection is lost - this is a more serious issue
                            logger.error(
                                "playwright_controller.handle_target_closed_with_context(): Browser connection lost - cannot recover automatically"
                            )
                            raise e

                        # Try basic recovery first
                        await _recover_page(page, timeout_secs)
                        await asyncio.sleep(0.5)

                    except Exception as recovery_error:
                        logger.error(
                            f"playwright_controller.handle_target_closed_with_context(): Enhanced page recovery failed: {recovery_error}"
                        )
                        raise e from recovery_error

            raise last_error

        return wrapper

    return decorator


class PlaywrightController:
    def __init__(
        self,
        animate_actions: bool = False,
        downloads_folder: Optional[str] = None,
        viewport_width: int = 1440,
        viewport_height: int = 900,
        _download_handler: Optional[Callable[[Download], None]] = None,
        to_resize_viewport: bool = True,
        single_tab_mode: bool = False,
        sleep_after_action: int = 10,
        timeout_load: int = 1,
        logger=None,
    ) -> None:
        """
        A controller for Playwright to interact with web pages.
        animate_actions: If True, actions will be animated.
        downloads_folder: The folder to save downloads to.
        viewport_width: The width of the viewport.
        viewport_height: The height of the viewport.
        _download_handler: A handler for downloads.
        to_resize_viewport: If True, the viewport will be resized.
        single_tab_mode (bool): If True, forces navigation to happen in the same tab rather than opening new tabs/windows.

        """
        self.animate_actions = animate_actions
        self.downloads_folder = downloads_folder
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self._download_handler = _download_handler
        self.to_resize_viewport = to_resize_viewport
        self.single_tab_mode = single_tab_mode
        self._sleep_after_action = sleep_after_action
        self._timeout_load = timeout_load
        self.logger = logger or logging.getLogger("playwright_controller")

        # Set up the download handler
        self.last_cursor_position: Tuple[float, float] = (0.0, 0.0)
        self._text_utils = WebpageTextUtilsPlaywright()

    async def sleep(self, page: Page, duration: Union[int, float]) -> None:
        await asyncio.sleep(duration)

    @handle_target_closed()
    async def on_new_page(self, page: Page) -> None:
        assert page is not None
        # bring page to front just in case
        await page.bring_to_front()
        page.on("download", self._download_handler)  # type: ignore
        if self.to_resize_viewport and self.viewport_width and self.viewport_height:
            await page.set_viewport_size(
                {"width": self.viewport_width, "height": self.viewport_height}
            )
        await self.sleep(page, 0.2)
        try:
            await page.wait_for_load_state(timeout=30000)
        except PlaywrightTimeoutError:
            self.logger.error("WARNING: Page load timeout, page might not be loaded")
            # stop page loading
            await page.evaluate("window.stop()")

    @handle_target_closed()
    async def _ensure_page_ready(self, page: Page) -> None:
        """Cheap pre-action check: confirm the page is loaded.

        Must be idempotent and side-effect free — runs before every click,
        type, screenshot, etc. Avoid bring_to_front()/sleep/listener-attach
        here: those belong in on_new_page() and would dismiss open dropdowns
        or accumulate listeners on every action.
        """
        assert page is not None
        try:
            # Already-loaded pages return immediately; short timeout so we
            # don't stall a click if a background request is hanging.
            await page.wait_for_load_state(timeout=2000)
        except PlaywrightTimeoutError:
            pass

    @handle_target_closed()
    async def get_screenshot(self, page: Page, path: str | None = None) -> bytes:
        """
        Capture a screenshot of the current page.

        Args:
            page (Page): The Playwright page object.
            path (str, optional): The file path to save the screenshot. If None, the screenshot will be returned as bytes. Default: None
        """
        await self._ensure_page_ready(page)
        try:
            screenshot = await page.screenshot(path=path, timeout=15000)
            return screenshot
        except Exception:
            await page.evaluate("window.stop()")
            # try again
            screenshot = await page.screenshot(path=path, timeout=15000)
            return screenshot

    @handle_target_closed()
    async def back(self, page: Page) -> None:
        await self._ensure_page_ready(page)
        try:
            await page.go_back(timeout=5000)
        except PlaywrightTimeoutError:
            self.logger.warning(
                "WARNING: Back navigation timed out; page history or navigation state may be inconsistent"
            )
            try:
                # Stop any in-flight navigation so subsequent actions are not
                # impacted by a page left mid-navigation after the timeout.
                await page.evaluate("window.stop()")
            except (PlaywrightError, TargetClosedError) as stop_error:
                self.logger.debug(
                    "Failed to stop page loading after back navigation timeout: %s",
                    stop_error,
                )

    @handle_target_closed()
    async def visit_page(self, page: Page, url: str) -> Tuple[bool, bool]:
        await self._ensure_page_ready(page)
        # Navigation always counts as a metadata-affecting event, even when
        # goto times out — by the time we return, the page state has changed
        # in some way the agent's prior fingerprint can no longer rely on.
        reset_prior_metadata_hash = True
        reset_last_download = False
        try:
            # Regular webpage. Wait only for `commit` (HTTP response received,
            # network is on the new URL) — not `load` or even `domcontentloaded`.
            # The page is allowed to keep loading; we just need the navigation
            # to commit so screenshots and clicks target the new URL. The
            # post-action settle delay (3s) handled by FaraQwen3Agent then
            # gives the DOM time to populate.
            #
            # `domcontentloaded` was tried but timed out frequently on Bing
            # under load (10s was hit even on simple search pages).
            # `commit` is the lowest level Playwright offers and is bounded
            # by network round-trip time, not page complexity.
            #
            # Use a generous timeout (20s) as a safety net for actually
            # unreachable URLs; this is hit only on real network failures.
            try:
                await page.goto(url, wait_until="commit", timeout=20000)
            except PlaywrightTimeoutError:
                # Navigation didn't commit within 20s — likely DNS failure,
                # connection refused, or the server is genuinely down.
                # Don't propagate: the agent loop will see whatever the
                # page currently shows and decide what to do next.
                self.logger.warning(
                    f"playwright_controller.visit_page(): goto timed out for "
                    f"{_redact_url_for_log(url)}; agent will see current page state"
                )
        except Exception as e_outer:
            # Downloaded file
            if self.downloads_folder and "net::ERR_ABORTED" in str(e_outer):
                async with page.expect_download() as download_info:
                    try:
                        await page.goto(url)
                    except Exception as e_inner:
                        if "net::ERR_ABORTED" in str(e_inner):
                            pass
                        else:
                            raise e_inner
                    download = await download_info.value
                    fname = os.path.join(
                        self.downloads_folder, download.suggested_filename
                    )
                    await download.save_as(fname)
                    message = f"<body style=\"margin: 20px;\"><h1>Successfully downloaded '{download.suggested_filename}' to local path:<br><br>{fname}</h1></body>"
                    await page.goto(
                        "data:text/html;base64,"
                        + base64.b64encode(message.encode("utf-8")).decode("utf-8")
                    )
                    reset_last_download = True
            else:
                raise e_outer
        return reset_prior_metadata_hash, reset_last_download

    @handle_target_closed()
    async def page_down(
        self, page: Page, amount: int = 400, full_page: bool = False
    ) -> None:
        await self._ensure_page_ready(page)
        if full_page:
            await page.mouse.wheel(0, self.viewport_height - 50)
        else:
            await page.mouse.wheel(0, amount)

    @handle_target_closed()
    async def page_up(
        self, page: Page, amount: int = 400, full_page: bool = False
    ) -> None:
        await self._ensure_page_ready(page)
        if full_page:
            await page.mouse.wheel(0, -self.viewport_height + 50)
        else:
            await page.mouse.wheel(0, -amount)

    async def gradual_cursor_animation(
        self, page: Page, start_x: float, start_y: float, end_x: float, end_y: float
    ) -> None:
        # animation helper
        # Create the red cursor if it doesn't exist
        await page.evaluate("""
            (function() {
                if (!document.getElementById('red-cursor')) {
                    let cursor = document.createElement('div');
                    cursor.id = 'red-cursor';
                    cursor.style.width = '10px';
                    cursor.style.height = '10px';
                    cursor.style.backgroundColor = 'red';
                    cursor.style.position = 'absolute';
                    cursor.style.borderRadius = '50%';
                    cursor.style.zIndex = '10000';
                    document.body.appendChild(cursor);
                }
            })();
        """)

        steps = 20
        for step in range(steps):
            x = start_x + (end_x - start_x) * (step / steps)
            y = start_y + (end_y - start_y) * (step / steps)
            # await page.mouse.move(x, y, steps=1)
            await page.evaluate(f"""
                (function() {{
                    let cursor = document.getElementById('red-cursor');
                    if (cursor) {{
                        cursor.style.left = '{x}px';
                        cursor.style.top = '{y}px';
                    }}
                }})();
            """)
            await asyncio.sleep(0.05)

        self.last_cursor_position = (end_x, end_y)
        await asyncio.sleep(1.0)

    @handle_target_closed()
    async def click_coords(self, page: Page, x: float, y: float) -> None:
        new_page: Page | None = None
        await self._ensure_page_ready(page)

        if self.animate_actions:
            # Move cursor to the box slowly
            start_x, start_y = self.last_cursor_position
            await self.gradual_cursor_animation(page, start_x, start_y, x, y)
            await asyncio.sleep(0.1)

            try:
                # Give it a chance to open a new page
                async with page.expect_event("popup", timeout=1000) as page_info:  # type: ignore
                    await page.mouse.click(x, y, delay=10)
                    new_page = await page_info.value  # type: ignore
                    assert isinstance(new_page, Page)
                    await self.on_new_page(new_page)
            except TimeoutError:
                pass
        else:
            try:
                # Give it a chance to open a new page
                async with page.expect_event("popup", timeout=1000) as page_info:  # type: ignore
                    await page.mouse.click(x, y, delay=10)
                    new_page = await page_info.value  # type: ignore
                    assert isinstance(new_page, Page)
                    await self.on_new_page(new_page)
            except TimeoutError:
                pass
        return new_page

    @handle_target_closed()
    async def hover_coords(self, page: Page, x: float, y: float) -> None:
        """
        Hovers the mouse over the specified coordinates.

        Args:
            page (Page): The Playwright page object.
            x (float): The x coordinate to hover over.
            y (float): The y coordinate to hover over.
        """
        await self._ensure_page_ready(page)

        if self.animate_actions:
            # Move cursor to the coordinates slowly
            start_x, start_y = self.last_cursor_position
            await self.gradual_cursor_animation(page, start_x, start_y, x, y)
            await asyncio.sleep(0.1)

        await page.mouse.move(x, y)

    async def _clear_field(self, page: Page) -> None:
        """Select all text in the focused field and delete it."""
        await page.keyboard.press("ControlOrMeta+A")
        await page.keyboard.press("Backspace")

    @handle_target_closed()
    async def fill_coords(
        self,
        page: Page,
        x: float,
        y: float,
        value: str,
        press_enter: bool = True,
        delete_existing_text: bool = False,
    ) -> Page | None:
        await self._ensure_page_ready(page)
        new_page: Page | None = None

        if self.animate_actions:
            start_x, start_y = self.last_cursor_position
            await self.gradual_cursor_animation(page, start_x, start_y, x, y)
            await asyncio.sleep(0.1)

        await page.mouse.click(x, y)
        await asyncio.sleep(0.05)  # Give the field time to focus

        if delete_existing_text:
            await self._clear_field(page)

        # Short strings (<100 chars) use 100ms delay per keystroke to avoid
        # dropping characters on fields with JS input masks (phone, credit card,
        # date). These masks have per-keystroke event handlers that need time to
        # reformat the value and reposition the cursor.
        # Long strings use 10ms since they are almost always plain text fields
        # with no input masks, and 100ms would be too slow.
        # See: https://github.com/microsoft/magentic-ui2.0/issues/279
        if len(value) < 100:
            delay_typing_speed = 100
        else:
            delay_typing_speed = 10

        # If a PlaywrightError occurs mid-typing (e.g., element detach,
        # navigation), clear the field before retrying to avoid corrupted input
        # from a partial first attempt followed by a full retry.
        try:
            await page.keyboard.type(value, delay=delay_typing_speed)
        except PlaywrightError:
            await self._clear_field(page)
            await page.keyboard.type(value, delay=delay_typing_speed)

        if press_enter:
            await page.keyboard.press("Enter")

        # Wait briefly for a popup that may have opened during typing or Enter.
        # Some websites open a new tab/popup on form submission (e.g., forms
        # with target="_blank"). The listener starts after typing so the timeout
        # window isn't consumed by keystroke delivery.
        try:
            new_page = await page.wait_for_event("popup", timeout=2000)
            assert isinstance(new_page, Page)
            await self.on_new_page(new_page)
        except (TimeoutError, asyncio.TimeoutError):
            pass

        return new_page

    async def keypress(self, page: Page, keys: list[str], key_mapping=None) -> None:
        """
        Press specified keys in sequence.

        Args:
            page (Page): The Playwright page object
            keys (List[str]): List of keys to press
            key_mapping: Optional mapping to override ``CUA_KEY_TO_PLAYWRIGHT_KEY``.
        """
        await self._ensure_page_ready(page)
        key_mapping = key_mapping or CUA_KEY_TO_PLAYWRIGHT_KEY
        mapped_keys = [key_mapping.get(key.lower(), key) for key in keys]
        pressed: list[str] = []
        try:
            for key in mapped_keys:
                await page.keyboard.down(key)
                pressed.append(key)
                if self.animate_actions:
                    await asyncio.sleep(0.05)
        except Exception as e:
            msg = str(e)
            if "Unknown key" in msg:
                bad = next(
                    (k for k in keys if key_mapping.get(k.lower(), k) not in pressed),
                    keys[-1],
                )
                raise ValueError(
                    f"Unknown key: {bad!r}. keypress only accepts single characters "
                    f"or named keys (Enter, Tab, ArrowDown, Control, ...). "
                    f"Use type() for text input."
                ) from None
            raise RuntimeError(
                f"I tried to keypress(keys={keys}), but I got an error: {e}"
            ) from None
        finally:
            for key in reversed(pressed):
                try:
                    await page.keyboard.up(key)
                    if self.animate_actions:
                        await asyncio.sleep(0.05)
                except Exception:
                    continue  # cleanup must not mask the primary failure

    @handle_target_closed()
    async def wait_for_load_state(
        self, page: Page, state: str = "load", timeout: Optional[int] = None
    ) -> None:
        """Wait for the page to reach a specific load state."""
        await page.wait_for_load_state(state, timeout=timeout)

    @handle_target_closed()
    async def get_page_url(self, page: Page) -> str:
        """Get the current page URL."""
        await self._ensure_page_ready(page)
        return page.url

    # ------------------------------------------------------------------
    # Extended actions for FaraQwen3NextAgent
    # ------------------------------------------------------------------

    @handle_target_closed()
    async def double_click_coords(self, page: Page, x: float, y: float) -> None:
        """Double-click at coordinates."""
        await self._ensure_page_ready(page)
        await page.mouse.dblclick(x, y)

    @handle_target_closed()
    async def right_click_coords(self, page: Page, x: float, y: float) -> None:
        """Right-click at coordinates."""
        await self._ensure_page_ready(page)
        await page.mouse.click(x, y, button="right")

    @handle_target_closed()
    async def triple_click_coords(self, page: Page, x: float, y: float) -> None:
        """Triple-click at coordinates (e.g. to select a line of text)."""
        await self._ensure_page_ready(page)
        await page.mouse.click(x, y, click_count=3)

    @handle_target_closed()
    async def left_click_drag(self, page: Page, end_x: float, end_y: float) -> None:
        """Drag from current cursor position to (end_x, end_y)."""
        await self._ensure_page_ready(page)
        await page.mouse.down()
        await page.mouse.move(end_x, end_y)
        await page.mouse.up()

    @handle_target_closed()
    async def hscroll(self, page: Page, pixels: int) -> None:
        """Horizontal scroll. Positive = right, negative = left."""
        await self._ensure_page_ready(page)
        await page.mouse.wheel(pixels, 0)

    async def get_page_markdown(self, page: Page, max_tokens: int = -1) -> str:
        """Extract page content as markdown. Delegates to WebpageTextUtilsPlaywright."""
        return await self._text_utils.get_page_markdown(page, max_tokens=max_tokens)
