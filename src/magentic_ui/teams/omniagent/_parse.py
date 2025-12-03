"""Response parsing for OmniAgent.

Extracts thoughts, tool calls, and final answers from the model's raw
text response. OmniAgent uses text-based tool calls (JSON inside
``<tool_call>...</tool_call>`` tags) rather than native function calling,
so parsing happens here rather than at the API layer.

The model may emit multiple ``<tool_call>`` blocks per response. They
are returned as an ordered list of :class:`ToolCallBlock` items —
each block is either a successfully-parsed :class:`ParsedToolCall`
or a :class:`ParseError`. Preserving the original order lets the
agent loop interleave error feedback with valid tool results when the
model self-correct against the right block.
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedToolCall:
    """A successfully-parsed ``<tool_call>`` block."""

    call: dict[str, Any]


@dataclass(frozen=True)
class ParseError:
    """A ``<tool_call>`` block that failed to parse.

    ``message`` includes a ``block N:`` prefix so the caller can keep
    its feedback to the model concise (just ``Error parsing {message}``).
    """

    message: str


ToolCallBlock = ParsedToolCall | ParseError


class ParsedResponse(NamedTuple):
    """Result of parsing an LLM response."""

    thoughts: str
    tool_call_blocks: list[ToolCallBlock]
    answer: str | None


def parse_response(response: str) -> ParsedResponse:
    """Parse LLM response to extract thoughts, tool-call blocks, and answer.

    Returns:
        ParsedResponse(thoughts, tool_call_blocks, answer).

        ``answer`` wins over ``tool_call_blocks`` — when ``<answer>`` is
        present, ``tool_call_blocks`` is empty and the loop terminates.
    """
    answer = extract_answer(response)
    thoughts = _extract_thoughts(response)
    if answer is not None:
        return ParsedResponse(thoughts, [], answer)

    return ParsedResponse(thoughts, _extract_tool_call_blocks(response), None)


def extract_answer(response: str) -> str | None:
    """Extract content from <answer> tags."""
    open_tag, close_tag = "<answer>", "</answer>"
    if open_tag not in response:
        return None
    start = response.index(open_tag) + len(open_tag)
    if close_tag in response[start:]:
        end = response.index(close_tag, start)
        return response[start:end].strip()
    # No closing tag — use rest of text
    return response[start:].strip()


def _extract_thoughts(response: str) -> str:
    """Return text before the first structured tag."""
    thoughts = response
    for tag in ("<answer>", "<tool_call>"):
        if tag in thoughts:
            thoughts = thoughts.split(tag, 1)[0]
    return thoughts.strip()


def _extract_tool_call_blocks(response: str) -> list[ToolCallBlock]:
    """Iterate every ``<tool_call>...</tool_call>`` block in original order.

    Each block is parsed with ``json.loads``; on failure
    ``ast.literal_eval`` is tried as a fallback for single-quoted dicts.
    Per-block failures become :class:`ParseError` entries inline so the
    caller can interleave them with successful results — one malformed
    block does not invalidate the rest.
    """
    if "<tool_call>" not in response:
        return []

    blocks: list[ToolCallBlock] = []
    raw_blocks = response.split("<tool_call>")[1:]  # drop preamble
    for idx, raw in enumerate(raw_blocks):
        if "</tool_call>" not in raw:
            blocks.append(ParseError(f"block {idx}: missing closing </tool_call> tag"))
            continue
        text = raw.split("</tool_call>", 1)[0].strip()
        parsed = _parse_one(text)
        if isinstance(parsed, dict):
            blocks.append(ParsedToolCall(parsed))
        else:
            blocks.append(ParseError(f"block {idx}: {parsed}"))

    return blocks


def _parse_one(text: str) -> dict[str, Any] | str:
    """Parse a single tool-call JSON body. Returns dict on success, error message on failure."""
    value: Any
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError) as e:
            return f"invalid JSON and ast.literal_eval also failed: {e}"
    if not isinstance(value, dict):
        return f"expected object, got {type(value).__name__}"
    return value  # type: ignore[no-any-return]
