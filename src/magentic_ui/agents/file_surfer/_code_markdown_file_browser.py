import io
import re
import time
from pathlib import Path
from mimetypes import guess_type
from typing import List, Optional, Tuple, Union
from autogen_core.code_executor import CodeExecutor, CodeBlock
from autogen_core import CancellationToken

from ._browser_code_helpers import (
    get_path_validation_code,
    get_is_dir_check_code,
    get_file_conversion_code,
    get_directory_listing_code,
    get_find_files_code,
)


class CodeExecutorMarkdownFileBrowser:
    """
    A Markdown-powered file browser that works with a CodeExecutor.

    This class provides functionality to browse files and directories, converting their contents
    to Markdown for display. It supports pagination, file searching, and navigation through
    directory structures.
    """

    def __init__(
        self,
        code_executor: CodeExecutor,
        viewport_size: int = 1024 * 8,
        save_converted_files: bool = False,
    ):
        """
        Initialize a new CodeExecutorMarkdownFileBrowser.

        Args:
            code_executor (CodeExecutor): The CodeExecutor instance to use for file operations
            viewport_size (int, optional): Maximum number of characters to display per page. Pages are adjusted dynamically to avoid cutting off words. Default: 8192.
            save_converted_files (bool, optional): If True, converted files are saved in a subdirectory named "converted_files" in the code executor's working directory. Default: False.
        """
        self.viewport_size = viewport_size  # Applies only to the standard uri types
        self.history: List[Tuple[str, float]] = list()
        self.page_title: Optional[str] = None
        self.save_converted_files: bool = save_converted_files
        self.viewport_current_page = 0
        self.viewport_pages: List[Tuple[int, int]] = list()
        self.image_path: Optional[str] = None
        self._markdown_converter = None  # Lazy init
        self._page_content: str = ""
        self._find_on_page_query: Union[str, None] = None
        self._find_on_page_last_result: Union[int, None] = (
            None  # Location of the last result
        )
        self._code_executor = code_executor
        self.did_lazy_init = False

    async def lazy_init(self) -> None:
        """
        Perform lazy initialization for the file browser.
        """
        if not self.did_lazy_init:
            await self.set_path(".")
            self.did_lazy_init = True

    @property
    def path(self) -> str:
        """Return the path of the current page."""
        if len(self.history) == 0:
            return "."
        return self.history[-1][0]

    async def set_path(self, path: str) -> None:
        """
        Set the current path and load its contents.

        Args:
            path (str): An absolute or relative path to the file or directory to open.

        The file or directory contents will be loaded and converted to Markdown format.
        Updates the browser history and resets the viewport position.
        """
        self.history.append((path, time.time()))
        await self._open_path(path)
        self.viewport_current_page = 0
        self.find_on_page_query = None
        self.find_on_page_viewport = None

    @property
    def viewport(self) -> str:
        """
        Get the content of the current viewport page.

        Returns:
            str: The text content for the current page of the viewport.
        """
        bounds = self.viewport_pages[self.viewport_current_page]
        return self.page_content[bounds[0] : bounds[1]]

    @property
    def page_content(self) -> str:
        """Return the full contents of the current page."""
        return self._page_content

    def _set_page_content(self, content: str, split_pages: bool = True) -> None:
        """
        Set the text content of the current page.

        Args:
            content (str): The full content to display on the page.
            split_pages (bool, optional): Whether to split the content into pages based on the viewport size. Default: True
        """
        self._page_content = content

        if split_pages:
            self._split_pages()
        else:
            self.viewport_pages = [(0, len(self._page_content))]

        if self.viewport_current_page >= len(self.viewport_pages):
            self.viewport_current_page = len(self.viewport_pages) - 1

    def page_down(self) -> None:
        """Move the viewport down one page, if possible."""
        self.viewport_current_page = min(
            self.viewport_current_page + 1, len(self.viewport_pages) - 1
        )

    def page_up(self) -> None:
        """Move the viewport up one page, if possible."""
        self.viewport_current_page = max(self.viewport_current_page - 1, 0)

    def find_on_page(self, query: str) -> Union[str, None]:
        """
        Search for text in the current document starting from the current viewport.

        Args:
            query (str): The text to search for. Supports basic wildcard (*) matching.

        Returns:
            str | None: The viewport content where the match was found, or None if no match found.
            If the query matches the previous search, performs a find_next operation instead.
        """
        # Did we get here via a previous find_on_page search with the same query?
        # If so, map to find_next
        if (
            query == self._find_on_page_query
            and self.viewport_current_page == self._find_on_page_last_result
        ):
            return self.find_next()

        # Ok it's a new search start from the current viewport
        self._find_on_page_query = query
        viewport_match = self._find_next_viewport(query, self.viewport_current_page)
        if viewport_match is None:
            self._find_on_page_last_result = None
            return None
        else:
            self.viewport_current_page = viewport_match
            self._find_on_page_last_result = viewport_match
            return self.viewport

    def find_next(self) -> Union[str, None]:
        """Scroll to the next viewport that matches the query"""

        if self._find_on_page_query is None:
            return None

        starting_viewport = self._find_on_page_last_result
        if starting_viewport is None:
            starting_viewport = 0
        else:
            starting_viewport += 1
            if starting_viewport >= len(self.viewport_pages):
                starting_viewport = 0

        viewport_match = self._find_next_viewport(
            self._find_on_page_query, starting_viewport
        )
        if viewport_match is None:
            self._find_on_page_last_result = None
            return None
        else:
            self.viewport_current_page = viewport_match
            self._find_on_page_last_result = viewport_match
            return self.viewport

    def _find_next_viewport(
        self, query: Optional[str], starting_viewport: int
    ) -> Union[int, None]:
        """Search for matches between the starting viewport looping when reaching the end."""

        if query is None:
            return None

        # Normalize the query, and convert to a regular expression
        nquery = re.sub(r"\*", "__STAR__", query)
        nquery = " " + (" ".join(re.split(r"\W+", nquery))).strip() + " "
        nquery = nquery.replace(
            " __STAR__ ", "__STAR__ "
        )  # Merge isolated stars with prior word
        nquery = nquery.replace("__STAR__", ".*").lower()

        if nquery.strip() == "":
            return None

        idxs: List[int] = list()
        idxs.extend(range(starting_viewport, len(self.viewport_pages)))
        idxs.extend(range(0, starting_viewport))

        for i in idxs:
            bounds = self.viewport_pages[i]
            content = self.page_content[bounds[0] : bounds[1]]

            # TODO: Remove markdown links and images
            ncontent = " " + (" ".join(re.split(r"\W+", content))).strip().lower() + " "
            if re.search(nquery, ncontent):
                return i

        return None

    async def open_path(self, path: str) -> str:
        """
        Open a file or directory in the file surfer.
        Args:
            path (str): An absolute or relative path to the file or directory to open.
        Returns:
            str: The viewport content where the match was found, or None if no match found.
        """
        await self.set_path(path)
        return self.viewport

    def _split_pages(self) -> None:
        """Split the page contents into pages that are approximately the viewport size. Small deviations are permitted to ensure words are not broken."""
        # Handle empty pages
        if len(self._page_content) == 0:
            self.viewport_pages = [(0, 0)]
            return

        # Break the viewport into pages
        self.viewport_pages = []
        start_idx = 0
        while start_idx < len(self._page_content):
            end_idx = min(start_idx + self.viewport_size, len(self._page_content))
            # Adjust to end on a space
            while end_idx < len(self._page_content) and self._page_content[
                end_idx - 1
            ] not in [" ", "\t", "\r", "\n"]:
                end_idx += 1
            self.viewport_pages.append((start_idx, end_idx))
            start_idx = end_idx

    async def _validate_path(self, path: str) -> bool:
        """
        Validate that a path exists using the code executor.
        Args:
            path (str): The path to validate.
        Returns:
            bool: True if the path exists, False otherwise.
        """
        code = get_path_validation_code(path)
        result = await self._code_executor.execute_code_blocks(
            [CodeBlock(code=code, language="python")],
            cancellation_token=CancellationToken(),
        )
        return result.output.strip().lower() == "true"

    async def _open_path(
        self,
        path: str,
    ) -> None:
        """
        Open a file for reading, converting it to Markdown in the process.
        Args:
            path (str): The path to the file to open.
        """
        if not await self._validate_path(path):
            self.page_title = "FileNotFoundError"
            self._set_page_content(f"# FileNotFoundError\n\nFile not found: {path}")
        else:
            try:
                code = get_is_dir_check_code(path)
                result = await self._code_executor.execute_code_blocks(
                    [CodeBlock(code=code, language="python")],
                    cancellation_token=CancellationToken(),
                )
                is_dir = result.output.strip().lower() == "true"
                mime_type, _ = guess_type(path)

                if is_dir:
                    dir_content = await self._fetch_local_dir(path)
                    if self._markdown_converter is None:
                        from markitdown import MarkItDown

                        self._markdown_converter = MarkItDown()
                    res = self._markdown_converter.convert_stream(
                        io.BytesIO(dir_content.encode("utf-8")),
                        file_extension=".txt",
                    )
                    self.page_title = res.title
                    self._set_page_content(res.text_content, split_pages=False)
                elif mime_type and mime_type.startswith("image/"):
                    self.page_title = Path(path).name
                    self._set_page_content("")
                    work_dir = getattr(self._code_executor, "work_dir", ".")
                    self.image_path = str((Path(work_dir) / path).resolve())
                else:
                    # Read and convert file content using code executor
                    convert_code = get_file_conversion_code(path)
                    result = await self._code_executor.execute_code_blocks(
                        [CodeBlock(code=convert_code, language="python")],
                        cancellation_token=CancellationToken(),
                    )

                    # Parse the output to get title and content
                    output_lines = result.output.split("\n")
                    title_line = next(
                        line for line in output_lines if line.startswith("TITLE:")
                    )
                    content_start = next(
                        i
                        for i, line in enumerate(output_lines)
                        if line.startswith("CONTENT:")
                    )

                    self.page_title = title_line[6:] or None
                    markdown_content = "\n".join(output_lines[content_start:])[8:]
                    self._set_page_content(markdown_content)

                    # Save as .converted.md regardless of original extension
                    if self.save_converted_files:
                        try:
                            work_dir = getattr(self._code_executor, "work_dir", ".")
                            converted_dir = Path(work_dir) / "converted_files"
                            converted_dir.mkdir(
                                parents=True, exist_ok=True
                            )  # Create if it doesn't exist
                            original_path = (Path(work_dir) / path).resolve()
                            md_filename = original_path.stem + ".converted.md"
                            md_path = converted_dir / md_filename
                            md_path.write_text(markdown_content)
                        except Exception as e:
                            print(
                                f"Warning: Failed to save markdown file for {path}: {e}"
                            )
            except Exception as e:
                UnsupportedFormatException, FileConversionException = (
                    _get_markitdown_exceptions()
                )
                if isinstance(e, UnsupportedFormatException):
                    self.page_title = "UnsupportedFormatException"
                    self._set_page_content(
                        f"# UnsupportedFormatException\n\nCannot preview '{path}' as Markdown."
                    )
                elif isinstance(e, FileConversionException):
                    self.page_title = "FileConversionException."
                    self._set_page_content(
                        f"# FileConversionException\n\nError converting '{path}' to Markdown."
                    )
                elif isinstance(e, FileNotFoundError):
                    self.page_title = "FileNotFoundError"
                    self._set_page_content(
                        f"# FileNotFoundError\n\nFile not found: {path}"
                    )
                else:
                    raise

    async def _fetch_local_dir(self, local_path: str) -> str:
        """
        Generate a Markdown table listing of a directory's contents.

        Args:
            local_path (str): Path to the directory to list

        Returns:
            str: A string containing a Markdown-formatted table with columns for name, size, and modification date of directory entries.
        """
        code = get_directory_listing_code(local_path)
        result = await self._code_executor.execute_code_blocks(
            [CodeBlock(code=code, language="python")],
            cancellation_token=CancellationToken(),
        )
        return result.output

    async def find_files(self, query: str) -> str:
        """
        Search for files matching the query in current directory and subdirectories.
        Returns up to 10 closest matches sorted by similarity score.

        Args:
            query (str): File name or pattern to search for. Supports wildcards.

        Returns:
            str: Markdown formatted string with search results
        """
        code = get_find_files_code(query)
        result = await self._code_executor.execute_code_blocks(
            [CodeBlock(code=code, language="python")],
            cancellation_token=CancellationToken(),
        )
        return result.output


def _get_markitdown_exceptions():
    try:
        from markitdown import UnsupportedFormatException, FileConversionException

        return UnsupportedFormatException, FileConversionException
    except ImportError:

        class _Dummy(Exception):
            pass

        return _Dummy, _Dummy
