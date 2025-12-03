"""Lightweight message types for OmniAgent conversation history.

Uses TypedDict so messages pass directly to the OpenAI API
with zero conversion, while still giving IDE autocomplete
and type-checker safety across our multi-layer stack.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Message(TypedDict):
    """Conversation message — passes directly to OpenAI chat completions API."""

    role: str  # "system", "user", "assistant"
    content: str | list[dict[str, Any]]  # text or multimodal content


def system_msg(content: str) -> Message:
    return {"role": "system", "content": content}


def user_msg(content: str) -> Message:
    return {"role": "user", "content": content}


def assistant_msg(content: str) -> Message:
    return {"role": "assistant", "content": content}
