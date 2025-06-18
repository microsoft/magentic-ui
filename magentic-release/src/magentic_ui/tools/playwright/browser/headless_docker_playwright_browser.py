from __future__ import annotations

import asyncio
import logging

from autogen_core import Component
import docker
from docker.models.containers import Container
from pydantic import BaseModel

from .base_playwright_browser import DockerPlaywrightBrowser

# Configure logging
logger = logging.getLogger(__name__)


class HeadlessBrowserConfig(BaseModel):
    """
    Configuration for the VNC Docker Playwright Browser Resource.
    """

    playwright_port: int = 37367
    inside_docker: bool = False


class HeadlessDockerPlaywrightBrowser(
    DockerPlaywrightBrowser, Component[HeadlessBrowserConfig]
):
    """
    A headless Docker Playwright Browser implementation using the official Playwright Docker image.

    Args:
        playwright_port (int, optional): The port number to expose for the Playwright browser WebSocket endpoint. Default: 37367.
        inside_docker (bool, optional): Whether the browser is running inside a Docker container. Default: False.

    Properties:
        browser_address (str): Returns the WebSocket address for connecting to the browser.
            Format: "ws://localhost:{playwright_port}"

    Example:
        ```python
        browser = HeadlessDockerPlaywrightBrowser(playwright_port=37367)
        await browser.start()
        # Use the browser for automation
        await browser.close()
        ```
    """

    component_config_schema = HeadlessBrowserConfig
    component_type = "other"

    def __init__(
        self,
        *,
        playwright_port: int = 37367,
        inside_docker: bool = False,
    ):
        super().__init__()
        self._playwright_port = playwright_port
        self._inside_docker = inside_docker
        self._hostname = (
            f"magentic-ui-headless-browser_{self._playwright_port}"
            if inside_docker
            else "localhost"
        )

    @property
    def browser_address(self) -> str:
        """
        Get the address of the Playwright browser.
        """
        return f"ws://{self._hostname}:{self._playwright_port}"

    def _generate_new_browser_address(self) -> None:
        """
        Generate a new address for the Playwright browser. Used if the current address fails to connect.
        """
        # TODO: Implement this
        pass

    async def create_container(self) -> Container:
        """
        Start a headless Playwright browser using the official Playwright Docker image.
        """
        logger.info(
            f"Starting headless Playwright browser on port {self._playwright_port}..."
        )

        client = docker.from_env()
        return await asyncio.to_thread(
            client.containers.create,
            name=f"magentic-ui-headless-browser_{self._playwright_port}",
            image="mcr.microsoft.com/playwright:v1.51.1-noble",
            detach=True,
            auto_remove=True,
            ports={
                f"{self._playwright_port}/tcp": self._playwright_port,
            },
            command=[
                "/bin/sh",
                "-c",
                f"npx -y playwright@1.51 run-server --port {self._playwright_port} --host 0.0.0.0",
            ],
        )

    def _to_config(self) -> HeadlessBrowserConfig:
        return HeadlessBrowserConfig(
            playwright_port=self._playwright_port,
            inside_docker=self._inside_docker,
        )

    @classmethod
    def _from_config(
        cls, config: HeadlessBrowserConfig
    ) -> HeadlessDockerPlaywrightBrowser:
        return cls(
            playwright_port=config.playwright_port,
            inside_docker=config.inside_docker,
        )
