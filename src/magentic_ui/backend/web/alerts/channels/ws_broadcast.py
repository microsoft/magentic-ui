"""Broadcast alerts to connected UI WebSocket clients."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from ..types import Alert, AlertChannel

logger = logging.getLogger(__name__)

#: Callable used by :class:`WebSocketBroadcastChannel` to fan a message out to
#: all connected UI clients. Typically bound to ``WebSocketManager.broadcast``.
BroadcastCallable = Callable[[Dict[str, Any]], Awaitable[None]]


class WebSocketBroadcastChannel(AlertChannel):
    """Pushes an ``alert`` event to every connected UI WebSocket.

    The :class:`WebSocketManager` owns the active connections; this channel
    only needs a callable that will asynchronously send a payload to all of
    them.
    """

    name = "ws_broadcast"

    def __init__(
        self,
        broadcast: BroadcastCallable,
        *,
        include_task_summary: bool = False,
    ) -> None:
        self._broadcast = broadcast
        self._include_task_summary = include_task_summary

    async def send(self, alert: Alert) -> None:
        payload: Dict[str, Any] = {
            "type": "alert",
            "data": alert.to_public_dict(
                include_task_summary=self._include_task_summary
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._broadcast(payload)
