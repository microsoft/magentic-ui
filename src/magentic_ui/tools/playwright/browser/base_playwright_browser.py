from __future__ import annotations
import asyncio
from types import TracebackType
from typing import AsyncContextManager, Optional, Type
from typing_extensions import Self
from abc import ABC, abstractmethod
from autogen_core import ComponentBase
from pydantic import BaseModel
from docker.errors import DockerException
from docker.models.containers import Container
from playwright.async_api import (
    BrowserContext,
    Playwright,
    Browser,
    async_playwright,
)

from loguru import logger


async def connect_browser_with_retry(
    playwright: Playwright, url: str, timeout: int = 30
) -> Browser:
    """Wait for the WebSocket server to be ready."""
    start_time = asyncio.get_event_loop().time()
    first_try = True
    while asyncio.get_event_loop().time() - start_time < timeout:
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


class PlaywrightBrowser(
    AsyncContextManager["PlaywrightBrowser"], ABC, ComponentBase[BaseModel]
):
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


class DockerPlaywrightBrowser(PlaywrightBrowser):
    """
    Base class for Docker Playwright Browser
    """

    def __init__(self):
        super().__init__()
        self._container: Optional[Container] = None
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    @property
    def browser_address(self) -> str:
        raise NotImplementedError()

    @property
    def browser_context(self) -> BrowserContext:
        """
        Return the Playwright browser context.
        This is a placeholder implementation and should be overridden in subclasses.
        """
        if self._context is None:
            raise RuntimeError(
                "Browser context is not initialized. Start the browser first."
            )
        return self._context

    @abstractmethod
    async def create_container(self) -> Container:
        pass

    @abstractmethod
    def _generate_new_browser_address(self) -> None:
        """
        Generate a new address for the Playwright browser. Used if the current address fails to connect.
        """
        pass

    def _close_container(self) -> None:
        if self._container:
            self._container.stop(timeout=10)
            self._container = None

    async def _close(self) -> None:
        """
        Close the browser resource.
        This is a placeholder implementation and should be overridden in subclasses.
        """
        logger.info("Closing browser...")
        if self._context:
            await self._context.close()

        if self._browser:
            await self._browser.close()

        if self._playwright:
            await self._playwright.stop()

        self._close_container()

    async def _start(self) -> None:
        """
        Start a headless Playwright browser using the official Playwright Docker image.
        """
        retries = 0
        while True:
            try:
                self._container = await self.create_container()
                await asyncio.to_thread(self._container.start)
                break
            except DockerException as e:
                # Handle container name conflict (409 error)
                if "409" in str(e) and "already in use" in str(e):
                    logger.warning(f"Container name conflict detected: {e}")
                    # Try to find and reuse existing container
                    if await self._try_reuse_existing_container():
                        logger.info("Successfully reused existing container")
                        break
                    else:
                        # If reuse fails, generate new address and retry
                        self._generate_new_browser_address()
                        logger.info(f"Generated new browser address: {self.browser_address}")
                        retries += 1
                        if retries >= 3:
                            raise
                        continue
                
                # Handle other container start failures
                retries += 1
                if retries >= 3:
                    raise
                self._generate_new_browser_address()
                logger.warning(
                    f"Failed to start container: {e}.\nRetrying with new address: {self.browser_address}"
                )

        browser_address = self.browser_address
        logger.info(f"Browser started at {browser_address}")

        self._playwright = await async_playwright().start()
        logger.info(f"Connecting to browser at {browser_address}")
        self._browser = await connect_browser_with_retry(
            self._playwright, browser_address
        )
        logger.info("Connected to browser")
        self._context = await self._browser.new_context()

    async def _try_reuse_existing_container(self) -> bool:
        """
        Try to reuse an existing container with the same name.
        Returns True if successful, False otherwise.
        """
        try:
            import docker
            
            client = docker.from_env()
            
            # Get expected container name
            container_name = self._get_expected_container_name()
            if not container_name:
                return False
            
            # Try to find existing container
            try:
                existing_container = client.containers.get(container_name)
                
                # Check if container is running
                if existing_container.status == 'running':
                    logger.info(f"Found running container: {container_name}")
                    self._container = existing_container
                    return True
                elif existing_container.status == 'exited':
                    logger.info(f"Found stopped container: {container_name}, restarting...")
                    existing_container.restart()  # type: ignore
                    self._container = existing_container
                    return True
                else:
                    logger.warning(f"Container {container_name} in unexpected state: {existing_container.status}")
                    return False
                    
            except Exception as not_found_error:
                # Handle container not found or other errors
                if "not found" in str(not_found_error).lower():
                    logger.info(f"Container {container_name} not found")
                else:
                    logger.warning(f"Error accessing container {container_name}: {not_found_error}")
                return False
                
        except Exception as e:
            logger.error(f"Error while trying to reuse container: {e}")
            return False
    
    def _get_expected_container_name(self) -> str:
        """
        Get the expected container name. Should be overridden by subclasses.
        """
        # This is a fallback implementation
        return ""
