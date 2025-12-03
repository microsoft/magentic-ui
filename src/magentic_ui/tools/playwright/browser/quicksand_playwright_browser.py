"""Quicksand-backed PlaywrightBrowser implementation.

Owns a single slot from ``QuicksandBrowserManager``.  On ``_start()`` it
acquires a slot (which boots Xvfb + VNC + noVNC + Chromium with
``--user-data-dir`` inside the VM), then connects from the host via CDP.
On ``_close()`` it releases the slot back to the pool, which merges the
profile back to the master directory.
"""

from __future__ import annotations

from playwright.async_api import BrowserContext, async_playwright, Playwright, Browser
from loguru import logger

from .base_playwright_browser import PlaywrightBrowser, connect_cdp_with_retry
from .quicksand_browser_manager import QuicksandBrowserManager, BrowserSlot


class QuicksandPlaywrightBrowser(PlaywrightBrowser):
    """PlaywrightBrowser backed by a Quicksand VM slot.

    The browser manager (singleton) is injected at construction time.
    ``_start`` acquires a slot and connects to Chromium's CDP endpoint.
    ``_close`` releases the slot (which triggers profile merge-back).
    """

    def __init__(
        self,
        browser_manager: QuicksandBrowserManager,
    ) -> None:
        super().__init__()
        self._browser_manager = browser_manager
        self._slot: BrowserSlot | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # ------------------------------------------------------------------
    # PlaywrightBrowser ABC
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        # Acquire slot (starts services inside VM, including Chromium with --user-data-dir)
        self._slot = await self._browser_manager.acquire_slot()

        try:
            cdp_url = f"http://127.0.0.1:{self._slot.cdp_host_port}"
            logger.info(
                f"Connecting to Chromium CDP on slot {self._slot.index} at {cdp_url}"
            )

            self._playwright = await async_playwright().start()
            self._browser = await connect_cdp_with_retry(self._playwright, cdp_url)

            # Use the default context (persistent profile from --user-data-dir)
            if not self._browser.contexts:
                raise RuntimeError("No browser contexts found after CDP connection")
            self._context = self._browser.contexts[0]
            logger.info(f"Quicksand browser context ready (slot {self._slot.index})")
        except Exception:
            # Release slot so it doesn't leak if playwright/CDP connection fails.
            # __aexit__ won't be called when __aenter__ raises.
            try:
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
            except Exception:
                logger.exception("Error stopping Playwright during startup cleanup")
            try:
                await self._browser_manager.release_slot(self._slot)
            except Exception:
                logger.exception("Error releasing slot during startup cleanup")
            finally:
                self._slot = None
            raise

    async def _close(self) -> None:
        # Each step is guarded so release_slot() is always reached
        try:
            if self._context:
                await self._context.close()
        except Exception as e:
            logger.warning(f"Error closing context: {e}")

        try:
            if self._browser:
                await self._browser.close()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error stopping playwright: {e}")

        # Release slot back to pool (triggers profile merge-back)
        if self._slot:
            await self._browser_manager.release_slot(self._slot)
            self._slot = None

        logger.info("Quicksand browser closed")

    @property
    def browser_context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError(
                "Browser context is not initialized. Start the browser first."
            )
        return self._context

    # ------------------------------------------------------------------
    # Port accessors (available after _start)
    # ------------------------------------------------------------------

    @property
    def novnc_host_port(self) -> int:
        if self._slot is None:
            raise RuntimeError("Slot not acquired yet")
        return self._slot.novnc_host_port

    @property
    def cdp_host_port(self) -> int:
        if self._slot is None:
            raise RuntimeError("Slot not acquired yet")
        return self._slot.cdp_host_port

    @property
    def vnc_password(self) -> str:
        if self._slot is None:
            raise RuntimeError("Slot not acquired yet")
        return self._slot.vnc_password
