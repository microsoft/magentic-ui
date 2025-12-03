"""Tests for live-browser pool-full handling (issue #587).

Covers:
- ``BrowserSlotPoolFullError`` from ``acquire_slot`` is converted into a
  user-facing InputRequest (system status + input_request payloads).
- The partial team manager is closed and removed.
- The run is left in ``AWAITING_INPUT`` with the original task preserved
  on the run row, so a reply triggers a retry.
- ``handle_input_response`` on a run with no team manager but
  ``AWAITING_INPUT`` status replays the original task ("continue"),
  or treats the reply as a new task otherwise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.backend.datamodel import Run, RunStatus
from magentic_ui.backend.web.managers._pool_full import (
    POOL_FULL_PROMPT_MARKER,
    handle_pool_full,
    maybe_retry_after_pool_full,
)
from magentic_ui.backend.web.managers.connection import WebSocketManager
from magentic_ui.magentic_ui_config import MagenticUIConfig


def _make_ws_manager() -> WebSocketManager:
    return WebSocketManager(
        db_manager=MagicMock(),
        app_dir=Path("/tmp/_unused_test_app_dir"),
        config=MagenticUIConfig(),
        quicksand_manager=None,
    )


def _patch_run_lookup(wm: WebSocketManager, run: Run | None) -> None:
    """Replace ``_get_run`` and ``_update_run_status`` with no-op fakes."""
    wm._get_run = AsyncMock(return_value=run)  # type: ignore[method-assign]
    wm._update_run_status = AsyncMock()  # type: ignore[method-assign]


@pytest.mark.asyncio
class TestHandlePoolFull:
    async def test_emits_input_request_via_ws(self) -> None:
        """The visible card is a top-level ``input_request`` WS message.

        Mirrors the agent's regular InputRequest path: ``_update_run_status``
        sends the (content-less) system status; we send the input_request
        with the prompt as a top-level WS message (NOT wrapped in
        ``{type: "message", data: ...}``, which would bypass the
        ``WS_SERVER_MESSAGE_TYPE.INPUT_REQUEST`` handler and render
        twice on the client).
        """
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=None)
        sent: list[dict[str, Any]] = []
        saved: list[dict[str, Any]] = []
        wm._send_message = AsyncMock(side_effect=lambda rid, msg: sent.append(msg))  # type: ignore[method-assign]
        wm._save_message = AsyncMock(side_effect=lambda rid, msg: saved.append(msg))  # type: ignore[method-assign]

        await handle_pool_full(wm, run_id=42, detail="All 5 in use")

        # Only ONE WS message is sent directly: the input_request. The
        # system status WS message is sent inside _update_run_status.
        assert len(sent) == 1
        ws = sent[0]
        assert ws["type"] == "input_request"
        assert ws["input_type"] == "text_input"
        assert ws["content"]  # non-empty visible prompt

        # Run status was set to AWAITING_INPUT *without* content (so the
        # system WS message has no body — preventing a duplicate card).
        wm._update_run_status.assert_awaited_once()  # type: ignore[attr-defined]
        args, kwargs = wm._update_run_status.call_args  # type: ignore[attr-defined]
        assert args[0] == 42
        assert args[1] == RunStatus.AWAITING_INPUT
        assert kwargs.get("content") is None and (len(args) < 3 or args[2] is None)

        # Both messages are persisted to DB so reload reproduces the
        # same shape: a content-less system status + an input_request.
        assert len(saved) == 2
        assert saved[0]["metadata"]["type"] == "system"
        assert saved[0]["metadata"]["status"] == "awaiting_input"
        assert saved[0]["content"] == ""  # invisible card on reload
        assert saved[0]["metadata"]["subtype"] == POOL_FULL_PROMPT_MARKER
        assert saved[0]["metadata"]["detail"] == "All 5 in use"

        assert saved[1]["metadata"]["type"] == "input_request"
        assert saved[1]["metadata"]["subtype"] == POOL_FULL_PROMPT_MARKER

    async def test_user_facing_text_does_not_mention_pool_size(self) -> None:
        """Non-engineers don't know what '5' means; the prompt avoids the number."""
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=None)
        sent: list[dict[str, Any]] = []
        wm._send_message = AsyncMock(side_effect=lambda rid, msg: sent.append(msg))  # type: ignore[method-assign]
        wm._save_message = AsyncMock()  # type: ignore[method-assign]

        await handle_pool_full(wm, run_id=1, detail="ignored")

        text = sent[0]["content"]
        assert "5" not in text
        # And it should tell the user where to reply, not "reply continue"
        # in the abstract (avoids the user replying in another tab).
        assert "here" in text.lower()

    async def test_closes_partial_team_manager(self) -> None:
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=None)
        wm._send_message = AsyncMock()  # type: ignore[method-assign]
        wm._save_message = AsyncMock()  # type: ignore[method-assign]
        partial_tm = MagicMock()
        partial_tm.close = AsyncMock()
        wm._team_managers[42] = partial_tm

        await handle_pool_full(wm, run_id=42, detail="x")

        partial_tm.close.assert_awaited_once()
        assert 42 not in wm._team_managers


