"""Unit tests for the max-rounds continuation flow in FaraWebSurfer.

Covers:

- `_handle_max_rounds_continuation` yields a `ContinuationRequest` and
  reacts to ``yes`` / ``no`` correctly.
- `_summarize_progress` reuses the existing ``chat_history`` with a
  one-shot summary system message in place of the action-mode system
  prompt and uses ``stop=[]`` so prose isn't truncated at
  ``</tool_call>``. Any pending text observation is appended as a
  trailing user message.
- The outer ``while True`` in ``run_stream`` enters the continuation
  branch only after the per-batch ``max_rounds`` is exhausted, and a
  ``yes`` reply grants a fresh batch instead of terminating.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from magentic_ui.agents.web_surfer.fara._fara_qwen3 import (
    FaraQwen3Agent,
    FaraQwen3AgentState,
)
from magentic_ui.agents.web_surfer.fara._fara_web_surfer import FaraWebSurfer
from magentic_ui.agents.web_surfer.fara._types import (
    BrowserEnvironment,
    LLMMessage,
    StreamUpdate,
)
from magentic_ui.types import ContinuationRequest


# ---------------------------------------------------------------------------
# Helpers (mirror the ones in test_fara_qwen3.py — kept local to avoid
# cross-module imports of test fixtures)
# ---------------------------------------------------------------------------


def _make_mock_env() -> AsyncMock:
    env = AsyncMock(spec=BrowserEnvironment)
    env.get_screenshot.return_value = _minimal_png()
    env.get_url.return_value = "https://example.com"
    env.goto.return_value = None
    return env


def _minimal_png() -> bytes:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, format="PNG")
    return buf.getvalue()


def _build_surfer(
    *,
    max_rounds: int = 2,
    generate_side_effect: Any = None,
    summary_response: str = "Concrete progress summary.",
) -> tuple[FaraWebSurfer, FaraQwen3Agent]:
    """Build a FaraWebSurfer wired to a mocked core agent.

    Mocks every private agent method touched by the harness so the
    tests exercise only the harness's continuation logic, not vLLM or
    the browser pipeline.
    """
    surfer = FaraWebSurfer(
        model_client_config={"api_key": "test", "base_url": "http://x"},
        max_rounds=max_rounds,
    )
    agent = FaraQwen3Agent(
        client_config={"api_key": "test", "base_url": "http://x"},
        max_rounds=max_rounds,
    )
    agent._state = FaraQwen3AgentState(
        chat_history=[LLMMessage(role="user", content="initial task")]
    )
    if generate_side_effect is not None:
        agent._generate_model_call = AsyncMock(  # type: ignore[method-assign]
            side_effect=generate_side_effect
        )
    # _summarize_progress reuses the agent's chat_history + a one-shot
    # summary system message, then calls _make_model_call. Stub the LLM
    # call so we can assert the prompt shape without a real backend.
    agent._make_model_call = AsyncMock(  # type: ignore[method-assign]
        return_value=summary_response
    )
    surfer._agent = agent
    surfer._env = _make_mock_env()
    surfer._lazy_init = AsyncMock(return_value=None)  # type: ignore[method-assign]
    # _inject_user_input calls _recover_active_page which asserts a
    # live BrowserContext. Tests don't drive a real browser, so
    # short-circuit the recovery path.
    surfer._recover_active_page = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return surfer, agent


# ---------------------------------------------------------------------------
# _handle_max_rounds_continuation
# ---------------------------------------------------------------------------


class TestHandleMaxRoundsContinuation:
    @pytest.mark.asyncio
    async def test_yields_continuation_request_with_prompt(self):
        surfer, _ = _build_surfer()
        gen = surfer._handle_max_rounds_continuation(actions_so_far=42)
        first = await anext(gen)  # pyright: ignore[reportUndefinedVariable]
        assert isinstance(first, ContinuationRequest)
        assert "42 actions" in first.prompt
        assert "Continue?" in first.prompt
        # Drain so the future doesn't leak
        first.respond("no")
        # Pull the rest so the generator completes
        async for _ in gen:
            pass

    @pytest.mark.asyncio
    async def test_yes_returns_true_and_does_not_emit_final_answer(self):
        surfer, _ = _build_surfer()
        events: list[Any] = []
        gen = surfer._handle_max_rounds_continuation(actions_so_far=10)
        request = await anext(gen)  # pyright: ignore[reportUndefinedVariable]
        request.respond("yes")
        async for evt in gen:
            events.append(evt)
        # Final terminal yield is ``True`` (continue), no StreamUpdate
        # for a final answer.
        assert events[-1] is True
        assert not any(
            isinstance(e, StreamUpdate)
            and e.additional_properties is not None
            and e.additional_properties.get("type") == "final_answer"
            for e in events
        )

    @pytest.mark.asyncio
    async def test_no_emits_final_answer_then_returns_false(self):
        surfer, _ = _build_surfer(summary_response="Best-effort summary text.")
        events: list[Any] = []
        gen = surfer._handle_max_rounds_continuation(actions_so_far=10)
        request = await anext(gen)  # pyright: ignore[reportUndefinedVariable]
        request.respond("no")
        async for evt in gen:
            events.append(evt)
        # Last yield is ``False`` (stop), preceded by a final_answer
        # StreamUpdate carrying the summary text.
        assert events[-1] is False
        final = next(
            e
            for e in events
            if isinstance(e, StreamUpdate)
            and e.additional_properties is not None
            and e.additional_properties.get("type") == "final_answer"
        )
        # Decoupled: StreamUpdate.text is the clean recap; the NOTE/envelope
        # is built Omni-side from the handoff info in additional_properties.
        assert final.text == "Best-effort summary text."
        assert "NOTE:" not in final.text
        assert final.additional_properties.get("max_rounds_reached") is True
        handoff = final.additional_properties.get("handoff")
        assert handoff is not None
        assert handoff["status"] == "incomplete"
        assert handoff["reason"] == "max_rounds"

    @pytest.mark.asyncio
    async def test_freeform_text_is_treated_as_no(self):
        # Anything other than "yes" stops; the connection-layer parser
        # is the source of truth for that policy and the agent only
        # ever sees "yes" or "no" sentinels in production. This test
        # pins the agent's defensive behavior when called directly.
        surfer, _ = _build_surfer()
        events: list[Any] = []
        gen = surfer._handle_max_rounds_continuation(actions_so_far=5)
        request = await anext(gen)  # pyright: ignore[reportUndefinedVariable]
        request.respond("can you also visit example.com?")
        async for evt in gen:
            events.append(evt)
        assert events[-1] is False


# ---------------------------------------------------------------------------
# _summarize_progress
# ---------------------------------------------------------------------------


class TestSummarizeProgress:
    @pytest.mark.asyncio
    async def test_calls_make_model_call_with_summary_system_and_history(self):
        surfer, agent = _build_surfer(summary_response="summary text")
        result = await surfer._summarize_progress()
        assert result == "summary text"

        agent._make_model_call.assert_awaited_once()  # type: ignore[attr-defined]
        call = agent._make_model_call.call_args  # type: ignore[attr-defined]
        full_history = call.args[0]
        # Shape: [summary system, ...existing chat_history...]
        # We reuse the agent's chat_history rather than rebuild a
        # screenshot + action-mode system prompt; only the leading
        # system message is swapped for one that asks for prose.
        assert full_history[0].role == "system"
        assert "stop" in full_history[0].content.lower()
        assert "tool_call" in full_history[0].content
        # Subsequent messages come from chat_history verbatim.
        assert full_history[1].role == "user"
        assert full_history[1].content == "initial task"

    @pytest.mark.asyncio
    async def test_overrides_default_stop_token(self):
        # The summary call must override the default ``stop=["</tool_call>"]``
        # so prose isn't truncated when the model writes XML-like text.
        surfer, agent = _build_surfer()
        await surfer._summarize_progress()
        call = agent._make_model_call.call_args  # type: ignore[attr-defined]
        assert call.kwargs["extra_create_args"]["stop"] == []

    @pytest.mark.asyncio
    async def test_trims_tool_call_opener_from_response(self):
        surfer, _ = _build_surfer(
            summary_response=(
                "Useful summary text here.\n<tool_call>\n{...}</tool_call>"
            )
        )
        result = await surfer._summarize_progress()
        assert "tool_call" not in result
        assert result == "Useful summary text here."

    @pytest.mark.asyncio
    async def test_falls_back_when_make_model_call_raises(self):
        surfer, agent = _build_surfer()
        agent._make_model_call = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("vLLM down")
        )
        result = await surfer._summarize_progress()
        assert result == "Stopped at the user's request before completion."

    @pytest.mark.asyncio
    async def test_falls_back_when_state_missing(self):
        surfer, agent = _build_surfer()
        agent._state = None
        result = await surfer._summarize_progress()
        assert result == "Stopped at the user's request before completion."


# ---------------------------------------------------------------------------
# Public summarize_progress (cross-restart resume entrypoint)
# ---------------------------------------------------------------------------


class TestSummarizeProgressPublic:
    """Covers the public wrapper called by OmniAgent's orphan-detection."""

    @pytest.mark.asyncio
    async def test_uses_in_memory_history_when_already_initialized(self):
        """If _agent is already constructed with chat_history, summarize
        runs against it without touching disk."""
        surfer, agent = _build_surfer(summary_response="from memory")
        text, info = await surfer.summarize_progress()
        # Decoupled: clean recap text; the NOTE/envelope is Omni-built.
        assert text == "from memory"
        assert "NOTE:" not in text
        assert info["status"] == "incomplete"
        assert info["reason"] == "orphan_recovery"
        agent._make_model_call.assert_awaited_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_returns_no_progress_when_history_empty(self, tmp_path):
        """An initialized agent with no chat_history must not invoke the
        LLM — return the explicit no-progress fallback instead."""
        surfer, agent = _build_surfer()
        agent._state.chat_history = []
        text, info = await surfer.summarize_progress()
        assert text == "No prior browsing progress is available for this session."
        assert info["reason"] == "orphan_recovery"
        agent._make_model_call.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_rehydrates_from_state_file_when_not_initialized(self, tmp_path):
        """Cross-restart: a newly-constructed Fara reads fara_state.json
        in summarize_progress and produces a real recap, no browser."""
        import json

        from magentic_ui.agents.web_surfer.fara._state_io import message_to_dict

        state_path = tmp_path / "fara_state.json"
        prior_msg = LLMMessage(role="user", content="found snap circuits jr")
        state_path.write_text(
            json.dumps(
                {
                    "chat_history": [message_to_dict(prior_msg)],
                    "facts": ["candidate: Snap Circuits Jr."],
                }
            )
        )

        surfer = FaraWebSurfer(
            model_client_config={"api_key": "test", "base_url": "http://x"},
            max_rounds=2,
            state_dir=tmp_path,
        )
        # Stub the model call done by _summarize_progress so we don't
        # hit the network; the assertion is that rehydration happened
        # and the LLM saw the recovered history.
        from unittest.mock import patch

        seen_history: list[Any] = []

        async def fake_make_model_call(self, history, **kwargs):
            seen_history.extend(history)
            return "Recovered: Snap Circuits Jr. was identified."

        with patch.object(FaraQwen3Agent, "_make_model_call", new=fake_make_model_call):
            text, info = await surfer.summarize_progress()

        # Decoupled: clean recap text; structured facts/url ride in info,
        # the envelope (NOTE/FACTS) is built Omni-side.
        assert text == "Recovered: Snap Circuits Jr. was identified."
        assert "NOTE:" not in text
        assert info["reason"] == "orphan_recovery"
        assert info["facts"] == ["candidate: Snap Circuits Jr."]
        assert surfer._agent is not None
        assert surfer._agent._state is not None
        assert len(surfer._agent._state.chat_history) == 1
        # The full prompt sent to the model includes a summary system msg
        # plus the restored chat_history — proves rehydration happened.
        assert any(
            isinstance(m.content, str) and "snap circuits" in m.content.lower()
            for m in seen_history
        )

    @pytest.mark.asyncio
    async def test_no_state_file_returns_no_progress(self, tmp_path):
        """Missing fara_state.json on resume → init runs with empty
        chat_history → return no-progress fallback, never call the LLM."""
        surfer = FaraWebSurfer(
            model_client_config={"api_key": "test", "base_url": "http://x"},
            max_rounds=2,
            state_dir=tmp_path,  # dir exists but no state file inside
        )
        from unittest.mock import patch

        with patch.object(
            FaraQwen3Agent, "_make_model_call", new=AsyncMock()
        ) as make_call:
            text, info = await surfer.summarize_progress()
        assert text == "No prior browsing progress is available for this session."
        assert info["reason"] == "orphan_recovery"
        make_call.assert_not_called()


