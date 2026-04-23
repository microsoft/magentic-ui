"""Tests for the stuck-run alert monitor and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import pytest

from magentic_ui.backend.datamodel import Run, RunStatus
from magentic_ui.backend.web.alerts import Alert, AlertDispatcher, AlertReason
from magentic_ui.backend.web.alerts.types import AlertChannel
from magentic_ui.backend.web.managers.alert_monitor import (
    AlertMonitor,
    AlertThresholds,
    classify_run,
)


def _make_run(
    *,
    run_id: int,
    status: RunStatus,
    updated_at: datetime,
    created_at: Optional[datetime] = None,
) -> Run:
    run = Run(
        id=run_id,
        session_id=1,
        user_id="user@example.com",
        status=status,
    )
    # Bypass SQLModel validation for timestamps (server-side defaults).
    object.__setattr__(run, "updated_at", updated_at)
    object.__setattr__(run, "created_at", created_at or updated_at)
    return run


def test_classify_run_active_stuck():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run = _make_run(
        run_id=1,
        status=RunStatus.ACTIVE,
        updated_at=now - timedelta(seconds=300),
    )
    reason = classify_run(run, AlertThresholds(stuck_inactivity_seconds=120), now)
    assert reason is AlertReason.STUCK_INACTIVITY


def test_classify_run_active_not_stuck():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run = _make_run(
        run_id=1,
        status=RunStatus.ACTIVE,
        updated_at=now - timedelta(seconds=10),
    )
    assert classify_run(run, AlertThresholds(), now) is None


def test_classify_run_start_timeout():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run = _make_run(
        run_id=2,
        status=RunStatus.CREATED,
        updated_at=now - timedelta(seconds=120),
    )
    reason = classify_run(run, AlertThresholds(start_timeout_seconds=60), now)
    assert reason is AlertReason.START_TIMEOUT


def test_classify_run_awaiting_input_timeout():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run = _make_run(
        run_id=3,
        status=RunStatus.AWAITING_INPUT,
        updated_at=now - timedelta(seconds=1200),
    )
    reason = classify_run(
        run, AlertThresholds(awaiting_input_seconds=600), now
    )
    assert reason is AlertReason.AWAITING_INPUT_TIMEOUT


def test_classify_run_terminal_status_ignored():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run = _make_run(
        run_id=4,
        status=RunStatus.COMPLETE,
        updated_at=now - timedelta(seconds=99999),
    )
    assert classify_run(run, AlertThresholds(), now) is None


def test_classify_run_disabled_rule():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run = _make_run(
        run_id=5,
        status=RunStatus.ACTIVE,
        updated_at=now - timedelta(seconds=99999),
    )
    # stuck_inactivity_seconds=None disables the rule
    assert (
        classify_run(run, AlertThresholds(stuck_inactivity_seconds=None), now)
        is None
    )


class RecordingChannel(AlertChannel):
    name = "recording"

    def __init__(self) -> None:
        self.sent: List[Alert] = []

    async def send(self, alert: Alert) -> None:
        self.sent.append(alert)


class FailingChannel(AlertChannel):
    name = "failing"

    async def send(self, alert: Alert) -> None:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_dispatcher_delivers_and_dedups():
    recorder = RecordingChannel()
    dispatcher = AlertDispatcher([recorder])
    alert = Alert(
        run_id=1, reason=AlertReason.STUCK_INACTIVITY, status="active"
    )
    delivered = await dispatcher.dispatch(alert)
    assert delivered == ["recording"]
    # Same (run_id, reason) should be suppressed.
    assert await dispatcher.dispatch(alert) == []
    assert len(recorder.sent) == 1
    # Different reason for same run still delivers.
    other = Alert(run_id=1, reason=AlertReason.ERROR, status="error")
    assert await dispatcher.dispatch(other) == ["recording"]
    # reset_dedup re-enables alerts for that run.
    dispatcher.reset_dedup(1)
    assert await dispatcher.dispatch(alert) == ["recording"]


@pytest.mark.asyncio
async def test_dispatcher_isolates_channel_errors():
    recorder = RecordingChannel()
    dispatcher = AlertDispatcher([FailingChannel(), recorder])
    alert = Alert(run_id=2, reason=AlertReason.ERROR, status="error")
    delivered = await dispatcher.dispatch(alert)
    # Failing channel must not prevent the recorder from being called.
    assert delivered == ["recording"]
    assert len(recorder.sent) == 1


@dataclass
class FakeDBResponse:
    status: bool = True
    data: List[Any] = field(default_factory=list)


class FakeDB:
    def __init__(self, runs: List[Run]):
        self._runs = runs

    def get(self, *, model_class, filters, return_json: bool = False):
        return FakeDBResponse(
            status=True,
            data=[r for r in self._runs if r.status == filters["status"]],
        )


@pytest.mark.asyncio
async def test_alert_monitor_check_once_fires_expected_alerts():
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    runs = [
        _make_run(run_id=10, status=RunStatus.ACTIVE, updated_at=now - timedelta(seconds=300)),
        _make_run(run_id=11, status=RunStatus.ACTIVE, updated_at=now),
        _make_run(run_id=12, status=RunStatus.CREATED, updated_at=now - timedelta(seconds=120)),
        _make_run(run_id=13, status=RunStatus.COMPLETE, updated_at=now - timedelta(seconds=99999)),
    ]
    recorder = RecordingChannel()
    dispatcher = AlertDispatcher([recorder])
    monitor = AlertMonitor(
        db_manager=FakeDB(runs),
        dispatcher=dispatcher,
        thresholds=AlertThresholds(
            stuck_inactivity_seconds=120,
            start_timeout_seconds=60,
            awaiting_input_seconds=600,
            poll_interval_seconds=1,
        ),
        clock=lambda: now,
    )
    produced = await monitor.check_once()
    fired = {(a.run_id, a.reason) for a in produced}
    assert (10, AlertReason.STUCK_INACTIVITY) in fired
    assert (12, AlertReason.START_TIMEOUT) in fired
    # Not stuck / terminal runs must not alert.
    assert all(r_id != 11 for (r_id, _) in fired)
    assert all(r_id != 13 for (r_id, _) in fired)
    # A second pass is fully deduped.
    assert await monitor.check_once() == []
    assert len(recorder.sent) == 2


def test_alert_to_public_dict_excludes_sensitive_by_default():
    alert = Alert(
        run_id=7,
        reason=AlertReason.ERROR,
        status="error",
        error_message="internal error details",
        task_summary="private task description",
    )
    public = alert.to_public_dict()
    assert "error_message" not in public
    assert "task_summary" not in public
    full = alert.to_public_dict(include_task_summary=True)
    assert full["error_message"] == "internal error details"
    assert full["task_summary"] == "private task description"
