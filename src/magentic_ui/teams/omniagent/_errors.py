"""Error types for OmniAgent tool execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolCallError:
    """Wraps tool execution errors for feeding back to the LLM.

    All tool errors (parse errors, unknown tool, execution failures)
    are wrapped in this type and returned as ``<tool_response>`` text.
    The LLM sees the error and can self-correct.
    """

    error: str

    def to_output(self) -> str:
        return f"Error: {self.error}"