# ---------------------------------------------------------------------------
# Integration through run_stream
# ---------------------------------------------------------------------------


class TestRunStreamContinuationIntegration:
    @pytest.mark.asyncio
    async def test_run_stream_emits_continuation_request_after_max_rounds(self):
        # Per-batch budget = 2. Make every action a benign click so the
        # loop keeps going until the cap is reached.
        click = {
            "arguments": {
                "action": "left_click",
                "coordinate": [10, 10],
                "thoughts": "click",
            }
        }
        surfer, _ = _build_surfer(
            max_rounds=2,
            generate_side_effect=[(click, "raw"), (click, "raw")],
        )

        # Avoid blocking on the future resolution: respond("no") as soon
        # as the request appears.
        events: list[Any] = []
        agen = surfer.run_stream("do the thing")
        async for evt in agen:
            events.append(evt)
            if isinstance(evt, ContinuationRequest):
                evt.respond("no")
                # The harness will then drain final_answer + return.
        # We saw exactly one ContinuationRequest …
        cr = [e for e in events if isinstance(e, ContinuationRequest)]
        assert len(cr) == 1
        # … and a final_answer with max_rounds_reached.
        final = [
            e
            for e in events
            if isinstance(e, StreamUpdate)
            and e.additional_properties is not None
            and e.additional_properties.get("type") == "final_answer"
            and e.additional_properties.get("max_rounds_reached")
        ]
        assert len(final) == 1