@pytest.mark.asyncio
class TestRetryAfterPoolFull:
    def _awaiting_run_with_task(self, content: str) -> Run:
        return Run(
            id=42,
            session_id=1,
            status=RunStatus.AWAITING_INPUT,
            task={"content": content, "source": "user"},
        )

    async def test_continue_reply_replays_original_task(self) -> None:
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=self._awaiting_run_with_task("Find the price of X"))
        wm._send_message = AsyncMock()  # type: ignore[method-assign]
        wm._save_message = AsyncMock()  # type: ignore[method-assign]
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        handled = await maybe_retry_after_pool_full(wm, 42, "continue")

        assert handled is True
        # Suppress _execute_stream's user-message echo: the user's "continue"
        # reply was already echoed above; without this the original task
        # would appear in the chat a second time.
        wm.start_stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            42, "Find the price of X", echo_user_message=False
        )

    async def test_continue_with_punctuation_still_retries(self) -> None:
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=self._awaiting_run_with_task("Original"))
        wm._send_message = AsyncMock()  # type: ignore[method-assign]
        wm._save_message = AsyncMock()  # type: ignore[method-assign]
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        await maybe_retry_after_pool_full(wm, 42, "Continue.")
        wm.start_stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            42, "Original", echo_user_message=False
        )

    async def test_empty_reply_echoes_continue_not_blank(self) -> None:
        """Whitespace/empty reply must not produce a blank user bubble."""
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=self._awaiting_run_with_task("Original"))
        sent: list[dict[str, Any]] = []
        saved: list[dict[str, Any]] = []
        wm._send_message = AsyncMock(side_effect=lambda rid, msg: sent.append(msg))  # type: ignore[method-assign]
        wm._save_message = AsyncMock(side_effect=lambda rid, msg: saved.append(msg))  # type: ignore[method-assign]
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        await maybe_retry_after_pool_full(wm, 42, "   ")

        assert sent[0]["data"]["content"] == "continue"
        assert saved[0]["content"] == "continue"
        wm.start_stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            42, "Original", echo_user_message=False
        )

    async def test_other_reply_treated_as_new_task(self) -> None:
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=self._awaiting_run_with_task("Original"))
        wm._send_message = AsyncMock()  # type: ignore[method-assign]
        wm._save_message = AsyncMock()  # type: ignore[method-assign]
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        await maybe_retry_after_pool_full(wm, 42, "Use Wikipedia instead")

        wm.start_stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            42, "Use Wikipedia instead", echo_user_message=False
        )

    async def test_skipped_when_not_awaiting_input(self) -> None:
        """A reply against a run that already moved past AWAITING_INPUT is ignored."""
        wm = _make_ws_manager()
        complete_run = Run(
            id=42,
            session_id=1,
            status=RunStatus.COMPLETE,
            task={"content": "Original", "source": "user"},
        )
        _patch_run_lookup(wm, run=complete_run)
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        handled = await maybe_retry_after_pool_full(wm, 42, "continue")

        assert handled is False
        wm.start_stream.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_skipped_when_no_run(self) -> None:
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=None)
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        handled = await maybe_retry_after_pool_full(wm, 42, "continue")

        assert handled is False
        wm.start_stream.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_skipped_when_no_original_task_and_empty_reply(self) -> None:
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=self._awaiting_run_with_task(""))
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]

        handled = await maybe_retry_after_pool_full(wm, 42, "")

        assert handled is False
        wm.start_stream.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_handle_input_response_dispatches_to_retry(self) -> None:
        """The public entry point chooses the retry branch when no TM exists."""
        wm = _make_ws_manager()
        _patch_run_lookup(wm, run=self._awaiting_run_with_task("Original"))
        wm._send_message = AsyncMock()  # type: ignore[method-assign]
        wm._save_message = AsyncMock()  # type: ignore[method-assign]
        wm.start_stream = AsyncMock()  # type: ignore[method-assign]
        # No team manager registered for this run.

        await wm.handle_input_response(42, "continue")

        wm.start_stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            42, "Original", echo_user_message=False
        )
