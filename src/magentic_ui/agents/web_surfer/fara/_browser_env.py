"""PlaywrightBrowserEnvironment — concrete BrowserEnvironment for Playwright.

Wraps a Playwright ``Page`` and ``PlaywrightController`` behind the
``BrowserEnvironment`` ABC so the fara agent never touches Playwright
directly.  Created during ``FaraWebSurfer._lazy_init()`` after the
quicksand browser is started.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ....tools.playwright.playwright_controller_fara import CUA_KEY_TO_PLAYWRIGHT_KEY
from ._types import BrowserEnvironment

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ....tools.playwright.playwright_controller_fara import PlaywrightController


_FIND_CHORD = frozenset({"Control", "f"})
_FIND_OVERLAY_JS = (Path(__file__).parent / "find_overlay.js").read_text()


def _normalize_chord(keys: list[str]) -> frozenset:
    """Map CUA/raw keys to Playwright names and lowercase single letters."""
    mapped = [CUA_KEY_TO_PLAYWRIGHT_KEY.get(k.lower(), k) for k in keys]
    return frozenset(k if len(k) > 1 else k.lower() for k in mapped)


class PlaywrightBrowserEnvironment(BrowserEnvironment):
    """Delegates every action to ``PlaywrightController`` + ``Page``."""

    def __init__(
        self,
        page: Page,
        controller: PlaywrightController,
        viewport_width: int = 1440,
        viewport_height: int = 900,
    ) -> None:
        self._page = page
        self._controller = controller
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        # Download tracking (managed internally, read by harness)
        self.last_download: str | None = None
        self.prior_metadata_hash: str | None = None

    # --- Page access for harness (_recover_active_page) ---

    @property
    def page(self) -> Page:
        return self._page

    @page.setter
    def page(self, new_page: Page) -> None:
        self._page = new_page

    # --- Core GUI actions ---

    async def left_click(self, x: float, y: float) -> None:
        new_page = await self._controller.click_coords(self._page, x, y)
        if new_page is not None:
            self._page = new_page

    async def type_text(
        self,
        x: float,
        y: float,
        text: str,
        press_enter: bool = True,
        clear_first: bool = False,
    ) -> None:
        new_page = await self._controller.fill_coords(
            self._page,
            x,
            y,
            text,
            press_enter=press_enter,
            delete_existing_text=clear_first,
        )
        if new_page is not None:
            self._page = new_page

    async def key(self, keys: list[str]) -> None:
        if _normalize_chord(keys) == _FIND_CHORD:
            await self._page.evaluate(_FIND_OVERLAY_JS)
            return
        await self._controller.keypress(self._page, keys)

    async def hover(self, x: float, y: float) -> None:
        await self._controller.hover_coords(self._page, x, y)

    async def scroll_up(self, amount: int = 400) -> None:
        await self._controller.page_up(self._page, amount)

    async def scroll_down(self, amount: int = 400) -> None:
        await self._controller.page_down(self._page, amount)

    async def wait(self, duration: float) -> None:
        await self._controller.sleep(self._page, duration)

    async def get_screenshot(self) -> bytes:
        return await self._controller.get_screenshot(self._page)

    # --- Browser navigation ---

    async def goto(self, url: str) -> None:
        reset_meta, reset_dl = await self._controller.visit_page(self._page, url)
        if reset_dl:
            self.last_download = None
        if reset_meta:
            self.prior_metadata_hash = None

    async def back(self) -> None:
        await self._controller.back(self._page)

    async def get_url(self) -> str:
        return await self._controller.get_page_url(self._page)

    # --- Extended actions (FaraQwen3NextAgent) ---

    async def double_click(self, x: float, y: float) -> None:
        await self._controller.double_click_coords(self._page, x, y)

    async def right_click(self, x: float, y: float) -> None:
        await self._controller.right_click_coords(self._page, x, y)

    async def triple_click(self, x: float, y: float) -> None:
        await self._controller.triple_click_coords(self._page, x, y)

    async def left_click_drag(self, end_x: float, end_y: float) -> None:
        await self._controller.left_click_drag(self._page, end_x, end_y)

    async def hscroll(self, pixels: int) -> None:
        await self._controller.hscroll(self._page, pixels)

    async def scroll_to(self, x: int, y: int) -> None:
        await self._page.evaluate(f"window.scrollTo({x}, {y})")

    async def get_scroll(self) -> tuple[int, int]:
        xy = await self._page.evaluate("[window.scrollX, window.scrollY]")
        return int(xy[0]), int(xy[1])

    async def type_direct(self, text: str) -> None:
        await self._page.keyboard.type(text)

    # --- Page content ---

    async def get_page_markdown(self) -> str:
        return await self._controller.get_page_markdown(self._page)

    # --- Lifecycle ---

    async def wait_for_load(
        self,
        state: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load",
        timeout: int | None = None,
    ) -> None:
        # Translate Playwright's TimeoutError (which inherits Exception, not
        # the built-in TimeoutError) into asyncio.TimeoutError, so callers
        # can stay Playwright-agnostic and rely on a standard, narrow
        # exception type.
        try:
            await self._controller.wait_for_load_state(
                self._page, state=state, timeout=timeout
            )
        except PlaywrightTimeoutError as e:
            raise asyncio.TimeoutError(str(e)) from e
