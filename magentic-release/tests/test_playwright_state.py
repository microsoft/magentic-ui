import pytest
import pytest_asyncio
from typing import AsyncGenerator
from playwright.async_api import Browser, BrowserContext, async_playwright
from magentic_ui.tools.playwright.playwright_state import (
    BrowserState,
    Tab,
    save_browser_state,
    load_browser_state,
)


@pytest_asyncio.fixture
async def browser() -> AsyncGenerator[Browser, None]:
    """Fixture that provides a browser instance."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def browser_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Fixture that provides a browser context."""
    context = await browser.new_context()
    yield context
    await context.close()


@pytest_asyncio.fixture
async def multi_tab_context(
    browser_context: BrowserContext,
) -> AsyncGenerator[BrowserContext, None]:
    # Create multiple tabs with different URLs and scroll positions
    pages = []
    urls = [
        "data:text/html,<body style='height: 2000px'>Page 1</body>",
        "data:text/html,<body style='height: 2000px'>Page 2</body>",
        "data:text/html,<body style='height: 2000px'>Page 3</body>",
    ]

    for url in urls:
        page = await browser_context.new_page()
        await page.goto(url)
        await page.evaluate("window.scrollTo(0, 100)")
        pages.append(page)

    # Set the second tab as active
    await pages[1].bring_to_front()

    yield browser_context


@pytest.mark.asyncio
async def test_save_state_basic(browser_context: BrowserContext):
    """Test saving state with a single tab"""
    page = await browser_context.new_page()
    url = "data:text/html,<body>Test Page</body>"
    await page.goto(url)

    state = await save_browser_state(browser_context, simplified=False)

    assert isinstance(state, BrowserState)
    assert len(state.tabs) == 1
    assert state.tabs[0].url == url
    assert state.tabs[0].scrollX == 0
    assert state.tabs[0].scrollY == 0
    assert state.activeTabIndex == 0


@pytest.mark.asyncio
async def test_save_state_with_scroll(browser_context: BrowserContext):
    """Test saving state with scroll position"""
    page = await browser_context.new_page()
    url = "data:text/html,<body style='height: 2000px'>Test Page</body>"
    await page.goto(url)
    await page.evaluate("window.scrollTo(0, 100)")

    state = await save_browser_state(browser_context, simplified=False)

    assert state.tabs[0].scrollY == 100


@pytest.mark.asyncio
async def test_save_state_multiple_tabs(multi_tab_context: BrowserContext):
    """Test saving state with multiple tabs"""
    state = await save_browser_state(
        multi_tab_context, controlled_page=multi_tab_context.pages[1], simplified=False
    )

    assert len(state.tabs) == 3
    assert state.activeTabIndex == 1  # Second tab should be active
    assert all(tab.scrollY == 100 for tab in state.tabs)


@pytest.mark.asyncio
async def test_load_state_basic(browser_context: BrowserContext):
    """Test loading a basic state"""
    # Create a simple state to load
    test_state = BrowserState(
        state={},
        tabs=[
            Tab(
                url="data:text/html,<body>Test Page</body>",
                index=0,
                scrollX=0,
                scrollY=0,
            )
        ],
        activeTabIndex=0,
    )

    await load_browser_state(browser_context, test_state)

    assert len(browser_context.pages) == 1
    assert browser_context.pages[0].url == test_state.tabs[0].url


@pytest.mark.asyncio
async def test_load_state_with_scroll(browser_context: BrowserContext):
    """Test loading state with scroll position"""
    test_state = BrowserState(
        state={},
        tabs=[
            Tab(
                url="data:text/html,<body style='height: 2000px'>Test Page</body>",
                index=0,
                scrollX=0,
                scrollY=100,
            )
        ],
        activeTabIndex=0,
    )

    await load_browser_state(browser_context, test_state)

    # Check scroll position
    scroll_y = await browser_context.pages[0].evaluate("window.scrollY")
    assert scroll_y == 100


@pytest.mark.asyncio
async def test_load_state_multiple_tabs(browser_context: BrowserContext):
    """Test loading state with multiple tabs"""
    test_state = BrowserState(
        state={},
        tabs=[
            Tab(
                url="data:text/html,<body>Page 1</body>", index=0, scrollX=0, scrollY=0
            ),
            Tab(
                url="data:text/html,<body>Page 2</body>", index=1, scrollX=0, scrollY=0
            ),
            Tab(
                url="data:text/html,<body>Page 3</body>", index=2, scrollX=0, scrollY=0
            ),
        ],
        activeTabIndex=1,
    )

    await load_browser_state(browser_context, test_state)

    assert len(browser_context.pages) == 3
    # Check that URLs match
    assert [page.url for page in browser_context.pages] == [
        tab.url for tab in test_state.tabs
    ]


@pytest.mark.asyncio
async def test_load_only_active_tab(browser_context: BrowserContext):
    """Test loading only the active tab"""
    test_state = BrowserState(
        state={},
        tabs=[
            Tab(
                url="data:text/html,<body>Page 1</body>", index=0, scrollX=0, scrollY=0
            ),
            Tab(
                url="data:text/html,<body>Page 2</body>", index=1, scrollX=0, scrollY=0
            ),
            Tab(
                url="data:text/html,<body>Page 3</body>", index=2, scrollX=0, scrollY=0
            ),
        ],
        activeTabIndex=1,
    )

    await load_browser_state(browser_context, test_state, load_only_active_tab=True)

    assert len(browser_context.pages) == 1
    assert browser_context.pages[0].url == test_state.tabs[1].url


@pytest.mark.asyncio
async def test_load_state_error_handling(browser_context: BrowserContext):
    """Test error handling during state loading"""
    # Create a state with an invalid URL
    test_state = BrowserState(
        state={},
        tabs=[Tab(url="invalid://url", index=0, scrollX=0, scrollY=0)],
        activeTabIndex=0,
    )

    await load_browser_state(browser_context, test_state)

    # Should fall back to about:blank
    assert len(browser_context.pages) == 1
    assert browser_context.pages[0].url == "about:blank"
