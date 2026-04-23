"""Deliver alerts as a POST to an arbitrary webhook URL."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..types import Alert, AlertChannel

logger = logging.getLogger(__name__)


class WebhookChannel(AlertChannel):
    """Posts the alert payload as JSON to ``url``.

    Uses ``aiohttp`` if available at call time. This is imported lazily so
    that the rest of the backend does not pay the cost when no webhook is
    configured and so that environments without ``aiohttp`` can still import
    the module.
    """

    name = "webhook"

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 5.0,
        include_task_summary: bool = False,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._url = url
        self._timeout = timeout_seconds
        self._include_task_summary = include_task_summary
        self._headers = dict(headers) if headers else None

    def _payload(self, alert: Alert) -> Dict[str, Any]:
        return {
            "type": "alert",
            "data": alert.to_public_dict(
                include_task_summary=self._include_task_summary
            ),
        }

    async def send(self, alert: Alert) -> None:
        try:
            import aiohttp  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "aiohttp is not installed; cannot deliver webhook alert for "
                "run %s",
                alert.run_id,
            )
            return

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self._url, json=self._payload(alert), headers=self._headers
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(
                        f"Webhook responded {response.status}: {body[:200]}"
                    )
