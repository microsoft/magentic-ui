"""Host-side create tool — creates file via sandbox, opens it."""

from __future__ import annotations

from dataclasses import dataclass

from ._state import ViewportState, format_viewport


@dataclass
class CreateOutput:
    """Result of creating a file."""

    content: str
    total_lines: int
    error: str | None = None

    def to_output(self, state: ViewportState) -> str:
        if self.error is not None:
            return self.error
        return format_viewport(state, self.content)
