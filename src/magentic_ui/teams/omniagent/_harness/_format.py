"""Tool output formatting and truncation.

``_render_plain()`` produces natural text inside ``<tool_response>``
tags, since our model expects raw text rather than a heredoc-style
serialization.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

MIN_LINES = 20  # stop trimming when fewer than this many lines remain


# ---------------------------------------------------------------------------
# Rendering — produces plain text inside ``<tool_response>`` tags.
# ---------------------------------------------------------------------------


def _render_plain(data: dict[str, Any]) -> str:
    """Render dict as natural plain text.

    Single-field dicts render as just the value (no key prefix).
    Multi-field dicts render as ``key: value`` lines, with multi-line
    values on the next line(s).
    """
    if len(data) == 1:
        return str(next(iter(data.values())))

    lines: list[str] = []
    for key, value in data.items():
        text = str(value)
        if "\n" in text:
            lines.append(f"{key}:")
            lines.append(text)
        else:
            lines.append(f"{key}: {text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# format_tool_output — formats a tool result dict into a string suitable for
# inclusion in <tool_response> tags, truncating large fields to fit ``budget``
# and spilling overflow to a file under ``outputs_dir``.
# ---------------------------------------------------------------------------


def format_tool_output(
    data: dict[str, Any],
    truncatable_fields: list[str],
    budget: int,
    outputs_dir: Path,
    to_guest_path: Callable[[Path], Path] = lambda p: p,
) -> str:
    """Render with spill-to-disk when serialized size exceeds the budget.

    If the result exceeds ``budget`` bytes, the first truncatable field is
    replaced by three entries:

    - ``{field}.head``  — first N lines (trimmed from middle until under budget)
    - ``{field}.tail``  — last N lines
    - ``{field}.file``  — guest path of the full content saved to disk

    Repeats until under budget or all truncatable fields are exhausted.
    A ``remarks`` field is appended when any spilling occurs.
    """
    for f in truncatable_fields:
        if f in data and not isinstance(data[f], str):
            raise TypeError(
                f"truncatable field {f!r} must be a str, got {type(data[f]).__name__}"
            )
    entries: list[tuple[str, Any]] = list(data.items())
    entry_keys = {k for k, _ in entries}
    to_spill = [f for f in truncatable_fields if f in entry_keys]
    spilled: list[str] = []

    while to_spill:
        serialized_size = len(_render_plain(dict(entries)).encode())
        if serialized_size <= budget:
            break
        field = to_spill.pop(0)

        new_entries: list[tuple[str, Any]] = []
        content: str | None = None
        for k, v in entries:
            if k == field:
                content = str(v)
                # --- Save full content to disk ---
                stem = f"{field}_{uuid.uuid4().hex[:12]}"
                path = outputs_dir / stem
                counter = 0
                while path.exists():
                    counter += 1
                    path = outputs_dir / f"{stem}_{counter}"
                outputs_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                guest_path = to_guest_path(path)

                # --- Trim middle lines to reduce serialized size ---
                lines = content.splitlines()
                excess = serialized_size - budget
                while excess > 0 and len(lines) > MIN_LINES:
                    removed = lines.pop(len(lines) // 2)
                    excess -= len(removed.encode()) + 1  # +1 for newline

                # --- Split into head/tail ---
                mid = len(lines) // 2
                new_entries.append((f"{field}.head", "\n".join(lines[:mid])))
                new_entries.append((f"{field}.tail", "\n".join(lines[mid:])))
                new_entries.append((f"{field}.file", str(guest_path)))
            else:
                new_entries.append((k, v))
        if content is not None:
            entries = new_entries
            spilled.append(field)

    if spilled:
        files = ", ".join(f"`{f}.file`" for f in spilled)
        entries.append(
            (
                "remarks",
                f"Some fields were too large and have been truncated. Full contents were saved to disk. "
                f"See {files} for the paths. To avoid this in the future, modify your tool call to "
                f"limit the output size.",
            )
        )

    return _render_plain(dict(entries))
