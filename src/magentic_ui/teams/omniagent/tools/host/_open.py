"""Host-side open tool — output type and formatting."""

from __future__ import annotations

from dataclasses import dataclass

from ._state import ViewportState, format_viewport


@dataclass
class OpenOutput:
    """Result of opening a file."""

    content: str
    total_lines: int
    error: str | None = None

    def to_output(self, state: ViewportState) -> str:
        if self.error is not None:
            return self.error
        return format_viewport(state, self.content)
