"""(De)serialize Fara LLMMessages for the session-level state file."""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image

from ._types import ImageObj, LLMMessage


def message_to_dict(msg: LLMMessage) -> dict[str, Any]:
    """Encode an LLMMessage to a JSON-serializable dict (images → base64 PNG)."""
    if isinstance(msg.content, str):
        content: str | list[dict[str, Any]] = msg.content
    else:
        parts: list[dict[str, Any]] = []
        for item in msg.content:
            if isinstance(item, ImageObj):
                parts.append({"type": "image_b64", "data": item.to_base64()})
            else:
                parts.append({"type": "text", "text": str(item)})
        content = parts
    return {"role": msg.role, "content": content, "metadata": msg.metadata}


def message_from_dict(d: dict[str, Any]) -> LLMMessage:
    """Inverse of :func:`message_to_dict`."""
    raw = d.get("content")
    content: str | list[str | ImageObj]
    if isinstance(raw, str):
        content = raw
    elif isinstance(raw, list):
        items: list[str | ImageObj] = []
        for part in raw:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_b64" and "data" in part:
                img = Image.open(io.BytesIO(base64.b64decode(part["data"])))
                items.append(ImageObj.from_pil(img))
            elif part.get("type") == "text":
                items.append(part.get("text", ""))
        content = items
    else:
        content = ""
    return LLMMessage(
        role=d.get("role", "user"),
        content=content,
        metadata=d.get("metadata"),
    )
