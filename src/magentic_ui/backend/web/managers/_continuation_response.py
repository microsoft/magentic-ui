"""Continuation-response helpers for :class:`WebSocketManager`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .connection import WebSocketManager


def normalize_continuation_decision(response: str) -> str:
    """Map a free-text continuation reply to ``"continue"`` or ``"stop"``."""
    normalized = response.strip().lower().rstrip(".!,")
    return "continue" if normalized in ("yes", "continue") else "stop"


async def save_continuation_response(
    manager: "WebSocketManager",
    run_id: int,
    content: str,
    decision: str,
) -> None:
    """Broadcast and persist a continuation-response marker message."""
    msg: dict[str, Any] = {
        "source": "user",
        "content": content,
        "type": "continuation_response",
        "metadata": {"type": "continuation_response", "decision": decision},
    }
    await manager._send_message(  # pyright: ignore[reportPrivateUsage]
        run_id, {"type": "message", "data": msg}
    )
    await manager._save_message(run_id, msg)  # pyright: ignore[reportPrivateUsage]
