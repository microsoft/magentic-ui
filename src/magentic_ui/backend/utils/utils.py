import os
from pathlib import Path
from typing import Any, List, Dict, Iterable, TypedDict
import json
from loguru import logger


class ModifiedFileInfo(TypedDict):
    """File info returned by get_modified_files()."""

    path: str
    short_path: str
    name: str
    extension: str
    type: str
    timestamp: float


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal.

    Strips directory components (including Windows-style backslash paths),
    rejects dangerous patterns.
    Raises ValueError for invalid filenames.
    """
    # Normalize Windows backslashes so os.path.basename strips all directory components
    # (e.g., browsers may send "C:\\fakepath\\file.txt")
    normalized = filename.replace("\\", "/")
    safe = os.path.basename(normalized)
    if not safe or safe in (".", "..") or safe.startswith("."):
        raise ValueError(f"Invalid filename: {filename!r}")
    return safe


def find_available_filename(
    directory: Path,
    filename: str,
    reserved: Iterable[str] = (),
) -> str:
    """Return ``filename``, or an ``_N``-suffixed variant if it collides on
    disk or with ``reserved``.

    ``filename`` must already be sanitized (no directory components).
    The suffix avoids spaces/parentheses to stay shell- and path-safe.
    """
    reserved_set = set(reserved)

    if not (directory / filename).exists() and filename not in reserved_set:
        return filename

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = f"{stem}_{counter}{suffix}"
        if not (directory / candidate).exists() and candidate not in reserved_set:
            return candidate
        counter += 1


def get_file_type(file_path: str) -> str:
    """
    Get file type determined by the file extension. If the file extension is not
    recognized, 'unknown' will be used as the file type.

    Args:
        file_path (str): The path to the file to be serialized.
    Returns:
        str: A string containing the file type.
    """

    # Extended list of file extensions for code and text files
    CODE_EXTENSIONS = {
        ".py",
        ".python",
        ".js",
        ".jsx",
        ".java",
        ".c",
        ".cpp",
        ".cs",
        ".ts",
        ".tsx",
        ".html",
        ".css",
        ".scss",
        ".less",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".md",
        ".rst",
        ".tex",
        ".sh",
        ".bat",
        ".ps1",
        ".php",
        ".rb",
        ".go",
        ".swift",
        ".kt",
        ".hs",
        ".scala",
        ".lua",
        ".pl",
        ".sql",
        ".config",
    }

    # Supported spreadsheet extensions
    CSV_EXTENSIONS = {".csv", ".xlsx"}

    # Supported image extensions
    IMAGE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".tiff",
        ".svg",
        ".webp",
    }
    # Supported (web) video extensions
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".avi", ".wmv"}

    # Supported PDF extension
    PDF_EXTENSION = ".pdf"

    # Determine the file extension
    _, file_extension = os.path.splitext(file_path)

    # Determine the file type based on the extension
    if file_extension in CODE_EXTENSIONS:
        file_type = "code"
    elif file_extension in CSV_EXTENSIONS:
        file_type = "csv"
    elif file_extension in IMAGE_EXTENSIONS:
        file_type = "image"
    elif file_extension == PDF_EXTENSION:
        file_type = "pdf"
    elif file_extension in VIDEO_EXTENSIONS:
        file_type = "video"
    else:
        file_type = "unknown"

    return file_type


def get_modified_files(
    start_timestamp: float, end_timestamp: float, source_dir: str
) -> List[ModifiedFileInfo]:
    """
    Identify files from source_dir that were modified within a specified timestamp range.
    The function excludes files with certain file extensions and names.

    Args:
        start_timestamp (float): The floating-point number representing the start timestamp to filter modified files.
        end_timestamp (float): The floating-point number representing the end timestamp to filter modified files.
        source_dir (str): The directory to search for modified files.
    Returns:
        List[ModifiedFileInfo]: A list of typed dicts with file path, name, extension, type, and timestamp.
            Files with extensions "*.pyc", "*.cache" and names "__pycache__", "__init__.py" are ignored.
    """
    modified_files: List[ModifiedFileInfo] = []
    ignore_extensions = {".pyc", ".cache"}
    # .agent holds agent-internal output (transcripts, traces, tool outputs)
    # that shouldn't surface as user-visible generated files in the UI.
    ignore_files = {"__pycache__", "__init__.py", ".agent"}

    # Walk through the directory tree
    for root, dirs, files in os.walk(source_dir):
        # Update directories and files to exclude those to be ignored
        dirs[:] = [d for d in dirs if d not in ignore_files]
        files[:] = [
            f
            for f in files
            if f not in ignore_files and os.path.splitext(f)[1] not in ignore_extensions
        ]

        for file in files:
            file_path = os.path.join(root, file)
            file_mtime = os.path.getmtime(file_path)

            # Verify if the file was modified within the given timestamp range
            if start_timestamp <= file_mtime <= end_timestamp:
                file_relative_path = (
                    "files/user" + file_path.split("files/user", 1)[1]
                    if "files/user" in file_path
                    else ""
                )
                file_type = get_file_type(file_path)

                file_dict: ModifiedFileInfo = {
                    "path": file_relative_path,
                    "short_path": file_relative_path,
                    "name": os.path.basename(file),
                    # Remove the dot
                    "extension": os.path.splitext(file)[1].lstrip("."),
                    "type": file_type,
                    "timestamp": file_mtime,
                }
                modified_files.append(file_dict)

    # Sort the modified files by extension
    modified_files.sort(key=lambda x: x["extension"])
    return modified_files


class ConstructTaskResult(TypedDict):
    """Return type for construct_task()."""

    agent_task: str  # Task string with file references (for the agent)
    attached_files: List[Dict[str, Any]]  # Raw attached-file dicts (for in-process use)
    attached_files_json: str  # JSON string of attached file metadata (for DB/WS)


def construct_task(
    query: str,
    files: List[Dict[str, Any]] | None = None,
) -> ConstructTaskResult:
    """Augment a task string with reference lines for uploaded files and return the attached-file metadata."""
    empty_result: ConstructTaskResult = {
        "agent_task": query,
        "attached_files": [],
        "attached_files_json": json.dumps([]),
    }
    if not files:
        return empty_result

    extra_lines: List[str] = []
    attached_files: List[Dict[str, Any]] = []

    for f in files:
        raw_name = f.get("name", "unknown.file")
        # Ensure name is a string before sanitizing to avoid TypeError
        name = raw_name if isinstance(raw_name, str) else "unknown.file"
        try:
            name = sanitize_filename(name)
        except (ValueError, TypeError):
            logger.warning(f"Skipping file with invalid name: {raw_name!r}")
            continue

        if f.get("uploaded") and f.get("path"):
            extra_lines.append(
                f"Attached file: {name} — newly uploaded by the user, "
                f"saved at ./{name} in your current working directory. "
                f"Open it directly to see what the user is referring to."
            )
            attached_files.append(
                {
                    "name": name,
                    "type": f.get("type", "file"),
                    "path": f["path"],
                    "uploaded": True,
                }
            )

    agent_task = query + "\n\n" + "\n".join(extra_lines) if extra_lines else query
    return {
        "agent_task": agent_task,
        "attached_files": attached_files,
        "attached_files_json": json.dumps(attached_files),
    }
