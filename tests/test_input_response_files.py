"""Tests for handle_input_response with mid-session file uploads (issue #291).

Covers:
- Files passed with input_response are validated, registered with the
  team manager via add_uploaded_files, and metadata is persisted on the
  saved/broadcast user message.
- Files passed alongside an approval-pending input are ignored with a warning.
- Plain text-only input_response (no files) keeps existing behavior unchanged.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.backend.web.managers.connection import WebSocketManager


def _make_ws_manager_with_team(
    team_manager: MagicMock,
    run: Any | None = None,
) -> WebSocketManager:
    """Build a WebSocketManager wired with a single team manager mock.

    Patches the I/O surface (`_send_message`, `_save_message`, `_get_run`,
    `_set_active_if_awaiting`, `_save_approval_response`) so we can assert
    on how `handle_input_response` orchestrates them without touching a
    real DB or socket.
    """
    mgr = WebSocketManager.__new__(WebSocketManager)
    mgr._team_managers = {1: team_manager}
    mgr._send_message = AsyncMock()
    mgr._save_message = AsyncMock()
    mgr._save_approval_response = AsyncMock()
    mgr._set_active_if_awaiting = AsyncMock()
    mgr._get_run = AsyncMock(return_value=run)
    return mgr


@pytest.mark.asyncio
async def test_input_response_with_files_registers_and_augments() -> None:
    """Files trigger add_uploaded_files registration, construct_task
    augmentation from the SERVER-VALIDATED safe refs (not raw client
    payload), and attached_files metadata on the saved message."""
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    # add_uploaded_files returns the server-validated safe refs in the
    # construct_task input shape — handle_input_response uses these
    # (not the raw client payload) to build attached_files_json so a
    # malicious client can't smuggle cross-tenant paths into chat metadata.
    team.add_uploaded_files = MagicMock(
        return_value=[
            {
                "name": "data.csv",
                "path": "files/user/u1/s1/1/data.csv",
                "type": "file",
                "uploaded": True,
            }
        ]
    )
    team.provide_input = MagicMock()
    run_obj = MagicMock(id=1, user_id="u1", session_id="s1")
    mgr = _make_ws_manager_with_team(team, run=run_obj)

    files = [
        {"name": "data.csv", "path": "files/user/u1/s1/1/data.csv", "uploaded": True},
    ]
    await mgr.handle_input_response(1, "please use this", files=files)

    # add_uploaded_files called with the raw client refs (filtered to dicts)
    team.add_uploaded_files.assert_called_once()
    call_args = team.add_uploaded_files.call_args
    raw_refs = call_args.args[0]
    assert [f["name"] for f in raw_refs] == ["data.csv"]
    assert call_args.kwargs.get("run") is run_obj

    # provide_input got the augmented response (with "Attached file:" line),
    # built from the server-validated safe refs.
    team.provide_input.assert_called_once()
    augmented = team.provide_input.call_args.args[0]
    assert "please use this" in augmented
    assert "Attached file: data.csv" in augmented

    # Broadcast: clean content + attached_files metadata (built from safe refs)
    mgr._send_message.assert_awaited_once()
    broadcast_payload = mgr._send_message.await_args.args[1]
    assert broadcast_payload["type"] == "message"
    assert broadcast_payload["data"]["content"] == "please use this"
    assert broadcast_payload["data"]["source"] == "user"
    metadata = broadcast_payload["data"]["metadata"]
    parsed = json.loads(metadata["attached_files"])
    assert parsed[0]["name"] == "data.csv"
    assert parsed[0]["uploaded"] is True

    # Saved message: same shape + type marker
    mgr._save_message.assert_awaited_once()
    save_payload = mgr._save_message.await_args.args[1]
    assert save_payload["type"] == "user_message"
    assert save_payload["content"] == "please use this"
    assert (
        json.loads(save_payload["metadata"]["attached_files"])[0]["name"] == "data.csv"
    )

    mgr._set_active_if_awaiting.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_input_response_no_files_emits_empty_attached_files() -> None:
    """Without files, message is still broadcast/saved with
    metadata.attached_files = '[]' so the wire format matches the
    start-task path. provide_input receives the raw response."""
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    team.add_uploaded_files = MagicMock()
    mgr = _make_ws_manager_with_team(team)

    await mgr.handle_input_response(1, "just text")

    team.add_uploaded_files.assert_not_called()
    team.provide_input.assert_called_once_with("just text")

    broadcast_payload = mgr._send_message.await_args.args[1]
    assert broadcast_payload["data"]["content"] == "just text"
    # Always emit attached_files metadata ("[]" when no attachments) so
    # the wire format is uniform across start-task and input-response.
    assert json.loads(broadcast_payload["data"]["metadata"]["attached_files"]) == []

    save_payload = mgr._save_message.await_args.args[1]
    assert save_payload["content"] == "just text"
    assert json.loads(save_payload["metadata"]["attached_files"]) == []


@pytest.mark.asyncio
async def test_input_response_empty_files_list_emits_empty_attached_files() -> None:
    """An empty/no-valid-entries list shouldn't trigger add_uploaded_files,
    but the message still gets metadata.attached_files = '[]'."""
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    team.add_uploaded_files = MagicMock()
    mgr = _make_ws_manager_with_team(team)

    await mgr.handle_input_response(1, "hi", files=[])

    team.add_uploaded_files.assert_not_called()
    team.provide_input.assert_called_once_with("hi")
    save_payload = mgr._save_message.await_args.args[1]
    assert json.loads(save_payload["metadata"]["attached_files"]) == []


@pytest.mark.asyncio
async def test_input_response_with_approval_pending_ignores_files(caplog) -> None:
    """When the team manager is awaiting an approval, file attachments
    are dropped (with a warning) and the response is treated as an NL
    approval."""
    team = MagicMock()
    team.has_pending_approval = True
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    team.add_uploaded_files = MagicMock()
    mgr = _make_ws_manager_with_team(team)

    await mgr.handle_input_response(
        1,
        "yes",
        files=[{"name": "x.csv", "path": "files/user/u/s/1/x.csv"}],
    )

    # Files are ignored — add_uploaded_files NOT called
    team.add_uploaded_files.assert_not_called()
    # Approval path: _save_approval_response is called, regular send/save are not
    mgr._save_approval_response.assert_awaited_once()
    mgr._send_message.assert_not_called()
    mgr._save_message.assert_not_called()
    # provide_input still gets the raw response
    team.provide_input.assert_called_once_with("yes")


@pytest.mark.asyncio
async def test_input_response_invalid_file_entries_filtered() -> None:
    """Non-dict entries in the files list are filtered out before reaching
    add_uploaded_files."""
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    team.add_uploaded_files = MagicMock(return_value=[])
    run_obj = MagicMock(id=1, user_id="u1", session_id="s1")
    mgr = _make_ws_manager_with_team(team, run=run_obj)

    await mgr.handle_input_response(
        1,
        "use these",
        files=[
            "not-a-dict",  # type: ignore[list-item]
            {"name": "a.csv", "path": "files/user/u1/s1/1/a.csv", "uploaded": True},
            42,  # type: ignore[list-item]
        ],
    )

    team.add_uploaded_files.assert_called_once()
    forwarded = team.add_uploaded_files.call_args.args[0]
    assert [f["name"] for f in forwarded] == ["a.csv"]


@pytest.mark.asyncio
async def test_input_response_unknown_run_logs_warning(caplog) -> None:
    """If the team manager is gone, handle_input_response should log a
    warning and not raise."""
    mgr = WebSocketManager.__new__(WebSocketManager)
    mgr._team_managers = {}  # no team manager for this run
    mgr._send_message = AsyncMock()
    mgr._save_message = AsyncMock()
    mgr._save_approval_response = AsyncMock()
    mgr._set_active_if_awaiting = AsyncMock()
    mgr._get_run = AsyncMock(return_value=None)

    await mgr.handle_input_response(99, "hello")

    mgr._send_message.assert_not_called()
    mgr._save_message.assert_not_called()
    mgr._set_active_if_awaiting.assert_not_called()


@pytest.mark.asyncio
async def test_input_response_files_dropped_when_run_missing_in_db() -> None:
    """Copilot review on PR #600: if `_get_run` returns None we must NOT
    fall back to the wider `app_dir/files/user` validation scope (which
    would let cross-run paths slip through). Drop attachments entirely,
    keep `attached_files` metadata as "[]", but still send the text reply
    and unblock the agent.
    """
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    team.add_uploaded_files = MagicMock()
    mgr = _make_ws_manager_with_team(team, run=None)  # _get_run -> None

    await mgr.handle_input_response(
        1,
        "still send my reply",
        files=[
            {"name": "evil.csv", "path": "files/user/u/s/r/evil.csv", "uploaded": True}
        ],
    )

    # add_uploaded_files must NOT be called when run lookup fails
    team.add_uploaded_files.assert_not_called()
    # Text reply still unblocks the agent
    team.provide_input.assert_called_once_with("still send my reply")
    # attached_files stays as "[]" — no leaked metadata
    save_payload = mgr._save_message.await_args.args[1]
    assert json.loads(save_payload["metadata"]["attached_files"]) == []
    broadcast_payload = mgr._send_message.await_args.args[1]
    assert json.loads(broadcast_payload["data"]["metadata"]["attached_files"]) == []


@pytest.mark.asyncio
async def test_input_response_uses_safe_refs_not_raw_client_payload() -> None:
    """Copilot review on PR #600: the persisted/broadcast attached_files
    metadata must come from the SERVER-validated safe refs returned by
    add_uploaded_files, NOT the raw client payload. This prevents a
    malicious client from sending a path pointing to another run's files
    and having the chat render a clickable chip linking to it.
    """
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    # Client sends two refs; server-side validation only accepts the
    # first (the second targets another run's directory). The mock
    # mirrors what real add_uploaded_files would do.
    team.add_uploaded_files = MagicMock(
        return_value=[
            {
                "name": "ok.csv",
                "path": "files/user/u1/s1/1/ok.csv",
                "type": "file",
                "uploaded": True,
            }
        ]
    )
    run_obj = MagicMock(id=1, user_id="u1", session_id="s1")
    mgr = _make_ws_manager_with_team(team, run=run_obj)

    raw_files = [
        {"name": "ok.csv", "path": "files/user/u1/s1/1/ok.csv", "uploaded": True},
        {
            "name": "secret.csv",
            "path": "files/user/other/s/r/secret.csv",
            "uploaded": True,
        },
    ]
    await mgr.handle_input_response(1, "use these", files=raw_files)

    # add_uploaded_files received the full client payload (it does its
    # own per-entry validation internally).
    team.add_uploaded_files.assert_called_once()
    forwarded = team.add_uploaded_files.call_args.args[0]
    assert len(forwarded) == 2

    # But the broadcast/saved metadata only contains the safe ref. The
    # cross-tenant `secret.csv` path NEVER reaches the wire.
    save_payload = mgr._save_message.await_args.args[1]
    parsed = json.loads(save_payload["metadata"]["attached_files"])
    assert [f["name"] for f in parsed] == ["ok.csv"]
    assert all("other" not in f.get("path", "") for f in parsed)

    # Same check on the broadcast payload
    broadcast_payload = mgr._send_message.await_args.args[1]
    broadcast_parsed = json.loads(
        broadcast_payload["data"]["metadata"]["attached_files"]
    )
    assert [f["name"] for f in broadcast_parsed] == ["ok.csv"]

    # Agent prompt augmentation only mentions the safe file
    augmented = team.provide_input.call_args.args[0]
    assert "Attached file: ok.csv" in augmented
    assert "secret.csv" not in augmented


@pytest.mark.asyncio
async def test_input_response_no_safe_refs_keeps_attached_files_empty() -> None:
    """If add_uploaded_files validates everything to nothing (e.g. all
    paths fail validation), attached_files stays "[]" and provide_input
    receives the raw response (no augmentation).
    """
    team = MagicMock()
    team.has_pending_approval = False
    team.has_pending_continuation = False
    team.provide_input = MagicMock()
    team.add_uploaded_files = MagicMock(return_value=[])  # all rejected
    run_obj = MagicMock(id=1, user_id="u1", session_id="s1")
    mgr = _make_ws_manager_with_team(team, run=run_obj)

    await mgr.handle_input_response(
        1,
        "hello",
        files=[
            {"name": "bad", "path": "../../etc/passwd", "uploaded": True},
        ],
    )

    team.add_uploaded_files.assert_called_once()
    team.provide_input.assert_called_once_with("hello")  # NOT augmented
    save_payload = mgr._save_message.await_args.args[1]
    assert json.loads(save_payload["metadata"]["attached_files"]) == []
