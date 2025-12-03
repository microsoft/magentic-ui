"""Sandbox-side read tool — reads a file and returns its contents as JSON.

Called as: python3 -m magui_tools.read '{"file_path": "/path/to/file"}'

Returns JSON to stdout:
  {"content": "...", "total_lines": N}
  {"content": "...", "total_lines": N, "converted": true}   (binary docs)
  {"error": "..."}                                           (on failure)

Behavior:
- Rejects images and directories
- Converts binary documents (.docx, .pdf, .xlsx, .pptx) via MarkItDown
- Returns raw text content for the host to format through viewport
"""

import json
import subprocess
import sys
from pathlib import Path

from ._path_utils import is_restricted


def _detect_mime(file_path: str) -> str:
    """Detect MIME type using file(1)."""
    try:
        result = subprocess.run(
            ["file", "-b", "--mime-type", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "application/octet-stream"


def _count_lines(content: str) -> int:
    """Count lines (matches awk 'END {print NR}')."""
    if not content:
        return 0
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def main() -> None:
    args = json.loads(sys.argv[1])
    file_path = args["file_path"]

    path = Path(file_path).expanduser()
    file_path = str(path)  # use expanded path for all downstream operations
    if is_restricted(path):
        print(
            json.dumps({"error": f"Path {file_path} is restricted (harness internal)"})
        )
        sys.exit(1)
    if not path.exists():
        print(json.dumps({"error": f"File {file_path} not found"}))
        sys.exit(1)

    if path.is_dir():
        print(
            json.dumps(
                {
                    "error": (
                        f"Error: {file_path} is a directory. "
                        "You can only open files. Use cd or ls to navigate directories."
                    )
                }
            )
        )
        sys.exit(1)

    # Empty files — return immediately (file(1) returns inode/x-empty)
    if path.stat().st_size == 0:
        print(json.dumps({"content": "", "total_lines": 0}))
        return

    mime = _detect_mime(file_path)

    # Reject images
    if mime.startswith("image"):
        print(
            json.dumps(
                {
                    "error": (
                        f"Error: {file_path} is an image file. "
                        "Current environment does not support image viewing."
                    )
                }
            )
        )
        sys.exit(1)

    # Text files — read directly
    if mime.startswith("text/") or mime in ("application/json", "application/xml"):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")
        print(json.dumps({"content": content, "total_lines": _count_lines(content)}))
        return

    # Binary documents — convert via MarkItDown
    try:
        from markitdown import MarkItDown  # pyright: ignore[reportMissingImports,reportUnknownVariableType]

        raw = MarkItDown().convert(file_path).text_content  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
        md_text: str = raw if isinstance(raw, str) else ""
        print(
            json.dumps(
                {
                    "content": md_text,
                    "total_lines": _count_lines(md_text),
                    "converted": True,
                }
            )
        )
    except Exception as e:
        print(json.dumps({"error": f"Cannot read {file_path}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
