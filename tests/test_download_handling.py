import os
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from playwright.async_api import Page, BrowserContext
from magentic_ui.tools.playwright.browser.local_playwright_browser import (
    LocalPlaywrightBrowser,
)
from magentic_ui.tools.playwright.playwright_controller import PlaywrightController


@pytest.mark.asyncio
class TestDownloadHandling:
    @pytest_asyncio.fixture
    async def browser(self, tmp_path):
        """Create a browser instance with downloads enabled"""
        browser = LocalPlaywrightBrowser(
            headless=True, enable_downloads=True, browser_data_dir=str(tmp_path)
        )
        await browser._start()
        yield browser
        await browser._close()

    @pytest_asyncio.fixture
    async def context(self, browser):
        """Get the browser context"""
        return browser.browser_context

    @pytest_asyncio.fixture
    async def downloads_dir(self, tmp_path):
        """Create a temporary downloads directory"""
        downloads_dir = tmp_path / "downloads"
        downloads_dir.mkdir(exist_ok=True)
        return str(downloads_dir)

    async def test_automated_download(self, browser, context, downloads_dir):
        """Test that automated downloads are saved to both directories"""
        # Create a controller
        controller = PlaywrightController(
            downloads_folder=downloads_dir, animate_actions=False
        )

        # Create a test page with a download link
        page = await context.new_page()
        await controller.on_new_page(page)
        await page.set_content("""
            <html>
                <body>
                    <a href="data:text/plain;base64,SGVsbG8gV29ybGQ=" download="test.txt" __elementId="1">Download</a>
                </body>
            </html>
        """)

        # Click the download link using the controller
        await controller.click_id(context, page, "1")

        # Wait for the download to complete
        await asyncio.sleep(2)  # Increased wait time

        # Get the expected webby directory path
        webby_dir = os.path.join(os.path.dirname(downloads_dir), ".webby")

        # Check that the file exists in both directories
        assert os.path.exists(os.path.join(downloads_dir, "test.txt")), f"File not found in {downloads_dir}"
        assert os.path.exists(os.path.join(webby_dir, "test.txt")), f"File not found in {webby_dir}"

        # Verify file contents
        with open(os.path.join(downloads_dir, "test.txt"), "rb") as f1, open(os.path.join(webby_dir, "test.txt"), "rb") as f2:
            assert f1.read() == f2.read(), "File contents don't match"

    async def test_manual_download(self, browser, context, downloads_dir):
        """Test that manual downloads are saved to both directories"""
        # Create a controller
        controller = PlaywrightController(
            downloads_folder=downloads_dir, animate_actions=False
        )

        # Create a test page with a download link
        page = await context.new_page()
        await controller.on_new_page(page)
        await page.set_content("""
            <html>
                <body>
                    <a href="data:text/plain;base64,SGVsbG8gV29ybGQ=" download="test_manual.txt">Download</a>
                </body>
            </html>
        """)

        # Simulate a manual click
        await page.click("text=Download")

        # Wait for the download to complete
        await asyncio.sleep(2)  # Increased wait time

        # Get the expected webby directory path
        webby_dir = os.path.join(os.path.dirname(downloads_dir), ".webby")

        # Check that the file exists in both directories
        assert os.path.exists(os.path.join(downloads_dir, "test_manual.txt")), f"File not found in {downloads_dir}"
        assert os.path.exists(os.path.join(webby_dir, "test_manual.txt")), f"File not found in {webby_dir}"

        # Verify file contents
        with open(os.path.join(downloads_dir, "test_manual.txt"), "rb") as f1, open(os.path.join(webby_dir, "test_manual.txt"), "rb") as f2:
            assert f1.read() == f2.read(), "File contents don't match"

    async def test_real_pdf_download(self, browser, context, downloads_dir):
        """Test downloading a real PDF from arXiv"""
        # Create a controller
        controller = PlaywrightController(
            downloads_folder=downloads_dir, animate_actions=False
        )

        # Create a test page
        page = await context.new_page()
        await controller.on_new_page(page)

        # Go to a real arXiv paper that exists
        await page.goto("https://arxiv.org/abs/2402.17764")

        # Wait for the page to load
        await page.wait_for_load_state("networkidle")

        # Try different selectors for the PDF link
        selectors = [
            "a.download-pdf",
            "a[href*='pdf']",
            "a[href$='.pdf']",
            "a.mobile-submission-download",
            "a[title*='Download PDF']",
        ]

        pdf_link = None
        for selector in selectors:
            try:
                # Try to find the link
                pdf_link = await page.wait_for_selector(
                    selector, timeout=5000, state="attached"
                )
                if pdf_link:
                    break
            except:
                continue

        assert pdf_link is not None, "Could not find PDF download link"

        # Add __elementId attribute for the controller
        await page.evaluate("el => el.setAttribute('__elementId', '1')", pdf_link)

        # Ensure the link is visible by scrolling to it
        await pdf_link.scroll_into_view_if_needed()
        await asyncio.sleep(1)  # Wait for any animations to complete

        # Click the link
        await controller.click_id(context, page, "1")

        # Wait longer for the download to complete (arXiv PDFs can be large)
        await asyncio.sleep(10)  # Increased wait time

        # Get the expected webby directory path
        webby_dir = os.path.join(os.path.dirname(downloads_dir), ".webby")

        # Check that the file exists in both directories
        pdf_files_downloads = [
            f for f in os.listdir(downloads_dir) if f.endswith(".pdf")
        ]
        pdf_files_webby = [f for f in os.listdir(webby_dir) if f.endswith(".pdf")]

        assert len(pdf_files_downloads) > 0, f"No PDF file found in {downloads_dir}"
        assert len(pdf_files_webby) > 0, f"No PDF file found in {webby_dir}"
        assert pdf_files_downloads[0] == pdf_files_webby[0], "PDF filenames don't match"

        # Verify file contents
        with open(os.path.join(downloads_dir, pdf_files_downloads[0]), "rb") as f1, open(os.path.join(webby_dir, pdf_files_webby[0]), "rb") as f2:
            assert f1.read() == f2.read(), "PDF file contents don't match"
