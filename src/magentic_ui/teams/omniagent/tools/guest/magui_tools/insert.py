"""Sandbox-side insert tool — inserts lines into a file.

Called as: python3 -m magui_tools.insert '{"file_path": "...", "line": 0, "content": "..."}'

Inserts content after the given line number (0 = beginning of file).
Python files are linted with flake8 — if new syntax errors are introduced,
the insert is reverted and the errors are returned.

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
    line = args["line"]
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

    # Build insertion lines, ensuring each ends with newline
    new_lines = content.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    elif not new_lines:
        new_lines = ["\n"]

    # Splice: insert after lines[line]
    result = lines[:line] + new_lines + lines[line:]
    edited_text = "".join(result)

    # Lint Python files
    if file_path.endswith(".py"):
        from .lint import filter_new_errors, format_errors, run_flake8

        errors_before = run_flake8(file_path)
        path.write_text(edited_text, encoding="utf-8")
        errors_after = run_flake8(file_path)

        # For insert: edit_start = line+1, edit_end = line (empty window), new lines inserted
        new_errors = filter_new_errors(
            errors_before, errors_after, line + 1, line, len(new_lines)
        )
        if new_errors:
            # Revert
            path.write_text(original_text, encoding="utf-8")
            print(
                json.dumps(
                    {
                        "error": "Insert introduced new syntax error(s).",
                        "lint_errors": format_errors(new_errors),
                        "edited_content": edited_text,
                        "original_content": original_text,
                        "insert_after": line,
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
