import pytest
import base64
import os
import pytest_asyncio

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
)

from magentic_ui.tools import PlaywrightController

FAKE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fake Page</title>
  <script>
    window.clickCount = 0;
    function incrementClickCount() {
      window.clickCount++;
    }
  </script>
</head>
<body>
  <h1 id="header">Welcome to the Fake Page</h1>
  <a href="#" id="new-page-link" __elementId="26">Open New Page</a>
  <button id="click-me" __elementId="10" onclick="incrementClickCount()">Click Me</button>
  <button id="disabled-button" __elementId="11" disabled>Disabled Button</button>
  <button id="hidden-button" __elementId="12" style="display:none;">Hidden Button</button>
  <input type="text" id="input-box" __elementId="13" />
  <select id="dropdown" __elementId="14">
    <option __elementId="15" value="one">Option One</option>
    <option __elementId="16" value="two">Option Two</option>
  </select>
  <select id="multi-dropdown" __elementId="17" multiple>
    <option __elementId="18" value="red">Red</option>
    <option __elementId="19" value="blue">Blue</option>
    <option __elementId="20" value="green">Green</option>
  </select>
  <div class="custom-dropdown" id="expandable-dropdown" __elementId="21">
    <button class="dropdown-button" __elementId="22">Select an option ▼</button>
    <div class="dropdown-content" style="display: none;">
      <div class="dropdown-item" __elementId="23" data-value="alpha">Alpha</div>
      <div class="dropdown-item" __elementId="24" data-value="beta">Beta</div>
      <div class="dropdown-item" __elementId="25" data-value="gamma">Gamma</div>
    </div>
  </div>
  <script>
    // Add dropdown functionality
    document.querySelector('.dropdown-button').addEventListener('click', function() {
      const content = document.querySelector('.dropdown-content');
      content.style.display = content.style.display === 'none' ? 'block' : 'none';
    });
    
    document.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', function() {
        document.querySelector('.dropdown-button').textContent = this.textContent;
        document.querySelector('.dropdown-content').style.display = 'none';
      });
    });

    // Fixed new page link functionality:
    document.getElementById('new-page-link').addEventListener('click', function(e) {
      e.preventDefault();
      const newWindow = window.open("", "_blank");
      newWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>New Page</title>
</head>
<body>
  <h1>New Page</h1>
</body>
</html>`);
      newWindow.document.close();
    });
  </script>
</body>
</html>
"""


@pytest_asyncio.fixture(scope="function")
async def browser():
    """
    Launch a headless browser for each test function.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def context(browser: Browser):
    """
    Create a fresh BrowserContext for each test.
    """
    ctx = await browser.new_context()
    yield ctx
    await ctx.close()


@pytest_asyncio.fixture
async def page(context: BrowserContext, controller):
    """
    Provide a new Page with FAKE_HTML loaded and the controller.
    Returns a tuple of (page, controller).
    """
    p = await context.new_page()
    await p.set_content(FAKE_HTML)
    yield (p, controller)  # Return both page and controller as a tuple
    await p.close()


@pytest.fixture
def controller(tmp_path):
    """
    Return an instance of the PlaywrightController.
    """
    downloads_folder = str(tmp_path / "downloads")
    os.makedirs(downloads_folder, exist_ok=True)

    # Instantiate your real controller
    # e.g. from your_module import PlaywrightController
    ctrl = PlaywrightController(
        downloads_folder=downloads_folder,
        animate_actions=False,
        viewport_width=800,
        viewport_height=600,
        to_resize_viewport=True,
        timeout_load=2,
        sleep_after_action=1,
        single_tab_mode=True,
    )
    return ctrl


@pytest.mark.asyncio
class TestPlaywrightController:
    async def test_get_interactive_rects(self, page):
        page_obj, pc = page
        rects = await pc.get_interactive_rects(page_obj)
        # We expect the 4 elements with __elementId to be listed: 10, 11, 12, 13, 14, 15, 16
        assert isinstance(rects, dict)
        assert "10" in rects  # "Click Me" button
        assert "13" in rects  # input box
        # "12" is hidden, but it's assigned __elementId. Depending on your script's logic,
        # a hidden element might not show up as an interactive rect if it's not visible.
        # So check conditionally:
        if "12" in rects:
            # That means the script is capturing it even though it's display=none
            # This depends on your page_script logic. Adjust as needed.
            pass

    async def test_get_focused_rect_id(self, page):
        page_obj, pc = page
        # Focus the input box (elementId="13")
        await page_obj.click("#input-box")
        focused_id = await pc.get_focused_rect_id(page_obj)
        assert focused_id == "13"

    async def test_get_page_metadata(self, page):
        page_obj, pc = page
        metadata = await pc.get_page_metadata(page_obj)
        # Might be empty if the script didn't find JSON-LD or meta tags
        # We'll check it's a dict anyway
        assert isinstance(metadata, dict)

    async def test_go_back_and_go_forward(self, page):
        """
        This is a contrived example:
        We'll do 2 navigations (fake), then check go_back/go_forward.
        In practice, you'd do real URLs or data URLs.
        """
        page_obj, pc = page

        # Start at FAKE_HTML
        # Now navigate somewhere else:
        await pc.visit_page(
            page_obj,
            "data:text/html;base64," + base64.b64encode(FAKE_HTML.encode()).decode(),
        )
        # We go back
        back_ok = await pc.go_back(page_obj)
        # In some cases, if there's no real history, back_ok might be False
        # Then forward
        forward_ok = await pc.go_forward(page_obj)

        # Just ensure calls don't crash
        assert isinstance(back_ok, bool)
        assert isinstance(forward_ok, bool)

    async def test_visit_page(self, page):
        page_obj, pc = page
        reset_prior, reset_last = await pc.visit_page(
            page_obj,
            "data:text/html;base64," + base64.b64encode(FAKE_HTML.encode()).decode(),
        )
        assert (
            reset_prior is True
        )  # The page loaded, so presumably we reset the metadata hash
        # If no download is triggered, reset_last should be False
        assert reset_last is False

    async def test_refresh_page(self, page):
        page_obj, pc = page
        # Refresh
        original_url = page_obj.url
        await pc.refresh_page(page_obj)
        assert page_obj.url == original_url

    async def test_page_down_and_up(self, page):
        page_obj, pc = page
        # page_down and page_up won't raise exceptions, let's just ensure the calls work
        await pc.page_down(page_obj)
        await pc.page_up(page_obj)

    async def test_add_remove_cursor_box(self, page):
        page_obj, pc = page
        # Animations are off by default in the fixture, so we just call:
        await pc.add_cursor_box(page_obj, "10")
        # There's no direct "result" but we can check that the script didn't crash
        # Then remove
        await pc.remove_cursor_box(page_obj, "10")

    async def test_click_id(self, context, page):
        page_obj, pc = page

        # Get initial click count
        initial_clicks = await page_obj.evaluate("() => window.clickCount")
        assert initial_clicks == 0

        # Test clicking the "Click Me" button (elementId="10")
        new_page = await pc.click_id(context, page_obj, "10")
        # Because single_tab_mode=False, if that button had a 'target=_blank' link, it might open a new page.
        # But here it's just a button. So new_page is expected to be None
        assert new_page is None

        # Verify the button was actually clicked
        final_clicks = await page_obj.evaluate("() => window.clickCount")
        assert final_clicks == 1, "Button click was not registered"

        # Test right click (should not increment clickCount, but should not error)
        await pc.click_id(context, page_obj, "10", button="right")
        right_clicks = await page_obj.evaluate("() => window.clickCount")
        assert (
            right_clicks == final_clicks
        ), "Right click should not increment clickCount"

        # Test holding left click for 0.2 seconds (should increment clickCount by 1)
        await pc.click_id(context, page_obj, "10", hold=0.2)
        held_clicks = await page_obj.evaluate("() => window.clickCount")
        assert (
            held_clicks == right_clicks + 1
        ), "Held left click should increment clickCount by 1"

        # If we attempt to click the disabled button (elementId="11"), your script might throw an exception
        # or ignore it. We'll see:
        try:
            await pc.click_id(context, page_obj, "11")
        except Exception:
            # It's okay if it fails because it's disabled
            pass

    async def test_hover_id(self, page):
        page_obj, pc = page
        # Hover over "click-me" button
        await pc.hover_id(page_obj, "10")
        # If the script is animating, it might move the mouse. We just expect no error.

    async def test_fill_id(self, page):
        page_obj, pc = page
        # Fill text into the input box
        await pc.fill_id(page_obj, "13", "Hello world", press_enter=False)
        # Retrieve the value to verify
        value = await page_obj.evaluate(
            "() => document.querySelector('#input-box').value"
        )
        assert value == "Hello world"

    async def test_scroll_id(self, page):
        page_obj, pc = page
        # We'll attempt to scroll the SELECT element with __elementId="14"
        # It's not scrollable in this simple HTML, but let's just ensure no crash:
        await pc.scroll_id(page_obj, "14", "down")
        await pc.scroll_id(page_obj, "14", "up")

    async def test_select_option(self, context, page):
        page_obj, pc = page
        # We'll select the second option (elementId="16")
        await pc.select_option(context, page_obj, "16")
        # Check if the <select> is now set to "two"
        selected_value = await page_obj.evaluate(
            "() => document.querySelector('#dropdown').value"
        )
        assert selected_value == "two"

    async def test_get_tabs_information(self, context, page):
        page_obj, pc = page
        tabs_info = await pc.get_tabs_information(context, page_obj)
        assert len(tabs_info) > 0
        assert isinstance(tabs_info, list)
        # We have at least one tab
        assert "index" in tabs_info[0]
        assert "title" in tabs_info[0]
        assert "url" in tabs_info[0]

    async def test_switch_tab_and_close_tab(self, context, page):
        page_obj, pc = page

        # Create a second tab
        page2 = await context.new_page()
        await page2.set_content("<html><body><p>Another page</p></body></html>")
        # We have 2 tabs. Switch to second tab (index=1)
        switched_page = await pc.switch_tab(context, 1)
        assert switched_page == page2

        # Close it (index=1 is the new tab)
        # Then we expect to switch automatically to index=0
        new_active_page = await pc.close_tab(context, 1)
        assert new_active_page == page_obj

    async def test_create_new_tab(self, context, page):
        page_obj, pc = page
        new_tab = await pc.create_new_tab(
            context,
            "data:text/html;base64," + base64.b64encode(FAKE_HTML.encode()).decode(),
        )
        assert new_tab is not None
        # The new tab presumably displays the same FAKE_HTML.
        await new_tab.wait_for_selector("#header")

    async def test_get_all_webpage_text(self, page):
        page_obj, pc = page
        text = await pc.get_all_webpage_text(page_obj, n_lines=10)
        assert "Welcome to the Fake Page" in text

    async def test_get_visible_text(self, page):
        page_obj, pc = page
        visible_text = await pc.get_visible_text(page_obj)
        assert "Welcome to the Fake Page" in visible_text
        # The hidden button text "Hidden Button" should not appear in the visible text.
        assert "Hidden Button" not in visible_text

    async def test_get_page_markdown(self, page):
        page_obj, pc = page
        # If MarkItDown is installed, this should return some markdown version of the HTML.
        try:
            markdown = await pc.get_page_markdown(page_obj, max_tokens=1000)
            assert "Welcome to the Fake Page" in markdown
        except ImportError:
            pytest.skip("MarkItDown library not installed; skipping markdown test.")

    async def test_describe_page(self, page):
        page_obj, pc = page
        message, screenshot_bytes, metadata_hash = await pc.describe_page(
            page_obj, get_screenshot=True
        )
        assert "Fake Page" in message
        assert metadata_hash  # Some hash string
        assert screenshot_bytes is not None
        assert len(screenshot_bytes) > 0

    async def test_select_multiple_options(self, context, page):
        page_obj, pc = page
        # Select multiple options in the multi-select dropdown
        await pc.select_option(context, page_obj, "20")  # Select "Green"

        # Check if both options are selected
        selected_values = await page_obj.evaluate(
            "() => Array.from(document.querySelector('#multi-dropdown').selectedOptions).map(opt => opt.value)"
        )
        assert "green" in selected_values
        assert len(selected_values) == 1

    async def test_expand_and_select_dropdown(self, context, page):
        page_obj, pc = page

        # First click to expand the dropdown
        await pc.click_id(context, page_obj, "22")  # Click the dropdown button

        # Verify the dropdown content is visible
        is_visible = await page_obj.evaluate(
            "() => document.querySelector('.dropdown-content').style.display === 'block'"
        )
        assert is_visible, "Dropdown content should be visible after clicking"

        # Select an option from the expanded dropdown
        await pc.click_id(context, page_obj, "24")  # Click "Beta" option

        # Verify the selection was made
        button_text = await page_obj.evaluate(
            "() => document.querySelector('.dropdown-button').textContent"
        )
        assert "Beta" in button_text, "Dropdown button should show selected option"

        # Verify the dropdown is closed after selection
        is_hidden = await page_obj.evaluate(
            "() => document.querySelector('.dropdown-content').style.display === 'none'"
        )
        assert is_hidden, "Dropdown content should be hidden after selection"

    @pytest.mark.parametrize("single_tab_mode", [False])
    async def test_new_page_button(self, browser, context, tmp_path, single_tab_mode):
        """Test behavior of a button that opens a new page in both single-tab and multi-tab modes."""

        # Create controller with specified single_tab_mode
        downloads_folder = str(tmp_path / "downloads")
        os.makedirs(downloads_folder, exist_ok=True)
        pc = PlaywrightController(
            downloads_folder=downloads_folder,
            animate_actions=False,
            viewport_width=800,
            viewport_height=600,
            to_resize_viewport=True,
            timeout_load=2,
            sleep_after_action=1,
            single_tab_mode=single_tab_mode,
        )
        # Create initial page
        page = await context.new_page()
        await page.set_content(FAKE_HTML)
        await pc.on_new_page(page)

        # Get initial tab count
        initial_tabs = len(context.pages)

        # Click the link that opens new page
        new_page = await pc.click_id(context, page, "26")

        # Get final tab count
        final_tabs = len(context.pages)

        if single_tab_mode:
            # In single tab mode:
            # - No new page should be returned
            # - Tab count should remain the same
            assert new_page is None
            assert final_tabs == initial_tabs

            # The content should be loaded in the same tab
            current_content = await page.content()
            assert "New Page" in current_content

        else:
            # In multi-tab mode:
            # - A new page object should be returned
            # - Tab count should increase by 1
            assert final_tabs == initial_tabs + 1
            assert new_page is not None

            # The new page should have the expected content
            new_page_content = await new_page.content()
            assert "New Page" in new_page_content

            # Original page should still show original content
            original_content = await page.content()
            assert "Welcome to the Fake Page" in original_content

    async def test_download_file(self, browser, context, tmp_path):
        """Test downloading a file and saving it to the downloads folder."""
        # Create a controller with downloads enabled
        downloads_folder = str(tmp_path / "downloads")
        os.makedirs(downloads_folder, exist_ok=True)
        pc = PlaywrightController(
            downloads_folder=downloads_folder,
            animate_actions=False,
            viewport_width=800,
            viewport_height=600,
            to_resize_viewport=True,
            timeout_load=2,
            sleep_after_action=1,
            single_tab_mode=False,
        )

        # Create a page with a download link
        page = await context.new_page()
        await pc.on_new_page(page)

        # Create HTML content with a download link and click counter
        download_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Download Test</title>
            <script>
                window.clickCount = 0;
                function incrementClickCount() {
                    window.clickCount++;
                    console.log('Click count:', window.clickCount);
                }
            </script>
        </head>
        <body>
            <a href="data:text/plain;base64,SGVsbG8gV29ybGQ="
               download="test.txt" 
               id="download-link" 
               onclick="incrementClickCount()"
               __elementId="1">Download Text File</a>
        </body>
        </html>
        """
        await page.set_content(download_html)

        # Get initial click count
        initial_clicks = await page.evaluate("() => window.clickCount")
        assert initial_clicks == 0

        # Click the download link
        _ = await pc.click_id(context, page, "1")

        # Verify the click occurred
        final_clicks = await page.evaluate("() => window.clickCount")
        assert final_clicks == 1, "Download link was not clicked"

        # Verify the download occurred
        downloaded_files = os.listdir(downloads_folder)
        assert len(downloaded_files) == 1, "Expected one downloaded file"
        assert downloaded_files[0] == "test.txt", "Expected file named test.txt"

        # Verify the file contents
        with open(os.path.join(downloads_folder, "test.txt"), "r") as f:
            content = f.read()
            assert content == "Hello World", "Expected file content to be 'Hello World'"

        # Clean up
        await page.close()

    async def test_upload_file(self, browser, context, tmp_path):
        """Test uploading a file to a file input element."""
        # Create a controller
        downloads_folder = str(tmp_path / "downloads")
        os.makedirs(downloads_folder, exist_ok=True)
        pc = PlaywrightController(
            downloads_folder=downloads_folder,
            animate_actions=False,
            viewport_width=800,
            viewport_height=600,
            to_resize_viewport=True,
            timeout_load=2,
            sleep_after_action=1,
            single_tab_mode=False,
        )

        # Create a page with a file input
        page = await context.new_page()
        await pc.on_new_page(page)

        # Create HTML content with a file input and a display area for the selected file
        upload_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>File Upload Test</title>
            <script>
                function displayFileName() {
                    const fileInput = document.getElementById('file-input');
                    const fileDisplay = document.getElementById('file-display');
                    if (fileInput.files.length > 0) {
                        fileDisplay.textContent = 'Selected file: ' + fileInput.files[0].name;
                    } else {
                        fileDisplay.textContent = 'No file selected';
                    }
                }
            </script>
        </head>
        <body>
            <h1>File Upload Test</h1>
            <input type="file" id="file-input" __elementId="30" onchange="displayFileName()">
            <div id="file-display">No file selected</div>
        </body>
        </html>
        """
        await page.set_content(upload_html)

        # Create a test file to upload
        test_file_path = os.path.join(tmp_path, "test_upload.txt")
        with open(test_file_path, "w") as f:
            f.write("This is a test file for upload")

        # Upload the file
        await pc.upload_file(page, "30", test_file_path)

        # Verify the file was selected
        file_display_text = await page.evaluate(
            "() => document.getElementById('file-display').textContent"
        )
        assert "test_upload.txt" in file_display_text, "File was not properly uploaded"

        # Clean up
        await page.close()

    async def test_double_click_coords(self, page):
        page_obj, pc = page
        # Add a double-click counter to the page
        await page_obj.evaluate("""
            window.doubleClickCount = 0;
            document.addEventListener('dblclick', () => {
                window.doubleClickCount++;
            });
        """)

        # Get coordinates of the "Click Me" button
        button = await page_obj.query_selector("#click-me")
        box = await button.bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2

        # Perform double click
        await pc.double_click_coords(page_obj, x, y)

        # Verify double click was registered
        double_clicks = await page_obj.evaluate("() => window.doubleClickCount")
        assert double_clicks == 1, "Double click was not registered"

    async def test_scroll_coords(self, page):
        page_obj, pc = page
        # Add content to make page scrollable
        await page_obj.evaluate("""
            const div = document.createElement('div');
            div.style.height = '2000px';
            div.textContent = 'Tall content';
            document.body.appendChild(div);
        """)

        # Initial scroll position
        initial_scroll = await page_obj.evaluate("() => window.scrollY")

        # Scroll down 100 pixels from coordinates (0, 0)
        await pc.scroll_coords(page_obj, 0, 0, 0, 100)

        # Verify scroll occurred
        new_scroll = await page_obj.evaluate("() => window.scrollY")
        assert new_scroll > initial_scroll, "Page did not scroll down"

    async def test_type_direct(self, page):
        page_obj, pc = page
        # Focus the input box
        input_box = await page_obj.query_selector("#input-box")
        await input_box.focus()

        # Type text directly
        test_text = "Hello World"
        await pc.type_direct(page_obj, test_text)

        # Verify text was typed
        value = await page_obj.evaluate(
            "() => document.querySelector('#input-box').value"
        )
        assert value == test_text, "Text was not typed correctly"

    async def test_hover_coords(self, page):
        page_obj, pc = page
        # Add hover detection to the button
        await page_obj.evaluate("""
            window.isHovered = false;
            document.querySelector('#click-me').addEventListener('mouseover', () => {
                window.isHovered = true;
            });
            document.querySelector('#click-me').addEventListener('mouseout', () => {
                window.isHovered = false;
            });
        """)

        # Get button coordinates
        button = await page_obj.query_selector("#click-me")
        box = await button.bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2

        # Hover over the coordinates
        await pc.hover_coords(page_obj, x, y)

        # Verify hover was detected
        is_hovered = await page_obj.evaluate("() => window.isHovered")
        assert is_hovered, "Hover was not detected"

    async def test_keypress(self, page):
        page_obj, pc = page
        # Focus the input box
        input_box = await page_obj.query_selector("#input-box")
        await input_box.focus()

        # Test various key combinations
        # Test simple key sequence
        await pc.keypress(page_obj, ["a", "b", "c"])
        value = await page_obj.evaluate(
            "() => document.querySelector('#input-box').value"
        )
        assert "abc" in value, "Single key press not registered"

    async def test_drag_coords(self, page):
        page_obj, pc = page
        # Add drag tracking to the page
        await page_obj.evaluate("""
            window.dragPath = [];
            document.addEventListener('mousedown', (e) => {
                window.dragPath = [{x: e.clientX, y: e.clientY}];
            });
            document.addEventListener('mousemove', (e) => {
                if (e.buttons === 1) {  // Left button is being pressed
                    window.dragPath.push({x: e.clientX, y: e.clientY});
                }
            });
        """)

        # Define a drag path
        drag_path = [
            {"x": 100, "y": 100},  # Start
            {"x": 200, "y": 200},  # End
        ]

        # Perform drag operation
        await pc.drag_coords(page_obj, drag_path)

        # Verify drag occurred
        path_length = await page_obj.evaluate("() => window.dragPath.length")
        assert path_length > 0, "Drag path was not recorded"

        # Verify start and end points
        start_point = await page_obj.evaluate("() => window.dragPath[0]")
        end_point = await page_obj.evaluate(
            "() => window.dragPath[window.dragPath.length - 1]"
        )
        assert (
            abs(start_point["x"] - drag_path[0]["x"]) < 5
        ), "Drag didn't start at correct X coordinate"
        assert (
            abs(start_point["y"] - drag_path[0]["y"]) < 5
        ), "Drag didn't start at correct Y coordinate"
        assert (
            abs(end_point["x"] - drag_path[-1]["x"]) < 5
        ), "Drag didn't end at correct X coordinate"
        assert (
            abs(end_point["y"] - drag_path[-1]["y"]) < 5
        ), "Drag didn't end at correct Y coordinate"

    async def test_click_coords(self, context, page):
        page_obj, pc = page
        # Get coordinates of the "Click Me" button
        button = await page_obj.query_selector("#click-me")
        box = await button.bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2

        # Test left click
        initial_clicks = await page_obj.evaluate("() => window.clickCount")
        await pc.click_coords(page_obj, x, y, "left")
        final_clicks = await page_obj.evaluate("() => window.clickCount")
        assert final_clicks == initial_clicks + 1, "Left click not registered"

        # Test right click
        await pc.click_coords(page_obj, x, y, "right")
        # Right click doesn't increment our counter, but shouldn't throw an error

        # Test wheel click
        await pc.click_coords(page_obj, x, y, "wheel")
        # Wheel click doesn't increment our counter, but shouldn't throw an error
