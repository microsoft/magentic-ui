"""Background monitor that detects stuck runs and fires alerts.

The monitor periodically queries the database for runs in a non-terminal
state and compares their ``updated_at`` timestamp (or last message timestamp,
when available) against configurable thresholds. When a threshold is crossed
it produces an :class:`~..alerts.types.Alert` and hands it to the
:class:`~..alerts.dispatcher.AlertDispatcher`.

The module is designed to be dependency-free of FastAPI so it can be unit
tested with an in-memory fake database and an injectable clock.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, List, Optional

from ...datamodel import Run, RunStatus
from ..alerts import Alert, AlertDispatcher, AlertReason

logger = logging.getLogger(__name__)


@dataclass
class AlertThresholds:
    """Thresholds controlling when a run is considered stuck.

    All values are in seconds. ``None`` disables the corresponding rule.
    """

    #: No message produced while ``ACTIVE`` for this long -> stuck.
    stuck_inactivity_seconds: Optional[int] = 120
    #: Still ``CREATED`` after this long -> startup failure.
    start_timeout_seconds: Optional[int] = 60
    #: ``AWAITING_INPUT`` longer than this -> user timed out.
    awaiting_input_seconds: Optional[int] = 600
    #: How often the monitor loop runs.
    poll_interval_seconds: int = 30


#: Non-terminal run states the monitor watches.
_WATCHED_STATUSES = (
    RunStatus.CREATED,
    RunStatus.ACTIVE,
    RunStatus.AWAITING_INPUT,
    RunStatus.PAUSED,
)


ClockFn = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Return ``value`` as an aware UTC datetime, or ``None``."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _last_activity(run: Run) -> Optional[datetime]:
    """Best-effort timestamp of the last observable activity on ``run``.

    Falls back through the most recent message timestamp, ``updated_at``, and
    ``created_at`` so that the monitor still works for runs that have never
    produced any messages.
    """
    messages: Iterable[Any] = run.messages or []
    latest: Optional[datetime] = None
    for message in messages:
        ts: Any = None
        # Messages may be SQLModel instances or plain dicts depending on how
        # they were loaded; support both cleanly.
        if isinstance(message, dict):
            ts = message.get("updated_at") or message.get("created_at")
        else:
            ts = getattr(message, "updated_at", None) or getattr(
                message, "created_at", None
            )
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = None
        if isinstance(ts, datetime):
            ts = _as_utc(ts)
            if latest is None or (ts is not None and ts > latest):
                latest = ts
    return latest or _as_utc(run.updated_at) or _as_utc(run.created_at)


def classify_run(
    run: Run,
    thresholds: AlertThresholds,
    now: datetime,
) -> Optional[AlertReason]:
    """Return an :class:`AlertReason` if ``run`` is stuck, else ``None``.

    Pure function — no I/O — so it is easy to unit-test with a fake clock.
    """
    status = run.status
    if status not in _WATCHED_STATUSES:
        return None

    last_activity = _last_activity(run) or now
    age = (now - last_activity).total_seconds()

    if (
        status == RunStatus.ACTIVE
        and thresholds.stuck_inactivity_seconds is not None
        and age >= thresholds.stuck_inactivity_seconds
    ):
        return AlertReason.STUCK_INACTIVITY
    if (
        status == RunStatus.CREATED
        and thresholds.start_timeout_seconds is not None
        and age >= thresholds.start_timeout_seconds
    ):
        return AlertReason.START_TIMEOUT
    if (
        status == RunStatus.AWAITING_INPUT
        and thresholds.awaiting_input_seconds is not None
        and age >= thresholds.awaiting_input_seconds
    ):
        return AlertReason.AWAITING_INPUT_TIMEOUT
    return None


class AlertMonitor:
    """Periodic stuck-run detector.

    Usage::

        monitor = AlertMonitor(db_manager, dispatcher, thresholds)
        await monitor.start()
        ...
        await monitor.stop()
    """

    def __init__(
        self,
        db_manager: Any,
        dispatcher: AlertDispatcher,
        thresholds: Optional[AlertThresholds] = None,
        *,
        clock: ClockFn = _default_clock,
    ) -> None:
        self._db = db_manager
        self._dispatcher = dispatcher
        self._thresholds = thresholds or AlertThresholds()
        self._clock = clock
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "AlertMonitor started (poll_interval=%ss)",
            self._thresholds.poll_interval_seconds,
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                self._task.cancel()
            finally:
                self._task = None
        logger.info("AlertMonitor stopped")

    async def _run_loop(self) -> None:
        interval = max(1, int(self._thresholds.poll_interval_seconds))
        while not self._stop_event.is_set():
            try:
                await self.check_once()
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                logger.exception("AlertMonitor tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def check_once(self) -> List[Alert]:
        """Run one inspection pass and return the alerts that were produced.

        Exposed so tests can drive the monitor deterministically without
        starting the background task.
        """
        runs = self._load_watched_runs()
        now = self._clock()
        produced: List[Alert] = []
        for run in runs:
            reason = classify_run(run, self._thresholds, now)
            if reason is None:
                continue
            if run.id is None:
                # A watched run without a primary key is a data-integrity
                # issue; log and skip rather than alert with a sentinel.
                logger.warning(
                    "Skipping %s alert for a %s run with no id",
                    reason.value,
                    run.status,
                )
                continue
            alert = Alert(
                run_id=run.id,
                reason=reason,
                status=str(run.status.value if hasattr(run.status, "value") else run.status),
                session_id=getattr(run, "session_id", None),
                user_id=getattr(run, "user_id", None),
                last_activity_at=_last_activity(run),
                error_message=getattr(run, "error_message", None),
            )
            delivered = await self._dispatcher.dispatch(alert)
            if delivered:
                produced.append(alert)
        return produced

    def _load_watched_runs(self) -> List[Run]:
        runs: List[Run] = []
        for status in _WATCHED_STATUSES:
            try:
                response = self._db.get(
                    model_class=Run,
                    filters={"status": status},
                    return_json=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "AlertMonitor failed to query runs with status %s: %s",
                    status,
                    exc,
                )
                continue
            if getattr(response, "status", False) and response.data:
                runs.extend(response.data)
        return runs
