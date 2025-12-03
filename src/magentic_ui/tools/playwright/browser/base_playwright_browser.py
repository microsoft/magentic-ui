from __future__ import annotations
import asyncio
from types import TracebackType
from typing import AsyncContextManager, Optional, Type
from typing_extensions import Self
from abc import ABC, abstractmethod
from playwright.async_api import (
    BrowserContext,
    Playwright,
    Browser,
)

from loguru import logger


async def connect_browser_with_retry(
    playwright: Playwright, url: str, timeout: int = 30
) -> Browser:
    """Wait for the WebSocket server to be ready."""
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    first_try = True
    while loop.time() - start_time < timeout:
        try:
            return await playwright.chromium.connect(url)
        except Exception as e:
            if first_try:
                logger.info(f"Trying to establish connection to browser at {url}...")
                first_try = False
            else:
                logger.warning(f"Retrying connection in 5 seconds: {e}.")
            await asyncio.sleep(5)

    raise TimeoutError("Browser did not become available in time")


async def connect_cdp_with_retry(
    playwright: Playwright, endpoint_url: str, timeout: int = 30
) -> Browser:
    """Connect to a running Chromium via CDP endpoint."""
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    first_try = True
    while loop.time() - start_time < timeout:
        try:
            return await playwright.chromium.connect_over_cdp(endpoint_url)
        except Exception as e:
            if first_try:
                logger.info(f"Trying CDP connection to {endpoint_url}...")
                first_try = False
            else:
                logger.warning(f"Retrying CDP connection in 5s: {e}")
            await asyncio.sleep(5)

    raise TimeoutError("Browser CDP endpoint did not become available in time")


class PlaywrightBrowser(AsyncContextManager["PlaywrightBrowser"], ABC):
    """
    Abstract base class for Playwright browser.
    """

    def __init__(self):
        self._closed: bool = False

    @abstractmethod
    async def _start(self) -> None:
        """
        Start the browser resource.
        """
        pass

    @abstractmethod
    async def _close(self) -> None:
        """
        Close the browser resource.
        """
        pass

    # Expose playwright context
    @property
    @abstractmethod
    def browser_context(self) -> BrowserContext:
        """
        Return the Playwright browser context.
        """
        pass

    async def __aenter__(self) -> Self:
        """
        Start the Playwright browser.

        Returns:
            Self: The current instance of PlaywrightBrowser
        """
        await self._start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Stop the browser.

        This method attempts a graceful termination first by sending SIGTERM,
        and if that fails, it forces termination with SIGKILL. It ensures
        the browser is properly cleaned up.
        """

        if not self._closed:
            # Close the browser resource
            await self._close()
            self._closed = True
