"""Tests for the max-rounds continuation flow on the connection layer.

Covers two surfaces:

- ``handle_continuation_response`` (button channel): maps the structured
  ``continue`` / ``stop`` decision to the agent's ``yes`` / ``no``
  sentinel and emits a ``continuation_response`` marker message.
- ``handle_input_response`` while the team manager is awaiting a
  continuation (NL channel): only ``yes`` / ``continue`` count as
  continue; everything else maps to stop. The user's typed text is
  NOT echoed as a separate user bubble — same shape as the approval
  NL flow — and a ``continuation_response`` marker is persisted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.backend.web.managers import connection as connection_module
from magentic_ui.backend.web.managers.connection import WebSocketManager


def _make_ws_manager(
    team_manager: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[WebSocketManager, AsyncMock]:
    """Build a WebSocketManager with stubbed I/O and ``save_continuation_response`` patched.

    Returns the manager and the AsyncMock that replaces the
    ``save_continuation_response`` helper imported into ``connection``.
    """
    mgr = WebSocketManager.__new__(WebSocketManager)
    mgr._team_managers = {1: team_manager}
    mgr._send_message = AsyncMock()
    mgr._save_message = AsyncMock()
    mgr._save_approval_response = AsyncMock()
    mgr._set_active_if_awaiting = AsyncMock()
    mgr._get_run = AsyncMock(return_value=None)
    save_helper = AsyncMock()
    monkeypatch.setattr(connection_module, "save_continuation_response", save_helper)
    return mgr, save_helper


def _continuation_pending_team() -> MagicMock:
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = True
    team.has_pending_input = True
    team.provide_input = MagicMock()
    return team


# ---------------------------------------------------------------------------
# Structured (button) channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_continuation_response_continue_maps_to_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = _continuation_pending_team()
    mgr, save_helper = _make_ws_manager(team, monkeypatch)

    await mgr.handle_continuation_response(1, "continue")

    save_helper.assert_awaited_once_with(mgr, 1, "continue", "continue")
    team.provide_input.assert_called_once_with("yes")
    mgr._set_active_if_awaiting.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_handle_continuation_response_stop_maps_to_no(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = _continuation_pending_team()
    mgr, save_helper = _make_ws_manager(team, monkeypatch)

    await mgr.handle_continuation_response(1, "stop")

    save_helper.assert_awaited_once_with(mgr, 1, "stop", "stop")
    team.provide_input.assert_called_once_with("no")
    mgr._set_active_if_awaiting.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_handle_continuation_response_inactive_run_is_logged() -> None:
    mgr = WebSocketManager.__new__(WebSocketManager)
    mgr._team_managers = {}
    # No spies needed — just verify the call returns without raising.
    await mgr.handle_continuation_response(99, "continue")


# ---------------------------------------------------------------------------
# NL channel (user typed in chat input while waiting on a continuation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,decision,sentinel",
    [
        ("yes", "continue", "yes"),
        ("Yes", "continue", "yes"),
        ("yes.", "continue", "yes"),
        ("continue", "continue", "yes"),
        ("no", "stop", "no"),
        ("stop", "stop", "no"),
        ("", "stop", "no"),
        ("y", "stop", "no"),  # bare "y" no longer counts as continue
        ("can you also visit example.com?", "stop", "no"),
    ],
)
@pytest.mark.asyncio
async def test_handle_input_response_continuation_nl_parsing(
    raw: str, decision: str, sentinel: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = _continuation_pending_team()
    mgr, save_helper = _make_ws_manager(team, monkeypatch)

    await mgr.handle_input_response(1, raw)

    save_helper.assert_awaited_once_with(mgr, 1, raw, decision)
    team.provide_input.assert_called_once_with(sentinel)
    mgr._set_active_if_awaiting.assert_awaited_once_with(1)
    # NL continuation must NOT echo a user bubble (mirrors approval NL flow).
    mgr._send_message.assert_not_awaited()
    mgr._save_message.assert_not_awaited()
