import asyncio
import base64
import os
import random
import json
import logging
import hashlib
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Tuple,
    Union,
    cast,
    List,
    Literal,
)
import warnings
from playwright.async_api import Locator
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Download, Page, BrowserContext
from .utils.animation_utils import AnimationUtilsPlaywright
from .utils.webpage_text_utils import WebpageTextUtilsPlaywright
from ..url_status_manager import UrlStatusManager

from .types import (
    InteractiveRegion,
    VisualViewport,
    interactiveregion_from_dict,
    visualviewport_from_dict,
)

warnings.filterwarnings(action="ignore", module="markitdown")

logger = logging.getLogger(__name__)


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


class PlaywrightController:
    """
    A helper class to allow Playwright to interact with web pages to perform actions such as clicking, filling, and scrolling.

    Args:
        downloads_folder (str, optional): The folder to save downloads to. If None, downloads are not saved. Default: None
        animate_actions (bool, optional): Whether to animate the actions (create fake cursor to click). Default: False
        viewport_width (int, optional): The width of the viewport. Default: 1440
        viewport_height (int, optional): The height of the viewport. Default: 1440
        _download_handler (callable, None], optional): A function to handle downloads.
        to_resize_viewport (bool, optional): Whether to resize the viewport. Default: True
        timeout_load (int | float, optional): Amount of time (in secs) to wait before timeout on actions. Default: 1
        sleep_after_action (int | float, optional): Amount of time (in secs) to sleep after performing action. Default: 1
        single_tab_mode (bool, optional): If True, forces navigation to happen in the same tab rather than opening new tabs/windows. Default: False
        url_status_manager (UrlStatusManager, optional): A list of websites to allow or deny. If None, all websites are allowed.
        url_validation_callback (callable, optional): A callback function to validate URLs. It should return a tuple of (str, bool) where the str is a failure string and bool indicates if the URL is allowed.
    """

    def __init__(
        self,
        downloads_folder: str | None = None,
        animate_actions: bool = False,
        viewport_width: int = 1440,
        viewport_height: int = 1440,
        _download_handler: Optional[Callable[[Download], None]] = None,
        to_resize_viewport: bool = True,
        timeout_load: Union[int, float] = 1,
        sleep_after_action: Union[int, float] = 0.1,
        single_tab_mode: bool = False,
        url_status_manager: UrlStatusManager | None = None,
        url_validation_callback: Optional[
            Callable[[str], Awaitable[Tuple[str, bool]]]
        ] = None,
    ) -> None:
        """
        Initialize the PlaywrightController.
        """
        assert isinstance(animate_actions, bool)
        assert isinstance(viewport_width, int)
        assert isinstance(viewport_height, int)
        assert viewport_height > 0
        assert viewport_width > 0
        assert timeout_load > 0

        self.animate_actions = animate_actions
        self.downloads_folder = downloads_folder
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self._download_handler = _download_handler
        self.to_resize_viewport = to_resize_viewport
        self._timeout_load = timeout_load
        self._sleep_after_action = sleep_after_action
        self.single_tab_mode = single_tab_mode
        self._url_status_manager = url_status_manager
        self._url_validation_callback = url_validation_callback
        self._page_script: str = ""
        self._markdown_converter: Optional[Any] | None = None

        # Create animation utils instance
        self._animation = AnimationUtilsPlaywright()
        # Use animation utils for cursor position tracking
        self.last_cursor_position = self._animation.last_cursor_position

        # Read page_script
        with open(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "page_script.js"),
            "rt",
            encoding="utf-8",
        ) as fh:
            self._page_script = fh.read()

        # Initialize WebpageTextUtils
        self._text_utils = WebpageTextUtilsPlaywright()

    async def on_new_page(self, page: Page) -> None:
        """
        Handle actions to perform on a new page.

        Args:
            page (Page): The Playwright page object.
        """
        assert page is not None

        awaiting_approval = False
        tentative_url = page.url
        tentative_url_approved = True
        # If the page is not whitelisted, block the site before asking if the user wants to allow it
        if self._url_status_manager and not self._url_status_manager.is_url_allowed(
            tentative_url
        ):
            await page.route("**/*", lambda route: route.abort("blockedbyclient"))
            try:
                # This will raise an exception, but we don't care about it
                await page.reload()
            except PlaywrightError:
                pass
            await page.unroute("**/*")

            if self._url_validation_callback is not None:
                awaiting_approval = True
                _, tentative_url_approved = await self._url_validation_callback(
                    tentative_url
                )

        # Wait for page load
        try:
            await page.wait_for_load_state(timeout=15000)
        except PlaywrightTimeoutError:
            logger.warning("Page load timeout, page might not be loaded")
            # refresh
            await page.reload()
            try:
                await page.wait_for_load_state(timeout=15000)
            except Exception:
                # stop page loading
                await page.evaluate("window.stop()")
        except Exception:
            pass

        if awaiting_approval and tentative_url_approved:
            # Visit the page if permission has been given
            await self.visit_page(page, tentative_url)

        page.on("download", self._download_handler)  # type: ignore

        # check if there is a need to resize the viewport
        page_viewport_size = page.viewport_size
        if self.to_resize_viewport and self.viewport_width and self.viewport_height:
            if (
                page_viewport_size is None
                or page_viewport_size["width"] != self.viewport_width
                or page_viewport_size["height"] != self.viewport_height
            ):
                await page.set_viewport_size(
                    {"width": self.viewport_width, "height": self.viewport_height}
                )
        await page.add_init_script(
            path=os.path.join(
                os.path.abspath(os.path.dirname(__file__)), "page_script.js"
            )
        )

    async def _ensure_page_ready(self, page: Page) -> None:
        """
        Ensure the page is properly configured before performing any action.

        Args:
            page (Page): The Playwright page object.
        """
        assert page is not None
        # bring the page to front
        await page.bring_to_front()
        await self.on_new_page(page)

    async def get_current_url_title(self, page: Page) -> Tuple[str, str]:
        """
        Get the current URL and title of the page.

        Args:
            page (Page): The Playwright page object.

        Returns:
            A tuple containing:
                - str: The current URL of the page.
                - str: The title of the page.
        """
        try:
            url = page.url
            title = await page.title()
            return url, title
        except Exception:
            logger.warning("Error getting current URL and title, returning unknown")
            return "Unknown", "Unknown"

    async def get_screenshot(self, page: Page, path: str | None = None) -> bytes:
        """
        Capture a screenshot of the current page.

        Args:
            page (Page): The Playwright page object.
            path (str, optional): The file path to save the screenshot. If None, the screenshot will be returned as bytes. Default: None
        """
        try:
            screenshot = await page.screenshot(path=path, timeout=7000)
            return screenshot
        except Exception:
            logger.warning(
                "Screenshot failed, page might not be loaded, stopping page and taking screenshot again"
            )
            # refresh the page
            await page.reload()
            await self._ensure_page_ready(page)
            # try again
            screenshot = await page.screenshot(path=path, timeout=10000)
            return screenshot

    async def sleep(self, page: Page, duration: Union[int, float]) -> None:
        """
        Pause the execution for a specified duration.

        Args:
            page (Page): The Playwright page object.
            duration (int | float): The duration to sleep in seconds.
        """
        await self._ensure_page_ready(page)
        await page.wait_for_timeout(duration * 1000)

    async def get_interactive_rects(self, page: Page) -> Dict[str, InteractiveRegion]:
        """
        Retrieve interactive regions from the web page.

        Args:
            page (Page): The Playwright page object.

        Returns:
            Dict[str, InteractiveRegion]: A dictionary of interactive regions.
        """
        await self._ensure_page_ready(page)
        # Read the regions from the DOM
        try:
            await page.evaluate(self._page_script)
        except Exception:
            pass
        result = cast(
            Dict[str, Dict[str, Any]],
            await page.evaluate("WebSurfer.getInteractiveRects();"),
        )

        # Convert the results into appropriate types
        assert isinstance(result, dict)
        typed_results: Dict[str, InteractiveRegion] = {}
        for k in result:
            assert isinstance(k, str)
            typed_results[k] = interactiveregion_from_dict(result[k])

        return typed_results

    async def get_visual_viewport(self, page: Page) -> VisualViewport:
        """
        Retrieve the visual viewport of the web page.

        Args:
            page (Page): The Playwright page object.

        Returns:
            VisualViewport: The visual viewport of the page.
        """
        await self._ensure_page_ready(page)
        try:
            await page.evaluate(self._page_script)
        except Exception:
            pass
        return visualviewport_from_dict(
            await page.evaluate("WebSurfer.getVisualViewport();")
        )

    async def get_focused_rect_id(self, page: Page) -> str:
        """
        Retrieve the ID of the currently focused element.

        Args:
            page (Page): The Playwright page object.

        Returns:
            str: The ID of the focused element.
        """
        await self._ensure_page_ready(page)
        try:
            await page.evaluate(self._page_script)
        except Exception:
            pass
        result = await page.evaluate("WebSurfer.getFocusedElementId();")
        return str(result)

    async def get_page_metadata(self, page: Page) -> Dict[str, Any]:
        """
        Retrieve metadata from the web page.

        Args:
            page (Page): The Playwright page object.

        Returns:
            Dict[str, Any]: A dictionary of page metadata.
        """
        await self._ensure_page_ready(page)
        try:
            await page.evaluate(self._page_script)
        except Exception:
            pass
        result = await page.evaluate("WebSurfer.getPageMetadata();")
        assert isinstance(result, dict)
        return cast(Dict[str, Any], result)

    async def go_back(self, page: Page) -> bool:
        """
        Navigate back to the previous page.

        Args:
            page (Page): The Playwright page object.

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        await self._ensure_page_ready(page)
        response = await page.go_back(
            wait_until="load", timeout=self._timeout_load * 1000
        )
        if response is None:
            return False
        else:
            return True

    async def go_forward(self, page: Page) -> bool:
        """
        Navigate forward to the next page.

        Args:
            page (Page): The Playwright page object.

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        await self._ensure_page_ready(page)
        response = await page.go_forward(
            wait_until="load", timeout=self._timeout_load * 1000
        )
        if response is None:
            return False
        else:
            return True

    async def visit_page(self, page: Page, url: str) -> Tuple[bool, bool]:
        """
        Visit a specified URL.

        Args:
            page (Page): The Playwright page object.
            url (str): The URL to visit.

        Returns:
            A tuple containing:
                - bool: Whether to reset prior metadata hash.
                - bool: Whether to reset the last download.
        """
        await self._ensure_page_ready(page)
        reset_prior_metadata_hash = False
        reset_last_download = False

        download = None
        download_future: asyncio.Task[Download] | None = None

        # If downloads are enabled, start listening for a download event before navigation.
        if self.downloads_folder:
            try:
                # Create a timeout for the download listener - use a longer timeout
                download_future = asyncio.create_task(
                    page.wait_for_event(  # type: ignore
                        "download", timeout=self._timeout_load * 5000
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to set up download listener: {e}")
                download_future = None

        try:
            # Attempt normal navigation.
            await page.goto(url)
            await page.wait_for_load_state("load", timeout=self._timeout_load * 1000)
            await asyncio.sleep(1)
            reset_prior_metadata_hash = True

        except Exception as e:
            # If a navigation error occurs and it's likely due to a download,
            # use the already waiting download event.
            if self.downloads_folder and "net::ERR_ABORTED" in str(e):
                if download_future:
                    try:
                        # Wait for download with a reasonable timeout
                        download = await asyncio.wait_for(
                            download_future, timeout=self._timeout_load * 1000
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Download timeout exceeded, continuing without download"
                        )
                    except Exception as download_error:
                        logger.warning(f"Download error: {download_error}")
            else:
                raise
        finally:
            # Clean up the download future if it exists and hasn't completed
            if download_future and not download_future.done():
                download_future.cancel()

        # Process any download that was detected
        if download:
            assert self.downloads_folder is not None
            fname = os.path.join(self.downloads_folder, download.suggested_filename)
            await download.save_as(fname)
            message = (
                f"<body style='margin: 20px;'>"
                f"<h1>Successfully downloaded '{download.suggested_filename}' to local path:<br><br>{fname}</h1>"
                f"</body>"
            )
            data_uri = "data:text/html;base64," + base64.b64encode(
                message.encode("utf-8")
            ).decode("utf-8")
            await page.goto(data_uri)
            reset_last_download = True

        if self._sleep_after_action > 0:
            await page.wait_for_timeout(self._sleep_after_action * 1000)

        return reset_prior_metadata_hash, reset_last_download

    async def refresh_page(self, page: Page) -> None:
        """
        Refresh the current page.

        Args:
            page (Page): The Playwright page object.
        """
        await self._ensure_page_ready(page)
        await page.reload()
        await page.wait_for_load_state("load", timeout=self._timeout_load * 1000)

    async def page_down(self, page: Page) -> None:
        """
        Scroll the page down by one viewport height minus 50 pixels.
        Updates cursor position if animations are enabled.
        When animations are enabled, scrolls smoothly instead of jumping.

        Args:
            page (Page): The Playwright page object.
        """
        await self._ensure_page_ready(page)
        scroll_amount = self.viewport_height - 50

        if self.animate_actions:
            # Smooth scrolling in smaller increments
            steps = 5  # Reduced from 10 for faster animation
            step_amount = scroll_amount / steps
            for _ in range(steps):
                await page.evaluate(f"window.scrollBy(0, {step_amount});")
                await asyncio.sleep(0.02)  # Reduced from 0.05 for faster animation

            # Move cursor with the scroll using gradual animation
            x, y = self.last_cursor_position
            new_y = max(0, min(y - scroll_amount, self.viewport_height))
            await self._animation.gradual_cursor_animation(page, x, y, x, new_y)
        else:
            # Regular instant scroll
            await page.evaluate(f"window.scrollBy(0, {scroll_amount});")

    async def page_up(self, page: Page) -> None:
        """
        Scroll the page up by one viewport height minus 50 pixels.
        Updates cursor position if animations are enabled.
        When animations are enabled, scrolls smoothly instead of jumping.

        Args:
            page (Page): The Playwright page object.
        """
        await self._ensure_page_ready(page)
        scroll_amount = self.viewport_height - 50

        if self.animate_actions:
            # Smooth scrolling in smaller increments
            steps = 5  # Reduced from 10 for faster animation
            step_amount = scroll_amount / steps
            for _ in range(steps):
                await page.evaluate(f"window.scrollBy(0, -{step_amount});")
                await asyncio.sleep(0.02)  # Reduced from 0.05 for faster animation

            # Move cursor with the scroll using gradual animation
            x, y = self.last_cursor_position
            new_y = max(0, min(y + scroll_amount, self.viewport_height))
            await self._animation.gradual_cursor_animation(page, x, y, x, new_y)
        else:
            # Regular instant scroll
            await page.evaluate(f"window.scrollBy(0, -{scroll_amount});")

    async def scroll_mousewheel(
        self, page: Page, direction: str, pixels: int = 400
    ) -> None:
        """
        Scroll the page using mouse wheel for a specific number of pixels.
        Updates cursor position if animations are enabled.

        Args:
            page (Page): The Playwright page object.
            direction (str): Direction to scroll ("up" or "down").
            pixels (int, optional): Number of pixels to scroll. Default: 400.
        """
        await self._ensure_page_ready(page)

        # Determine scroll direction (negative for up, positive for down)
        scroll_amount = pixels if direction.lower() == "down" else -pixels

        if self.animate_actions:
            # Smooth scrolling in smaller increments
            steps = 4
            step_amount = scroll_amount / steps
            for _ in range(steps):
                await page.evaluate(f"window.scrollBy(0, {step_amount});")
                await asyncio.sleep(0.015)

            # Move cursor with the scroll using gradual animation
            x, y = self.last_cursor_position
            # Calculate new cursor position relative to scroll direction
            cursor_offset = min(pixels / 3, 100)  # Limit cursor movement
            new_y = (
                y - cursor_offset if direction.lower() == "down" else y + cursor_offset
            )
            new_y = max(0, min(new_y, self.viewport_height))
            await self._animation.gradual_cursor_animation(page, x, y, x, new_y)
        else:
            # Regular instant scroll
            await page.evaluate(f"window.scrollBy(0, {scroll_amount});")

        if self._sleep_after_action > 0:
            await page.wait_for_timeout(self._sleep_after_action * 1000)

    async def click_id(
        self,
        context: BrowserContext,
        page: Page,
        identifier: str,
        hold: float = 0.0,
        button: Literal["left", "right"] = "left",
    ) -> Optional[Page]:
        """
        Click an element with the given identifier. Handles regular clicks, right clicks, holding the mouse button, new page creation, and file downloads.

        Args:
            context (BrowserContext): The Playwright browser context.
            page (Page): The Playwright page object.
            identifier (str): The element identifier.
            hold (float, optional): Seconds to hold the mouse button down before releasing. Default: 0.0
            button (Literal["left", "right"], optional): Mouse button to use. Default: "left"

        Returns:
            Optional[Page]: The new page object if a popup was created, None otherwise.

        Raises:
            ValueError: If the element is not visible on the page.
            TimeoutError: If the element does not appear within the timeout period.
        """
        await self._ensure_page_ready(page)

        new_page: Optional[Page] = None
        selector = f"[__elementId='{identifier}']"
        try:
            # Wait for the element to be visible and scroll it into view
            await page.wait_for_selector(
                selector, state="visible", timeout=self._timeout_load * 1000
            )
            target = page.locator(selector)
            await target.scroll_into_view_if_needed()
        except PlaywrightTimeoutError:
            raise ValueError(
                f"Element with identifier {identifier} not found or not visible"
            )

        # Retrieve bounding box to determine the center for clicking
        box = await target.bounding_box()
        if not box:
            raise ValueError(
                f"Element with identifier {identifier} is not visible on the page."
            )
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2

        # In single tab mode, override target attributes to avoid opening a new tab
        if self.single_tab_mode:
            await target.evaluate("""
                el => {
                    // Remove target attribute from clicked element and all _blank links/forms
                    el.removeAttribute('target');
                    document.querySelectorAll('a[target=_blank], form[target=_blank]')
                        .forEach(e => e.removeAttribute('target'));
                }
            """)

        download = None
        download_future: asyncio.Task[Download] | None = None

        # Start listening for a download event if downloads are enabled
        if self.downloads_folder:
            try:
                download_future = asyncio.create_task(
                    page.wait_for_event(  # type: ignore
                        "download", timeout=self._timeout_load * 2000
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to set up download listener: {e}")
                download_future = None

        async def perform_click() -> Optional[Page]:
            nonlocal download
            try:
                if self.single_tab_mode:
                    await page.mouse.move(center_x, center_y, steps=1)
                    if hold == 0.0 and button == "left":
                        await page.mouse.click(center_x, center_y)
                    else:
                        await page.mouse.down(button=button)
                        if hold > 0:
                            await asyncio.sleep(hold)
                        await page.mouse.up(button=button)
                    return None
                else:
                    # Create a task to wait for a new page event
                    new_page_promise: asyncio.Task[Page] = asyncio.create_task(
                        context.wait_for_event(  # type: ignore
                            "page", timeout=self._timeout_load * 1000
                        )
                    )

                    # Perform the click
                    await page.mouse.move(center_x, center_y, steps=1)
                    if hold == 0.0 and button == "left":
                        await page.mouse.click(center_x, center_y, delay=10)
                    else:
                        await page.mouse.down(button=button)
                        if hold > 0:
                            await asyncio.sleep(hold)
                        await page.mouse.up(button=button)

                    try:
                        # Wait for the new page to open
                        new_page = await new_page_promise
                        await self._ensure_page_ready(new_page)
                        return new_page
                    except PlaywrightTimeoutError:
                        # No new page opened within timeout
                        return None
            except Exception:
                raise

        # Optionally animate the click
        if self.animate_actions:
            await self.add_cursor_box(page, identifier)
            start_x, start_y = self.last_cursor_position
            await self.gradual_cursor_animation(
                page, start_x, start_y, center_x, center_y
            )

        new_page = await perform_click()

        # Handle any download that occurred
        if download_future:
            try:
                if not download:
                    # Use asyncio.wait_for with a reasonable timeout
                    try:
                        download = await asyncio.wait_for(
                            download_future, timeout=self._timeout_load * 1000
                        )
                    except asyncio.TimeoutError:
                        # No download occurred within the timeout period
                        logger.debug("No download detected within timeout period")
                        pass

                if download:
                    logger.info(
                        f"Downloading {download.suggested_filename} to {self.downloads_folder}"
                    )
                    assert self.downloads_folder is not None
                    fname = os.path.join(
                        self.downloads_folder, download.suggested_filename
                    )
                    await download.save_as(fname)
            except Exception as e:
                logger.debug(f"Error handling download: {e}")
            finally:
                if not download_future.done():
                    download_future.cancel()

        if self.animate_actions:
            await self.remove_cursor_box(page, identifier)

        if self._sleep_after_action > 0:
            await page.wait_for_timeout(self._sleep_after_action * 1000)

        return new_page

    async def hover_id(self, page: Page, identifier: str) -> None:
        """
        Hover the mouse over the element with the given identifier.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier.
        """
        await self._ensure_page_ready(page)
        target = page.locator(f"[__elementId='{identifier}']")

        # See if it exists
        try:
            await target.wait_for(timeout=5000)
        except PlaywrightTimeoutError:
            raise ValueError("No such element.") from None

        # Hover over it
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)

        box = cast(Dict[str, Union[int, float]], await target.bounding_box())
        try:
            if self.animate_actions:
                await self.add_cursor_box(page, identifier)
                # Move cursor to the box slowly
                start_x, start_y = self.last_cursor_position
                end_x, end_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                await self.gradual_cursor_animation(
                    page, start_x, start_y, end_x, end_y
                )
                await asyncio.sleep(0.1)
                await page.mouse.move(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                )

                await self.remove_cursor_box(page, identifier)
            else:
                await page.mouse.move(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                )
        except Exception:
            if self.animate_actions:
                await self.remove_cursor_box(page, identifier)
            await target.hover()

    async def fill_id(
        self,
        page: Page,
        identifier: str,
        value: str,
        press_enter: bool = True,
        delete_existing_text: bool = False,
    ) -> None:
        """
        Fill the element with the given identifier with the specified value.
        Works with text inputs, textareas, and comboboxes.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier.
            value (str): The value to fill.
            press_enter (bool, optional): Whether to press enter after filling. Default: True
            delete_existing_text (bool, optional): Whether to delete existing text before filling. Default: False
        """
        await self._ensure_page_ready(page)
        await page.wait_for_selector(f"[__elementId='{identifier}']", state="visible")
        target = page.locator(f"[__elementId='{identifier}']")
        await target.scroll_into_view_if_needed()

        # See if it exists
        try:
            await target.wait_for(timeout=5000)
        except PlaywrightTimeoutError:
            raise ValueError("No such element.") from None

        # Fill it
        box = cast(Dict[str, Union[int, float]], await target.bounding_box())

        if self.single_tab_mode:
            # Remove target attributes to prevent new tabs
            await target.evaluate("""
                el => el.removeAttribute('target')
                // Remove 'target' on all <a> tags
                for (const a of document.querySelectorAll('a[target=_blank]')) {
                    a.removeAttribute('target');
                }
                // Remove 'target' on all <form> tags
                for (const frm of document.querySelectorAll('form[target=_blank]')) {
                    frm.removeAttribute('target');
                }
            """)
        try:
            end_x, end_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            if self.animate_actions:
                await self.add_cursor_box(page, identifier)
                # Move cursor to the box slowly
                start_x, start_y = self.last_cursor_position
                await self.gradual_cursor_animation(
                    page, start_x, start_y, end_x, end_y
                )
                await asyncio.sleep(0.1)

            # Focus on the element
            await page.mouse.click(end_x, end_y)

            if delete_existing_text:
                await page.keyboard.press("ControlOrMeta+A")
                await page.keyboard.press("Backspace")

            if self.animate_actions:
                # Type slower for short text, faster for long text
                delay_typing_speed = (
                    20 + 30 * random.random() if len(value) < 100 else 5
                )
                try:
                    await page.keyboard.type(value, delay=delay_typing_speed)
                except PlaywrightError:
                    await target.fill(value)

            else:
                try:
                    await page.keyboard.type(value)
                except PlaywrightError:
                    await target.fill(value)

            if press_enter:
                # if it's a combobox, wait a bit before pressing enter to allow suggestions to appear
                await page.keyboard.press("Enter")

        finally:
            if self.animate_actions:
                await self.remove_cursor_box(page, identifier)

    async def scroll_id(self, page: Page, identifier: str, direction: str) -> None:
        """
        Scroll the element with the given identifier in the specified direction.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier.
            direction (str): The direction to scroll ("up" or "down").
        """
        await self._ensure_page_ready(page)
        await page.evaluate(
            f"""
        (function() {{
            let elm = document.querySelector("[__elementId='{identifier}']");
            if (elm) {{
                if ("{direction}" == "up") {{
                    elm.scrollTop = Math.max(0, elm.scrollTop - elm.clientHeight);
                }}
                else {{
                    elm.scrollTop = Math.min(elm.scrollHeight - elm.clientHeight, elm.scrollTop + elm.clientHeight);
                }}
            }}
        }})();
    """
        )

    async def select_option(
        self, context: BrowserContext, page: Page, identifier: str
    ) -> Optional[Page]:
        """
        Select an option element with the given identifier. If the element has a visible size,
        it will be clicked normally. Otherwise, it will be selected programmatically.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier of the option to select.

        Returns:
            Optional[Page]: The Playwright page object of the newly focused tab.
        """
        await self._ensure_page_ready(page)
        new_page: Optional[Page] = None
        try:
            # Wait for element to be present
            await page.wait_for_selector(
                f"[__elementId='{identifier}']", state="attached"
            )

            try:
                # First try normal click if element is visible
                target = page.locator(f"[__elementId='{identifier}']").first
                # Get the bounding box to check element size
                box = await target.bounding_box()

                if box and box["width"] > 0 and box["height"] > 0:
                    # Element has visible size - use normal click
                    return await self.click_id(context, page, identifier)

            except PlaywrightError as e:
                if "strict mode violation" in str(e):
                    # If multiple elements found, try clicking the first visible one
                    elements: List[Locator] = await page.locator(
                        f"[__elementId='{identifier}']"
                    ).all()
                    for element in elements:
                        try:
                            if await element.is_visible():
                                await element.click()
                                return new_page
                        except PlaywrightError:
                            continue

            # If click didn't work, try programmatic selection
            # First check if it's a standard <option> element
            option_element = await page.evaluate(
                """
                (identifier) => {
                    const elements = document.querySelectorAll(`[__elementId='${identifier}']`);
                    for (const el of elements) {
                        if (el.tagName.toLowerCase() === 'option') {
                            return true;
                        }
                    }
                    return false;
                }
                """,
                identifier,
            )

            if option_element:
                # Handle standard <select> dropdown
                await page.evaluate(
                    """
                    (identifier) => {
                        const option = Array.from(document.querySelectorAll(`[__elementId='${identifier}']`))
                            .find(el => el.tagName.toLowerCase() === 'option');
                        if (!option) throw new Error('Option not found');
                        const select = option.closest('select');
                        if (select) {
                            option.selected = true;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            select.blur();
                        }
                    }
                    """,
                    identifier,
                )
            else:
                # Handle custom dropdown/combobox options
                await page.evaluate(
                    """
                    (identifier) => {
                        const element = document.querySelector(`[__elementId='${identifier}']`);
                        if (!element) throw new Error('Element not found');

                        // Dispatch multiple events to ensure the selection is registered
                        const events = ['mousedown', 'mouseup', 'click', 'change'];
                        events.forEach(eventType => {
                            element.dispatchEvent(new Event(eventType, { bubbles: true }));
                        });

                        // If element has aria-selected, set it
                        if (element.hasAttribute('aria-selected')) {
                            element.setAttribute('aria-selected', 'true');
                        }

                        // If element has a data-value, try to set it on the parent
                        const value = element.getAttribute('data-value');
                        if (value) {
                            const parent = element.closest('[role="listbox"], [role="combobox"]');
                            if (parent) {
                                parent.setAttribute('data-value', value);
                            }
                        }
                    }
                    """,
                    identifier,
                )

            # Optional sleep/pause after the action
            if self._sleep_after_action > 0:
                await page.wait_for_timeout(self._sleep_after_action * 1000)

        except PlaywrightTimeoutError:
            raise ValueError(
                f"No option found with identifier '{identifier}' within "
                f"{self._timeout_load} seconds."
            ) from None
        return new_page

    async def get_tabs_information(
        self, context: BrowserContext, current_page: Page
    ) -> List[Dict[str, Any]]:
        """
        Get information about all tabs in the browser context.

        Args:
            context (BrowserContext): The Playwright browser context.
            current_page (Page): The currently controlled page.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing information about each tab.
            Each dictionary contains:
                - title (str): The tab's title
                - url (str): The tab's URL
                - index (int): The tab's position index
                - is_active (bool): Whether this tab is currently visible in the browser
                - is_controlled (bool): Whether this tab is currently controlled by WebSurfer
        """
        assert context is not None
        tabs = context.pages
        tabs_info: List[Dict[str, Any]] = []

        # Get the currently active tab
        active_tab: Optional[Page] = None
        for tab in tabs:
            if await tab.evaluate("document.visibilityState") == "visible":
                active_tab = tab
                break

        for idx, tab in enumerate(tabs):
            tabs_info.append(
                {
                    "index": idx,
                    "title": await tab.title(),
                    "url": tab.url,
                    "is_active": tab == active_tab,
                    "is_controlled": tab
                    == current_page,  # Compare with the passed current page
                }
            )
        return tabs_info

    async def switch_tab(self, context: BrowserContext, tab_id: int) -> Page:
        """
        Switch to a specific tab in the browser context.

        Args:
            context (BrowserContext): The Playwright browser context.
            tab_id (int): The index of the tab to switch to.

        Returns:
            Page: The Playwright page object of the newly focused tab.

        Raises:
            ValueError: If the tab_id is out of range.
        """
        assert context is not None
        tabs = context.pages
        try:
            tab = tabs[tab_id]
            await self._ensure_page_ready(tab)
            # Bring the tab to front
            await tab.bring_to_front()
            return tab
        except IndexError:
            raise ValueError(f"Tab index {tab_id} is out of range.")

    async def close_tab(self, context: BrowserContext, tab_id: int) -> Page:
        """
        Close a specific tab in the browser context and switch to an adjacent tab.

        Args:
            context (BrowserContext): The Playwright browser context.
            tab_id (int): The index of the tab to close.

        Returns:
            Page: The Playwright page object of the newly focused tab.

        Raises:
            ValueError: If attempting to close the last tab or if tab_id is out of range.
        """
        assert context is not None
        tabs = context.pages
        if len(tabs) == 1:
            raise ValueError("Cannot close the last tab.")
        if tab_id >= len(tabs):
            raise ValueError(f"Tab index {tab_id} is out of range.")

        # Determine which tab to switch to.
        # If closing the first tab, choose the tab to the right.
        # Otherwise, choose the tab to the left.
        if tab_id == 0:
            new_tab = tabs[1]
        else:
            new_tab = tabs[tab_id - 1]

        # Close the specified tab
        await tabs[tab_id].close()

        # Bring the chosen tab to the front
        await new_tab.bring_to_front()
        return new_tab

    async def create_new_tab(self, context: BrowserContext, url: str) -> Page:
        """
        Add a new tab to the browser context and optionally navigate to a URL.

        Args:
            context (BrowserContext): The Playwright browser context.
            url (str): The URL to navigate to in the new tab.

        Returns:
            Page: The Playwright page object of the newly created tab.
        """
        assert context is not None
        new_page: Page = await context.new_page()
        await self._ensure_page_ready(new_page)
        # bring the page to the foreground
        await new_page.bring_to_front()
        try:
            await self.visit_page(new_page, url)
        except Exception:
            # If URL navigation fails, the tab will still be created
            pass
        return new_page

    async def double_click_coords(self, page: Page, x: int, y: int) -> None:
        """
        Double click at specified coordinates.

        Args:
            page (Page): The Playwright page object
            x (int): X coordinate
            y (int): Y coordinate
        """
        await self._ensure_page_ready(page)
        try:
            if self.animate_actions:
                start_x, start_y = self.last_cursor_position
                await self.gradual_cursor_animation(page, start_x, start_y, x, y)
            await page.mouse.dblclick(x, y)
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def scroll_coords(
        self, page: Page, x: int, y: int, scroll_x: int, scroll_y: int
    ) -> None:
        """
        Scroll the page from given coordinates.

        Args:
            page (Page): The Playwright page object
            x (int): Starting X coordinate
            y (int): Starting Y coordinate
            scroll_x (int): Horizontal scroll amount
            scroll_y (int): Vertical scroll amount
        """
        await self._ensure_page_ready(page)
        try:
            if self.animate_actions:
                start_x, start_y = self.last_cursor_position
                await self.gradual_cursor_animation(page, start_x, start_y, x, y)
            await page.mouse.move(x, y)
            await page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y});")
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def type_direct(self, page: Page, text: str) -> None:
        """
        Type text using keyboard.

        Args:
            page (Page): The Playwright page object
            text (str): Text to type
        """
        await self._ensure_page_ready(page)
        try:
            if self.animate_actions:
                # Type slower for short text, faster for long text
                delay_typing_speed = 20 + 30 * random.random() if len(text) < 100 else 5
                for char in text:
                    await page.keyboard.type(char, delay=delay_typing_speed)
            else:
                await page.keyboard.type(text)
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def hover_coords(self, page: Page, x: int, y: int) -> None:
        """
        Move mouse to specified coordinates.

        Args:
            page (Page): The Playwright page object
            x (int): X coordinate
            y (int): Y coordinate
        """
        await self._ensure_page_ready(page)
        try:
            if self.animate_actions:
                start_x, start_y = self.last_cursor_position
                await self.gradual_cursor_animation(page, start_x, start_y, x, y)
            await page.mouse.move(x, y)
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def keypress(self, page: Page, keys: List[str]) -> None:
        """
        Press specified keys in sequence.

        Args:
            page (Page): The Playwright page object
            keys (List[str]): List of keys to press
        """
        await self._ensure_page_ready(page)
        mapped_keys = [CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key) for key in keys]
        try:
            if self.animate_actions:
                for key in mapped_keys:
                    await page.keyboard.down(key)
                    await asyncio.sleep(0.02)
                for key in reversed(mapped_keys):
                    await page.keyboard.up(key)
                    await asyncio.sleep(0.02)
            else:
                for key in mapped_keys:
                    await page.keyboard.down(key)
                for key in reversed(mapped_keys):
                    await page.keyboard.up(key)
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def drag_coords(self, page: Page, path: List[Dict[str, int]]) -> None:
        """
        Perform drag operation along specified path.

        Args:
            page (Page): The Playwright page object
            path (List[Dict[str, int]]): List of coordinates forming the drag path
        """
        await self._ensure_page_ready(page)
        if not path:
            return

        try:
            if self.animate_actions:
                # Animate cursor movement to start position
                start_x, start_y = self.last_cursor_position
                await self.gradual_cursor_animation(
                    page, start_x, start_y, path[0]["x"], path[0]["y"]
                )

            await page.mouse.move(path[0]["x"], path[0]["y"])
            await page.mouse.down()

            for point in path[1:]:
                if self.animate_actions:
                    # Animate the drag movement
                    await self.gradual_cursor_animation(
                        page,
                        self.last_cursor_position[0],
                        self.last_cursor_position[1],
                        point["x"],
                        point["y"],
                    )
                else:
                    await page.mouse.move(point["x"], point["y"])

            await page.mouse.up()
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def click_coords(
        self,
        page: Page,
        x: int,
        y: int,
        button: Literal["left", "right", "back", "forward", "wheel"] = "left",
    ) -> Optional[Page]:
        """
        Click at specified coordinates with given button.

        Args:
            page (Page): The Playwright page object
            x (int): X coordinate
            y (int): Y coordinate
            button (str): Mouse button to use ('left', 'right', 'back', 'forward', 'wheel'). Default: 'left'

        Returns:
            Optional[Page]: New page if navigation occurred
        """
        await self._ensure_page_ready(page)
        try:
            match button:
                case "back":
                    await self.go_back(page)
                    return None
                case "forward":
                    await self.go_forward(page)
                    return None
                case "wheel":
                    if self.animate_actions:
                        start_x, start_y = self.last_cursor_position
                        await self.gradual_cursor_animation(
                            page, start_x, start_y, x, y
                        )
                    await page.mouse.wheel(x, y)
                    return None
                case "left" | "right" as btn:
                    if self.animate_actions:
                        start_x, start_y = self.last_cursor_position
                        await self.gradual_cursor_animation(
                            page, start_x, start_y, x, y
                        )
                    await page.mouse.click(x, y, button=btn)
                    return None
        finally:
            if self.animate_actions:
                await self.cleanup_animations(page)

    async def upload_file(self, page: Page, target_id: str, file_path: str) -> None:
        """
        Upload a file to the specified input element on the page.

        Args:
            page (Page): The Playwright page object to interact with.
            target_id (str): The unique element ID of the file input element.
            file_path (str): The local file system path to the file to upload.

        Raises:
            ValueError: If the specified input element is not found on the page.
        """
        await self._ensure_page_ready(page)
        input_file_element = page.locator(f"[__elementId='{target_id}']")
        await input_file_element.wait_for(state="attached")

        if await input_file_element.count() > 0:
            await input_file_element.set_input_files(file_path)
        else:
            raise ValueError(f"Element with ID '{target_id}' not found.")

    async def get_all_webpage_text(self, page: Page, n_lines: int = 50) -> str:
        """
        Retrieve the text content of the web page.

        Args:
            page (Page): The Playwright page object.
            n_lines (int, optional): The number of lines to return from the page inner text. Default: 50

        Returns:
            str: The text content of the page.
        """
        await self._ensure_page_ready(page)
        return await self._text_utils.get_all_webpage_text(page, n_lines)

    async def get_visible_text(self, page: Page) -> str:
        """
        Retrieve the text content of the browser viewport (approximately).
        Args:
            page (Page): The Playwright page object.
        Returns:
            str: The text content of the page.
        """
        await self._ensure_page_ready(page)
        return await self._text_utils.get_visible_text(page)

    async def get_page_markdown(self, page: Page, max_tokens: int = -1) -> str:
        """
        Retrieve the markdown content of the web page, limited to a specified number of tokens.
        Automatically detects and handles PDF content.

        Args:
            page (Page): The Playwright page object.
            max_tokens (int, optional): The maximum number of tokens to return. Default: -1 (no limit)

        Returns:
            str: The markdown content of the page or extracted PDF content.
        """
        await self._ensure_page_ready(page)
        return await self._text_utils.get_page_markdown(page, max_tokens)

    async def describe_page(
        self,
        page: Page,
        get_screenshot: bool = True,
    ) -> Tuple[str, Union[bytes, None], str]:
        """
        Describe the current state of the page including a screenshot, text content, viewport details, and metadata.

        Args:
            page (Page): The Playwright page object.
            prior_metadata_hash (Optional[str]): The previous metadata hash to compare with the current one.
            get_screenshot (bool, optional): Whether to include a screenshot in the response. Default: True

        Returns:
            A tuple containing:
                - str: The message content describing the page.
                - bytes | None: The screenshot bytes if requested. Otherwise None.
                - str: The new metadata hash of the page.
        """
        await self._ensure_page_ready(page)
        screenshot = None
        if get_screenshot:
            screenshot = await self.get_screenshot(page, path=None)
        page_title = await page.title()
        viewport = await self.get_visual_viewport(page)
        viewport_text = await self._text_utils.get_visible_text(page)
        percent_visible = int(viewport["height"] * 100 / viewport["scrollHeight"])
        percent_scrolled = int(viewport["pageTop"] * 100 / viewport["scrollHeight"])
        position_text = (
            "at the top of the page"
            if percent_scrolled < 1
            else "at the bottom of the page"
            if percent_scrolled + percent_visible >= 99
            else f"{percent_scrolled}% down from the top of the page"
        )
        page_metadata = json.dumps(await self.get_page_metadata(page), indent=4)
        metadata_hash = hashlib.md5(page_metadata.encode("utf-8")).hexdigest()

        page_metadata = f"\nThe following metadata was extracted from the webpage:\n\n{page_metadata.strip()}\n"

        message_content = (
            f"We are at the following webpage [{page_title}]({page.url}).\n"
            f"The viewport shows {percent_visible}% of the webpage, and is positioned {position_text}\n"
            f"The text in the viewport is:\n {viewport_text}"
        )

        return message_content, screenshot, metadata_hash

    async def add_cursor_box(self, page: Page, identifier: str) -> None:
        await self._animation.add_cursor_box(page, identifier)

    async def remove_cursor_box(self, page: Page, identifier: str) -> None:
        await self._animation.remove_cursor_box(page, identifier)

    async def gradual_cursor_animation(
        self, page: Page, start_x: float, start_y: float, end_x: float, end_y: float
    ) -> None:
        await self._animation.gradual_cursor_animation(
            page, start_x, start_y, end_x, end_y
        )
        self.last_cursor_position = self._animation.last_cursor_position

    async def cleanup_animations(self, page: Page) -> None:
        await self._animation.cleanup_animations(page)

    async def preview_action(self, page: Page, identifier: str) -> None:
        """
        Preview an action by animating the cursor movement and highlighting the element,
        without actually performing the action. Used for previewing clicks, hovers, or other
        interactive actions before getting user approval.

        Args:
            page (Page): The Playwright page object.
            identifier (str): The element identifier.

        Raises:
            ValueError: If the element is not visible on the page.
            PlaywrightTimeoutError: If the element does not appear within the timeout period.
        """
        await self._ensure_page_ready(page)

        selector = f"[__elementId='{identifier}']"
        try:
            # Wait for the element to be visible and scroll it into view
            await page.wait_for_selector(
                selector, state="visible", timeout=self._timeout_load * 1000
            )
            target = page.locator(selector)
            await target.scroll_into_view_if_needed()
        except PlaywrightTimeoutError:
            raise ValueError(
                f"Element with identifier {identifier} not found or not visible"
            )

        # Retrieve bounding box to determine the center for cursor movement
        box = await target.bounding_box()
        if not box:
            raise ValueError(
                f"Element with identifier {identifier} is not visible on the page."
            )
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2

        # Animate the cursor movement
        if self.animate_actions:
            await self.add_cursor_box(page, identifier)
            start_x, start_y = self.last_cursor_position
            await self.gradual_cursor_animation(
                page, start_x, start_y, center_x, center_y
            )
