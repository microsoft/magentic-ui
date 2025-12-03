"""Viewport state and formatting for OmniAgent file-editing tools.

Viewport state is four variables: ``current_file``, ``current_line``,
``window``, ``overlap``.  Each tool mutates them, then calls
``format_viewport()`` to render the visible window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ViewportState:
    """Viewport state: current_file, current_line, window, overlap."""

    current_file: str | None = None
    current_line: int = 0
    window: int = 1000
    overlap: int = 2
    scroll_count: int = 0  # consecutive scroll count for warning


# ---------------------------------------------------------------------------
# Scroll warning
#
#   Warning shown after 3 consecutive scrolls.
# ---------------------------------------------------------------------------

SCROLL_WARNING = (
    "\nWARNING: Scrolling many times in a row is very inefficient.\n"
    "If you know what you are looking for, use `search_file <pattern>` instead.\n"
)


def increment_scroll(state: ViewportState) -> None:
    """Increment consecutive scroll count."""
    state.scroll_count += 1


def reset_scroll(state: ViewportState) -> None:
    """Reset consecutive scroll count (called by non-scroll tools)."""
    state.scroll_count = 0


# ---------------------------------------------------------------------------
# constrain_line
#
#   half_window = floor(WINDOW / 2)
#   CURRENT_LINE = min(CURRENT_LINE, max_line - half_window)
#   CURRENT_LINE = max(CURRENT_LINE, half_window)
# ---------------------------------------------------------------------------


def constrain_line(state: ViewportState, total_lines: int) -> None:
    """Clamp current_line into valid range.  Mutates *state* in place."""
    half_window = math.floor(state.window / 2)
    state.current_line = min(state.current_line, total_lines - half_window)
    state.current_line = max(state.current_line, half_window)


# ---------------------------------------------------------------------------
# format_viewport
#
#   lines_above = max(0, floor(CURRENT_LINE - WINDOW/2))
#   lines_below = max(0, round(total_lines - CURRENT_LINE - WINDOW/2))
#   head_n      = floor(max(CURRENT_LINE + WINDOW/2, WINDOW/2))
#   tail_n      = WINDOW
#   visible     = cat FILE | grep -n $ | head -n head_n | tail -n tail_n
# ---------------------------------------------------------------------------


def format_viewport(state: ViewportState, content: str) -> str:
    """Render the viewport."""
    if state.current_file is None:
        return "No file open. Use the open command first."

    lines = content.splitlines()
    total_lines = len(lines)

    # Header
    header = f"[File: {state.current_file} ({total_lines} lines total)]"

    # Above / below counts
    lines_above = max(0, math.floor(state.current_line - state.window / 2))
    # jq round = "round half away from zero"; Python round = banker's rounding.
    # Use floor(x + 0.5) to match jq's behavior.
    lines_below = max(
        0, math.floor(total_lines - state.current_line - state.window / 2 + 0.5)
    )

    # Visible line range (1-based)
    #   head -n head_n  →  keeps lines 1..head_n
    #   tail -n WINDOW  →  keeps last WINDOW of those
    head_n = math.floor(max(state.current_line + state.window / 2, state.window / 2))
    head_n = min(head_n, total_lines)  # head stops at EOF
    tail_n = state.window

    first_visible = max(1, head_n - tail_n + 1)
    last_visible = head_n

    # Build output
    parts: list[str] = [header]

    if lines_above > 0:
        parts.append(f"({lines_above} more lines above)")

    # grep -n $ format: "N:content"  (1-based, no padding)
    for i in range(first_visible - 1, last_visible):
        parts.append(f"{i + 1}:{lines[i]}")

    if lines_below > 0:
        parts.append(f"({lines_below} more lines below)")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# open() / goto() line-number computation
#
#   With line_number:
#     OFFSET = floor(WINDOW / 6)
#     CURRENT_LINE = max(floor(line_number + WINDOW/2 - OFFSET), 1)
#   Without:
#     CURRENT_LINE = WINDOW / 2
# ---------------------------------------------------------------------------


def compute_open_line(state: ViewportState, line_number: int | None = None) -> int:
    """Compute current_line for open/goto."""
    if line_number is None:
        return math.floor(state.window / 2)
    offset = math.floor(state.window / 6)
    return max(math.floor(line_number + state.window / 2 - offset), 1)


# ---------------------------------------------------------------------------
# scroll
#
#   scroll_down: CURRENT_LINE += WINDOW - OVERLAP
#   scroll_up:   CURRENT_LINE -= WINDOW - OVERLAP
# ---------------------------------------------------------------------------


def compute_scroll_down(state: ViewportState) -> int:
    """Compute CURRENT_LINE after scroll_down."""
    return state.current_line + state.window - state.overlap


def compute_scroll_up(state: ViewportState) -> int:
    """Compute CURRENT_LINE after scroll_up."""
    return state.current_line - state.window + state.overlap
