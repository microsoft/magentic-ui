import socket
from pathlib import Path
from typing import Tuple
from autogen_core import ComponentModel

from .base_playwright_browser import PlaywrightBrowser
from .headless_docker_playwright_browser import HeadlessDockerPlaywrightBrowser
from .local_playwright_browser import LocalPlaywrightBrowser
from .vnc_docker_playwright_browser import VncDockerPlaywrightBrowser


def get_available_port() -> tuple[int, socket.socket]:
    """
    Get an available port on the local machine.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    return port, s


def _get_docker_browser_resource_config(
    bind_dir: Path,
    novnc_port: int,
    playwright_port: int,
    inside_docker: bool,
    headless: bool,
    network_name: str = "my-network",
) -> Tuple[PlaywrightBrowser, int, int]:
    if playwright_port == -1:
        playwright_port, sock = get_available_port()
        sock.close()

    if headless:
        browser = HeadlessDockerPlaywrightBrowser(
            playwright_port=playwright_port,
            inside_docker=inside_docker,
        )
    else:
        if novnc_port == -1:
            novnc_port, sock = get_available_port()
            sock.close()

        browser = VncDockerPlaywrightBrowser(
            bind_dir=bind_dir,
            playwright_port=playwright_port,
            novnc_port=novnc_port,
            inside_docker=inside_docker,
            network_name=network_name,
        )

    return browser, novnc_port, playwright_port


def get_browser_resource_config(
    bind_dir: Path,
    novnc_port: int = -1,
    playwright_port: int = -1,
    inside_docker: bool = True,
    headless: bool = True,
    local: bool = False,
    network_name: str = "my-network",
) -> Tuple[ComponentModel, int, int]:
    """
    Create a VNC Docker Playwright Browser Resource configuration. The requested ports for novnc and playwright may be overwritten. The final values for each port number will be in the return value.

    Args:
        bind_dir (str): Directory to bind for the browser resource.
        novnc_port (int, optional): Port for the noVNC server. Default: -1 (auto-assign).
        playwright_port (int, optional): Port for the Playwright browser. Default: -1 (auto-assign).
        inside_docker (bool, optional): Whether the browser is running inside Docker. Default: True.
        headless (bool, optional): Whether the browser is running in headless mode. Default: True.
        local (bool, optional): Whether the browser is running locally. Default: False.
        network_name (str, optional): Name of the Docker network to use. Default: "my-network".
    Returns:
        A tuple containing the following:
            - VncDockerPlaywrightBrowserResource: Configured browser resource.
            - int: Port number for the noVNC server.
            - int: Port number for the Playwright browser.
    """

    if local:
        browser = LocalPlaywrightBrowser(headless=headless)
    else:
        browser, novnc_port, playwright_port = _get_docker_browser_resource_config(
            bind_dir=bind_dir,
            novnc_port=novnc_port,
            playwright_port=playwright_port,
            inside_docker=inside_docker,
            headless=headless,
            network_name=network_name,
        )

    return browser.dump_component(), novnc_port, playwright_port
