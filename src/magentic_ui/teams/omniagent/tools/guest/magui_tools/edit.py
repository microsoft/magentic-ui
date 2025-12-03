"""Sandbox-side edit tool — replaces lines in a file.

Called as: python3 -m magui_tools.edit '{"file_path": "...", "start_line": 1, "end_line": 2, "content": "..."}'

Replaces lines start_line through end_line (inclusive, 1-based) with content.
Python files are linted with flake8 — if new syntax errors are introduced,
the edit is reverted and the errors are returned.

Prints JSON to stdout:
  {"ok": true}
  {"error": "...", "lint_errors": "...", "edited_content": "...", "original_content": "..."}
  {"error": "..."}
"""

import json
import sys
from pathlib import Path

from ._path_utils import is_restricted


def main() -> None:
    args = json.loads(sys.argv[1])
    file_path = args["file_path"]
    start_line = args["start_line"]
    end_line = args["end_line"]
    content = args["content"]

    path = Path(file_path).expanduser()
    file_path = str(path)  # use expanded path for all downstream operations
    if is_restricted(path):
        print(
            json.dumps({"error": f"Path {file_path} is restricted (harness internal)"})
        )
        sys.exit(1)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)

    original_text = path.read_text(encoding="utf-8")
    lines = original_text.splitlines(keepends=True)

    # Build replacement lines, ensuring each ends with newline
    new_lines = content.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    elif not new_lines:
        new_lines = ["\n"]

    # Splice: replace lines[start_line-1:end_line] with new_lines
    result = lines[: start_line - 1] + new_lines + lines[end_line:]
    edited_text = "".join(result)

    # Lint Python files
    if file_path.endswith(".py"):
        from .lint import filter_new_errors, format_errors, run_flake8

        errors_before = run_flake8(file_path)
        path.write_text(edited_text, encoding="utf-8")
        errors_after = run_flake8(file_path)

        new_errors = filter_new_errors(
            errors_before, errors_after, start_line, end_line, len(new_lines)
        )
        if new_errors:
            # Revert
            path.write_text(original_text, encoding="utf-8")
            print(
                json.dumps(
                    {
                        "error": "Edit introduced new syntax error(s).",
                        "lint_errors": format_errors(new_errors),
                        "edited_content": edited_text,
                        "original_content": original_text,
                        "start_line": start_line,
                        "end_line": end_line,
                        "line_count": len(new_lines),
                    }
                )
            )
            sys.exit(1)
    else:
        path.write_text(edited_text, encoding="utf-8")

    print(json.dumps({"ok": True}))


if __name__ == "__main__":
    main()
