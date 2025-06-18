from typing import Dict, List, Any
from playwright.async_api import BrowserContext, Page, StorageState
from pydantic import BaseModel
from logging import getLogger

logger = getLogger(__name__)


class Tab(BaseModel):
    """
    Represents the state of a browser tab.
    """

    url: str
    index: int
    scrollX: int
    scrollY: int


class BrowserState(BaseModel):
    """
    Represents the saved state of a browser.
    """

    state: Any  # type: ignore
    # originally: state: StorageState (TypedDict from Playwright, not compatible with Pydantic on Python < 3.12)
    tabs: List[Tab]
    activeTabIndex: int


async def save_browser_state(
    context: BrowserContext,
    controlled_page: Page | None = None,
    simplified: bool = True,
) -> BrowserState:
    """
    Save the browser's storage state along with the URLs and scroll positions of all open tabs,
    and identify the active tab.

    Args:
        context (BrowserContext): The browser context to save state from
        controlled_page (Page, optional): Optional page that is currently being controlled
        simplified (bool, optional): If True, skip saving scroll positions and storage state. Saving context state can interfere with the live browser. Default: True

    Returns:
        BrowserState: A BrowserState instance.
    """

    # Use controlled page as active tab if provided, otherwise use first page
    active_tab_index = 0
    if controlled_page is not None:
        # Find index of controlled page
        for i, page in enumerate(context.pages):
            if page == controlled_page:
                active_tab_index = i
                break

    state: StorageState = (
        await context.storage_state() if not simplified else StorageState(origins=[])
    )

    open_tabs: List[Tab] = []
    for i, page in enumerate(context.pages):
        if simplified:
            sx, sy = 0, 0
        else:
            try:
                scroll: Dict[str, int] = await page.evaluate(
                    "() => ({ scrollX: window.scrollX, scrollY: window.scrollY })"
                )
                # Cast values to int to avoid float issues
                sx, sy = int(scroll["scrollX"]), int(scroll["scrollY"])
            except Exception:
                # In case evaluation fails, use default scroll positions
                sx, sy = 0, 0
        assert isinstance(page.url, str)
        open_tabs.append(
            Tab(
                url=page.url,
                index=i,
                scrollX=sx,
                scrollY=sy,
            )
        )

    return BrowserState(state=state, tabs=open_tabs, activeTabIndex=active_tab_index)


async def load_browser_state(
    context: BrowserContext, state: BrowserState, load_only_active_tab: bool = False
) -> None:
    """
    Load the browser's storage state and restore open tabs using the provided BrowserState instance.
    The function reopens each tab at its saved URL and scroll position and brings the saved active tab
    into focus. Only empty tabs (about:blank) are closed first.

    Args:
        context (BrowserContext): The browser context to load state into
        state (BrowserState): The BrowserState instance containing the saved state
        load_only_active_tab (bool, optional): If True, only the active tab is loaded, otherwise all tabs are loaded. Default: False

    Returns:
        None
    """
    # Only close empty pages (about:blank) in the context
    try:
        for page in context.pages:
            if page.url == "about:blank":
                await page.close()

        restored_tabs: List[str] = []
        pages: List[Page] = []

        # Determine which tabs to restore
        tabs_to_restore = (
            [state.tabs[state.activeTabIndex]] if load_only_active_tab else state.tabs
        )

        # Create tabs
        for tab in tabs_to_restore:
            page: Page = await context.new_page()
            await page.goto(tab.url)
            await page.wait_for_load_state("load")
            await page.evaluate(
                "([x, y]) => window.scrollTo(x, y)", [tab.scrollX, tab.scrollY]
            )
            restored_tabs.append(f"{tab.url} ({tab.scrollX}, {tab.scrollY})")
            pages.append(page)

        # Bring the active tab to front
        if pages:
            # If only loading active tab, it will be the first page
            # Otherwise, use the saved active tab index
            active_index = 0 if load_only_active_tab else state.activeTabIndex
            if 0 <= active_index < len(pages):
                await pages[active_index].bring_to_front()
            await pages[0].wait_for_timeout(5000)

    except Exception as e:
        logger.error(f"Error loading state: {e}")
