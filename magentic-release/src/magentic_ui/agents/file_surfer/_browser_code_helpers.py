import inspect
from typing import Callable, List, Tuple


def _validate_path_impl() -> Callable[[str], None]:
    """The actual implementation of path validation"""
    import os

    def validate(path: str) -> None:
        if path == ".":
            print("true")
        else:
            print(os.path.exists(path))

    return validate


def _check_is_dir_impl() -> Callable[[str], None]:
    """The actual implementation of directory checking"""
    import os

    def check(path: str) -> None:
        if path == ".":
            print("true")
            return
        else:
            print(os.path.isdir(path))

    return check


def _convert_file_impl() -> Callable[[str], None]:
    """The actual implementation of file conversion"""
    from markitdown import MarkItDown

    def convert(path: str) -> None:
        converter = MarkItDown()
        result = converter.convert_local(path)
        print("TITLE:" + (result.title or ""))
        print("CONTENT:" + result.text_content)

    return convert


def _directory_listing_impl() -> Callable[[str], None]:
    """The actual implementation of directory listing"""
    import os
    import datetime

    def list_directory(path: str) -> None:
        listing = """
| Name | Size | Date Modified |
| ---- | ---- | ------------- |
| .. (parent directory) | | |
"""
        for entry in os.listdir(path):
            size = ""
            full_path = os.path.join(path, entry)

            mtime = ""
            try:
                mtime = datetime.datetime.fromtimestamp(
                    os.path.getmtime(full_path)
                ).strftime("%Y-%m-%d %H:%M")
            except Exception as e:
                mtime = f"N/A: {type(e).__name__}"

            if os.path.isdir(full_path):
                entry = entry + os.path.sep
            else:
                try:
                    size = str(os.path.getsize(full_path))
                except Exception as e:
                    size = f"N/A: {type(e).__name__}"

            listing += f"| {entry} | {size} | {mtime} |\n"
        print(listing)

    return list_directory


def _find_files_impl() -> Callable[[str], None]:
    """The actual implementation of file finding"""
    import os
    from difflib import SequenceMatcher

    def find_files(query: str) -> None:
        import json

        ROOT_DIR = "."
        THRESHOLD = 0.2
        MAX_RESULTS = 20
        INCLUDE_DIRECTORIES = False

        matches: List[Tuple[str, float]] = []
        perfect_match = None

        for root, dirs, files in os.walk(ROOT_DIR):
            # Add both files and directories
            dirs[:] = [
                d for d in dirs if d not in ["node_modules", ".git", "__pycache__"]
            ]
            if INCLUDE_DIRECTORIES:
                items = files + dirs
            else:
                items = files
            for name in items:
                path = os.path.join(root, name)[2:]  # Remove ./ prefix

                # Check for exact matches first (case insensitive)
                if name.lower() == query.lower():
                    score = 1.0
                    perfect_match = path
                else:
                    # Calculate similarity score
                    score = SequenceMatcher(None, query.lower(), name.lower()).ratio()

                if score > THRESHOLD:  # Minimum similarity threshold
                    matches.append((path, score))

        # Sort by score and take top results
        matches.sort(key=lambda x: x[1], reverse=True)
        matches = matches[:MAX_RESULTS]

        result = {"matches": matches, "perfect_match": perfect_match}

        print(json.dumps(result))

    return find_files


# The template functions that generate the code to be executed
def get_path_validation_code(path: str) -> str:
    inner_func = inspect.getsource(_validate_path_impl()).split("def validate", 1)[1]
    return f"""
import os
def validate{inner_func}
validate('{path}')
"""


def get_is_dir_check_code(path: str) -> str:
    inner_func = inspect.getsource(_check_is_dir_impl()).split("def check", 1)[1]
    return f"""
import os
def check{inner_func}
check('{path}')
"""


def get_file_conversion_code(path: str) -> str:
    inner_func = inspect.getsource(_convert_file_impl()).split("def convert", 1)[1]
    return f"""
from markitdown import MarkItDown
def convert{inner_func}
convert('{path}')
"""


def get_directory_listing_code(local_path: str) -> str:
    inner_func = inspect.getsource(_directory_listing_impl()).split(
        "def list_directory", 1
    )[1]
    return f"""
import os
import datetime
def list_directory{inner_func}
list_directory('{local_path}')
"""


def get_find_files_code(query: str) -> str:
    inner_func = inspect.getsource(_find_files_impl()).split("def find_files", 1)[1]
    return f"""
import os
from difflib import SequenceMatcher
def find_files{inner_func}
find_files('{query}')
"""
