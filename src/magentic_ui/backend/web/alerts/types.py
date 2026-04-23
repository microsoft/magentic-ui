"""Core types for the alerting subsystem."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class AlertReason(str, Enum):
    """Why an alert is being fired for a run."""

    # Terminal failure reported by the run loop.
    ERROR = "error"
    # Run has been ``ACTIVE`` but produced no messages for too long.
    STUCK_INACTIVITY = "stuck_inactivity"
    # Run stayed in ``CREATED`` without being picked up by a worker.
    START_TIMEOUT = "start_timeout"
    # Run has been ``AWAITING_INPUT`` beyond the configured window.
    AWAITING_INPUT_TIMEOUT = "awaiting_input_timeout"
    # Run exceeded configured orchestrator step / replan ceiling.
    STEP_LIMIT_EXCEEDED = "step_limit_exceeded"
    # Client WebSocket disconnected while the run was still ``ACTIVE``.
    CLIENT_DISCONNECTED = "client_disconnected"


@dataclass
class Alert:
    """A single alert event emitted about a run.

    ``task_summary`` is an opt-in, short, redacted description of the task —
    kept off by default so that sensitive content is not leaked to external
    channels. Use :meth:`to_public_dict` to serialize.
    """

    run_id: int
    reason: AlertReason
    status: str
    session_id: Optional[int] = None
    user_id: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    error_message: Optional[str] = None
    task_summary: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_public_dict(self, include_task_summary: bool = False) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict suitable for broadcasting.

        ``task_summary`` and ``error_message`` are excluded by default to avoid
        leaking potentially sensitive task content to external channels.
        """

        def _iso(value: Optional[datetime]) -> Optional[str]:
            return value.isoformat() if value is not None else None

        payload: Dict[str, Any] = {
            "run_id": self.run_id,
            "reason": self.reason.value,
            "status": self.status,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "last_activity_at": _iso(self.last_activity_at),
            "created_at": _iso(self.created_at),
        }
        if include_task_summary:
            payload["task_summary"] = self.task_summary
            payload["error_message"] = self.error_message
        return payload


class AlertChannel(abc.ABC):
    """Base class for alert delivery channels.

    Implementations must be safe to call concurrently and must never raise
    out of :meth:`send` — the dispatcher logs and swallows any error so that a
    misbehaving channel cannot take down a run.
    """

    #: Human-readable name used for logging and in ``delivered_channels``.
    name: str = "base"

    @abc.abstractmethod
    async def send(self, alert: Alert) -> None:  # pragma: no cover - interface
        """Deliver ``alert`` through this channel."""
        raise NotImplementedError
