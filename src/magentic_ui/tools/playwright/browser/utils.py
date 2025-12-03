from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

from .base_playwright_browser import PlaywrightBrowser
from .local_playwright_browser import LocalPlaywrightBrowser

if TYPE_CHECKING:
    from .quicksand_browser_manager import QuicksandBrowserManager


def get_available_port() -> tuple[int, socket.socket]:
    """
    Get an available port on the local machine.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    return port, s


def get_browser_resource(
    bind_dir: Path,
    novnc_port: int = -1,
    playwright_port: int = -1,
    headless: bool = True,
    local: bool = False,
    quicksand_manager: QuicksandBrowserManager | None = None,
) -> Tuple[PlaywrightBrowser, int, int]:
    """
    Create a Playwright browser instance.

    Args:
        bind_dir: Directory to bind for the browser resource.
        novnc_port: Port for the noVNC server. Default: -1 (auto-assign).
        playwright_port: Port for the Playwright browser. Default: -1 (auto-assign).
        headless: Whether the browser is running in headless mode. Default: True.
        local: Whether the browser is running locally. Default: False.
        quicksand_manager: If provided, route the browser through this
            Quicksand VM manager (acquires a slot inside the VM); otherwise
            a local Playwright browser is launched on the host.

    Returns:
        A tuple containing:
            - PlaywrightBrowser: The browser instance.
            - int: Port number for the noVNC server (-1 for quicksand until _start).
            - int: Port number for the Playwright browser (-1 for quicksand until _start).
    """
    if quicksand_manager is not None:
        from .quicksand_playwright_browser import QuicksandPlaywrightBrowser

        browser = QuicksandPlaywrightBrowser(
            browser_manager=quicksand_manager,
        )
        # Ports are not known until _start() acquires a slot.
        # Callers read ports from browser.novnc_host_port after start.
        return browser, -1, -1

    browser = LocalPlaywrightBrowser(headless=headless)
    return browser, novnc_port, playwright_port
