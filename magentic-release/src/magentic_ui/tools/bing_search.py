from urllib.parse import quote_plus
from playwright.async_api import async_playwright
from urllib.parse import urlparse
import asyncio
import tiktoken
from dataclasses import dataclass
from loguru import logger
from ..tools import PlaywrightController


@dataclass
class BingSearchResults:
    search_results: str
    links: list[dict[str, str]]
    page_contents: dict[str, str]
    combined_content: str


async def extract_page_markdown(url: str) -> tuple[str, str]:
    """Extract markdown content from a given URL.

    Args:
        url (str): The URL to extract content from

    Returns:
        A tuple containing:
            - str: The URL
            - str: The markdown content extracted from the page
    """
    try:
        async with async_playwright() as p:
            launch_args = ["--disable-extensions", "--disable-file-system"]
            browser = await p.chromium.launch(
                headless=True, env={}, args=launch_args, chromium_sandbox=True
            )
            context = await browser.new_context(
                accept_downloads=False,  # Disable downloads
                permissions=[],  # No additional permissions
            )

            controller = PlaywrightController()

            page = await context.new_page()
            try:
                await page.goto(url)
                await asyncio.sleep(1)
                markdown = await controller.get_page_markdown(page)
            except Exception as e:
                logger.error(f"Error extracting content: {e}")
                markdown = "Error extracting content"

            await context.close()
            await browser.close()
            return url, markdown
    except Exception as e:
        logger.error(f"Error extracting content: {e}")
        return url, "Error extracting content"


async def get_bing_search_results(
    query: str,
    max_pages: int = 3,
    timeout_seconds: int = 10,
    max_tokens_per_page: int = 10000,
) -> BingSearchResults:
    """Get the Bing search results for a given query.

    WARNING: This function spawns multiple browser local playwright instances which may consume a lot of resources and can cause risks.

    Args:
        query (str): The search query to use
        max_pages (int, optional): Maximum number of pages to extract. Default: 3
        timeout_seconds (int, optional): Maximum time in seconds to wait for search results. Default: 10
        max_tokens_per_page (int, optional): Maximum number of tokens to extract from each page. Default: 10000

    Returns:
        BingSearchResults: Contains search results markdown, links, and extracted content
    """
    search_results: str = ""
    links: list[dict[str, str]] = []
    page_contents: dict[str, str] = {}
    combined_content: str = ""

    try:
        result = await asyncio.wait_for(
            extract_page_markdown(
                f"https://www.bing.com/search?q={quote_plus(query)}&FORM=QBLH"
            ),
            timeout=timeout_seconds,
        )
        _, search_results = result

        # Extract links from markdown
        def extract_links(markdown_text: str) -> list[dict[str, str]]:
            """Extract links from markdown text.

            Args:
                markdown_text (str): The markdown text to extract links from

            Returns:
                list[dict[str, str]]: List of dictionaries containing display_text and url
            """

            def is_valid_url(url: str) -> bool:
                """Check if a URL is valid."""
                try:
                    result = urlparse(url)
                    return all([result.scheme in ("http", "https"), result.netloc])
                except Exception:
                    return False

            links: list[dict[str, str]] = []
            lines = markdown_text.split("\n")
            for line in lines:
                # Match markdown link format: [display_text](url)
                if (
                    line.count("[") == 1
                    and line.count("]") == 1
                    and line.count("(") == 1
                    and line.count(")") == 1
                ):
                    display_start = line.find("[") + 1
                    display_end = line.find("]")
                    url_start = line.find("(") + 1
                    url_end = line.find(")")

                    if all(
                        i != -1
                        for i in [
                            display_start,
                            display_end,
                            url_start,
                            url_end,
                        ]
                    ):
                        display_text = line[display_start:display_end]
                        url = line[url_start:url_end]

                        # Only add if URL is valid
                        if is_valid_url(url):
                            links.append({"display_text": display_text, "url": url})
            return links

        links = extract_links(search_results)

        # Extract content from first 5 links in parallel
        first_few_urls = [link["url"] for link in links[:max_pages]]
        tasks = [extract_page_markdown(url) for url in first_few_urls]
        extracted_contents = await asyncio.gather(*tasks, return_exceptions=True)

        # Create a dictionary mapping URLs to their content, handling any failed extractions
        page_contents: dict[str, str] = {}
        for i, result in enumerate(extracted_contents):
            url = first_few_urls[i]
            if isinstance(result, Exception):
                continue
            elif isinstance(result, tuple):
                _, content = result  # type: ignore
                if content != "Error extracting content":
                    page_contents[url] = content

        # Combine all extracted page contents into a single string
        if page_contents:
            combined_content = "Search Results for " + query + "\n\n"
            for url, content in page_contents.items():
                if max_tokens_per_page == -1:
                    token_limited_content = content
                else:
                    tokenizer = tiktoken.encoding_for_model("gpt-4o")
                    tokens = tokenizer.encode(content)
                    limited_content = tokenizer.decode(tokens[:max_tokens_per_page])
                    token_limited_content = limited_content
                combined_content += f"Page: {url}\n{token_limited_content}\n\n"

    except asyncio.TimeoutError as e:
        logger.info(f"Timeout error: {e}")
        # If we timeout, we'll still return any partial results we managed to get
        if not combined_content and page_contents:
            # If we got some pages but hadn't combined them yet
            combined_content = (
                "Search Results for " + query + " (Partial results due to timeout)\n\n"
            )
            for url, content in page_contents.items():
                if max_tokens_per_page == -1:
                    token_limited_content = content
                else:
                    tokenizer = tiktoken.encoding_for_model("gpt-4o")
                    tokens = tokenizer.encode(content)
                    limited_content = tokenizer.decode(tokens[:max_tokens_per_page])
                    token_limited_content = limited_content
                combined_content += f"Page: {url}\n{token_limited_content}\n\n"
        elif not search_results:
            # If we got absolutely nothing, return empty results
            return BingSearchResults("", [], {}, "")
    except Exception as e:
        logger.error(f"Error getting Bing search results: {e}")
        return BingSearchResults("", [], {}, "")
    return BingSearchResults(search_results, links, page_contents, combined_content)
