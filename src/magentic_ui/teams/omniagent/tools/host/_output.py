"""Tool output protocol — all tool outputs implement to_output(state)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ._state import ViewportState


class ToolOutput(Protocol):
    def to_output(self, state: ViewportState) -> str: ...
