"""Tests that ``TeamManager._create_agent`` persists the resolved
``agent_mode`` onto the run row.

The frontend uses ``run.agent_mode`` as the authoritative source of truth
for distinguishing OmniAgent runs from FARA-only runs (e.g. to decide
whether the web_surfer's ``final_answer`` is the real final answer or an
intermediate hand-off). If this write breaks, runs render with the wrong
mode after the user changes Settings — which manifests as duplicated
"final answer" cards in the UI.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.backend.datamodel.db import Run, RunStatus
from magentic_ui.backend.teammanager.teammanager import TeamManager
from magentic_ui.magentic_ui_config import AgentMode


@pytest.mark.asyncio
async def test_create_agent_persists_agent_mode_on_run(tmp_path: Path) -> None:
    """When Settings has agent_mode=omniagent_only, the run row should be
    updated with that value the moment the agent is created."""

    # Settings row with model configs + agent_mode the test cares about.
    settings_config = {
        "agent_mode": AgentMode.OMNIAGENT_ONLY.value,
        "model_client_configs": {
            "orchestrator": {"provider": "stub", "config": {"model": "x"}},
            # No web_surfer needed for omniagent_only.
        },
    }
    settings_row = MagicMock()
    settings_row.config = settings_config

    settings_response = MagicMock()
    settings_response.status = True
    settings_response.data = [settings_row]

    upsert_response = MagicMock()
    upsert_response.status = True

    db_manager = MagicMock()
    db_manager.get.return_value = settings_response
    db_manager.upsert.return_value = upsert_response

    tm = TeamManager(app_dir=tmp_path, db_manager=db_manager)

    # Stub out the heavy `get_task_team` call — we only care about the
    # mode-resolution / persistence side effect.
    fake_agent = AsyncMock()
    monkey_target = "magentic_ui.backend.teammanager.teammanager.get_task_team"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(monkey_target, AsyncMock(return_value=fake_agent))

        run = Run(id=42, session_id=1, status=RunStatus.CREATED, user_id="u1")
        host_run_dir = tmp_path / "run-42"
        host_run_dir.mkdir()

        await tm._create_agent(host_run_dir=host_run_dir, run=run)

    # Run object updated in place.
    assert run.agent_mode == AgentMode.OMNIAGENT_ONLY.value
    # And the change was flushed to the DB.
    db_manager.upsert.assert_called_once()
    upserted = db_manager.upsert.call_args.args[0]
    assert upserted is run


@pytest.mark.asyncio
async def test_create_agent_does_not_break_when_run_is_none(tmp_path: Path) -> None:
    """Backward compatibility: callers that pass run=None (older code paths
    or tests) should still get a working agent and not raise."""

    settings_config = {
        "agent_mode": AgentMode.WEBSURFER_ONLY.value,
        "model_client_configs": {
            "web_surfer": {"provider": "stub", "config": {"model": "x"}},
        },
    }
    settings_row = MagicMock()
    settings_row.config = settings_config

    settings_response = MagicMock()
    settings_response.status = True
    settings_response.data = [settings_row]

    db_manager = MagicMock()
    db_manager.get.return_value = settings_response
    db_manager.upsert = MagicMock()

    tm = TeamManager(app_dir=tmp_path, db_manager=db_manager)

    fake_agent = AsyncMock()
    monkey_target = "magentic_ui.backend.teammanager.teammanager.get_task_team"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(monkey_target, AsyncMock(return_value=fake_agent))

        host_run_dir = tmp_path / "run-none"
        host_run_dir.mkdir()

        # Should not raise even without a run argument.
        await tm._create_agent(host_run_dir=host_run_dir, run=None)

    db_manager.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_create_agent_db_failure_does_not_block_creation(tmp_path: Path) -> None:
    """If persisting agent_mode fails (e.g. DB error), agent creation must
    still proceed — the run row simply lacks the column data, and the
    frontend falls back to its message-source heuristic."""

    settings_config = {
        "agent_mode": AgentMode.ALL.value,
        "model_client_configs": {
            "orchestrator": {"provider": "stub", "config": {"model": "x"}},
            "web_surfer": {"provider": "stub", "config": {"model": "x"}},
        },
    }
    settings_row = MagicMock()
    settings_row.config = settings_config

    settings_response = MagicMock()
    settings_response.status = True
    settings_response.data = [settings_row]

    db_manager = MagicMock()
    db_manager.get.return_value = settings_response
    db_manager.upsert.side_effect = RuntimeError("simulated db error")

    tm = TeamManager(app_dir=tmp_path, db_manager=db_manager)

    fake_agent = AsyncMock()
    monkey_target = "magentic_ui.backend.teammanager.teammanager.get_task_team"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(monkey_target, AsyncMock(return_value=fake_agent))

        run = Run(id=7, session_id=1, status=RunStatus.CREATED, user_id="u1")
        host_run_dir = tmp_path / "run-7"
        host_run_dir.mkdir()

        # Must not raise.
        agent = await tm._create_agent(host_run_dir=host_run_dir, run=run)

    assert agent is fake_agent
    # The persistence path must actually have been exercised — without this
    # the test would still pass if a future refactor silently dropped the
    # write, defeating the point of the failure-handling check.
    db_manager.upsert.assert_called_once()
    # And the in-memory ``run.agent_mode`` should have been reverted so the
    # caller can't accidentally observe a "persisted" state that isn't.
    assert run.agent_mode is None
