"""Multi-channel alert dispatcher.

The dispatcher fans an :class:`.types.Alert` out to every registered
:class:`.types.AlertChannel`, suppresses per-channel exceptions, and keeps an
in-memory deduplication set keyed by ``(run_id, reason)`` so that the periodic
monitor does not re-alert on every tick.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List, Set, Tuple

from .types import Alert, AlertChannel, AlertReason

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Fan alerts out to multiple channels with dedup and error isolation."""

    def __init__(self, channels: Iterable[AlertChannel] | None = None) -> None:
        self._channels: List[AlertChannel] = list(channels or [])
        self._sent_keys: Set[Tuple[int, AlertReason]] = set()
        self._lock = asyncio.Lock()

    def register(self, channel: AlertChannel) -> None:
        """Add ``channel`` to the dispatcher."""
        self._channels.append(channel)

    @property
    def channels(self) -> List[AlertChannel]:
        return list(self._channels)

    def reset_dedup(self, run_id: int) -> None:
        """Forget any alerts previously sent for ``run_id``.

        Call this whenever a run transitions into a new observable state
        (e.g. receives a new message or moves back to ``ACTIVE``) so that a
        subsequent stall produces a fresh alert.
        """
        self._sent_keys = {
            (rid, reason) for (rid, reason) in self._sent_keys if rid != run_id
        }

    async def dispatch(self, alert: Alert, *, dedup: bool = True) -> List[str]:
        """Send ``alert`` to every channel.

        Returns the list of channel names that delivered successfully. When
        ``dedup`` is true (the default) the same ``(run_id, reason)`` is only
        delivered once until :meth:`reset_dedup` is called for that run.
        """
        key = (alert.run_id, alert.reason)
        async with self._lock:
            if dedup and key in self._sent_keys:
                logger.debug(
                    "Suppressing duplicate alert for run %s reason %s",
                    alert.run_id,
                    alert.reason.value,
                )
                return []
            self._sent_keys.add(key)

        if not self._channels:
            logger.info(
                "Alert for run %s (%s) not delivered: no channels configured",
                alert.run_id,
                alert.reason.value,
            )
            return []

        delivered: List[str] = []
        results = await asyncio.gather(
            *[self._safe_send(channel, alert) for channel in self._channels],
            return_exceptions=False,
        )
        for channel, ok in zip(self._channels, results):
            if ok:
                delivered.append(channel.name)
        logger.info(
            "Dispatched alert for run %s (%s) to channels=%s",
            alert.run_id,
            alert.reason.value,
            delivered,
        )
        return delivered

    async def _safe_send(self, channel: AlertChannel, alert: Alert) -> bool:
        try:
            await channel.send(alert)
            return True
        except Exception as exc:  # noqa: BLE001 - isolate channel failures
            logger.warning(
                "Alert channel %s failed for run %s: %s",
                channel.name,
                alert.run_id,
                exc,
            )
            return False
