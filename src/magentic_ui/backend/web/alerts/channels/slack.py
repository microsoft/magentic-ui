"""Deliver alerts to a Slack-compatible incoming webhook."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..types import Alert
from .webhook import WebhookChannel


class SlackChannel(WebhookChannel):
    """Formats the alert as a Slack ``text`` payload and POSTs it.

    Works against any Slack-compatible incoming webhook (Slack, Microsoft
    Teams via an adapter, Mattermost, ...). Only the ``text`` field is sent;
    richer formatting can be added by subclassing if a deployment needs it.
    """

    name = "slack"

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 5.0,
        include_task_summary: bool = False,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(
            url,
            timeout_seconds=timeout_seconds,
            include_task_summary=include_task_summary,
            headers=headers,
        )

    def _payload(self, alert: Alert) -> Dict[str, Any]:
        data = alert.to_public_dict(
            include_task_summary=self._include_task_summary
        )
        lines = [
            f":warning: *Magentic-UI run alert*: `{alert.reason.value}`",
            f"run_id=`{alert.run_id}` status=`{alert.status}`",
        ]
        if data.get("session_id") is not None:
            lines.append(f"session_id=`{data['session_id']}`")
        if data.get("user_id"):
            lines.append(f"user=`{data['user_id']}`")
        if data.get("last_activity_at"):
            lines.append(f"last_activity=`{data['last_activity_at']}`")
        if self._include_task_summary and alert.error_message:
            lines.append(f"error: {alert.error_message}")
        return {"text": "\n".join(lines)}
