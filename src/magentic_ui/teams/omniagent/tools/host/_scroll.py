"""Host-side scroll and goto tools — updates viewport, re-reads file, formats output."""

from __future__ import annotations

from dataclasses import dataclass

from ._state import ViewportState, SCROLL_WARNING, format_viewport


@dataclass
class ScrollOutput:
    """Result of a scroll or goto operation."""

    content: str
    total_lines: int
    error: str | None = None

    def to_output(self, state: ViewportState) -> str:
        if self.error is not None:
            return self.error
        viewport = format_viewport(state, self.content)
        if state.scroll_count >= 3:
            return viewport + SCROLL_WARNING
        return viewport
