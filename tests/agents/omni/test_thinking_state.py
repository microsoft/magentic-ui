"""Integration tests for OmniAgent thinking-state stream output.

Asserts that ``OmniAgent.run_stream`` surfaces the transient
``agent_state`` signals (``calling_model`` / ``generating``) around each
LLM call and stamps ``thinking_seconds`` onto the reasoning message
when the model streamed at least one token.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import OmniAgent

from ._stream_mock import StreamScript, content_delta, install_stream_mock


def _make_completion(text: str, total_tokens: int = 50) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage = MagicMock(
        prompt_tokens=total_tokens - 5,
        completion_tokens=5,
        total_tokens=total_tokens,
    )
    return response


async def _build_agent(
    tmp_path: Path, client: MagicMock
) -> tuple[OmniAgent, NullSandbox]:
    sandbox = NullSandbox(workspace=tmp_path)
    await sandbox.__aenter__()
    agent = OmniAgent(
        client=client,
        model="test-model",
        host_workspace=tmp_path,
        sandbox=sandbox,
        approval_policy=ApprovalPolicy.AUTO_APPROVE,
    )
    return agent, sandbox


def _props(event: object) -> dict:
    return getattr(event, "additional_properties", {}) or {}


def _of_type(events: list[object], type_name: str) -> list[object]:
    return [e for e in events if _props(e).get("type") == type_name]


class TestThinkingStateStream:
    @pytest.mark.asyncio
    async def test_emits_calling_model_then_generating_around_llm_call(
        self, tmp_path: Path
    ) -> None:
        """Each LLM call yields a ``calling_model`` signal, then a
        ``generating`` signal once the first token streams back."""
        client = MagicMock()
        install_stream_mock(
            client,
            [
                StreamScript(
                    events=[content_delta()],
                    completion=_make_completion("Let me think.\n<answer>done</answer>"),
                )
            ],
        )
        agent, sandbox = await _build_agent(tmp_path, client)
        try:
            events = [evt async for evt in agent.run_stream("go")]
        finally:
            await sandbox.__aexit__(None, None, None)

        states = [_props(e).get("state") for e in _of_type(events, "agent_state")]
        # calling_model is emitted before the request; generating after the
        # first streamed token. Order matters.
        assert states == ["calling_model", "generating"]

    @pytest.mark.asyncio
    async def test_reasoning_carries_thinking_seconds_when_streamed(
        self, tmp_path: Path
    ) -> None:
        """A streamed token starts the clock, so the reasoning message is
        stamped with a non-negative integer ``thinking_seconds``."""
        client = MagicMock()
        install_stream_mock(
            client,
            [
                StreamScript(
                    events=[content_delta()],
                    completion=_make_completion("Let me think.\n<answer>done</answer>"),
                )
            ],
        )
        agent, sandbox = await _build_agent(tmp_path, client)
        try:
            events = [evt async for evt in agent.run_stream("go")]
        finally:
            await sandbox.__aexit__(None, None, None)

        reasoning = _of_type(events, "reasoning")
        assert len(reasoning) == 1
        secs = _props(reasoning[0]).get("thinking_seconds")
        assert isinstance(secs, int)
        assert secs >= 0

    @pytest.mark.asyncio
    async def test_reasoning_omits_thinking_seconds_without_tokens(
        self, tmp_path: Path
    ) -> None:
        """With no token stream there is no ``thinking`` signal, so the
        reasoning message omits ``thinking_seconds`` and the frontend
        falls back to its timestamp-diff heuristic."""
        client = MagicMock()
        install_stream_mock(
            client, [_make_completion("Let me think.\n<answer>done</answer>")]
        )
        agent, sandbox = await _build_agent(tmp_path, client)
        try:
            events = [evt async for evt in agent.run_stream("go")]
        finally:
            await sandbox.__aexit__(None, None, None)

        reasoning = _of_type(events, "reasoning")
        assert len(reasoning) == 1
        assert "thinking_seconds" not in _props(reasoning[0])
