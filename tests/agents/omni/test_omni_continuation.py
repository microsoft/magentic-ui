"""Tests for OmniAgent's max-rounds continuation flow.

Mirrors :mod:`tests.agents.fara.test_fara_continuation`. Covers the
three exit paths from the new ``while True`` loop in ``run_stream``:

- Continue: per-batch counter resets, new round runs, ``total_rounds``
  keeps climbing.
- Stop: a ``final_answer`` event with ``max_rounds_reached=True`` is
  emitted (built from ``_generate_final_answer``); the loop exits.
- Sub-agent user-stop: when a delegated agent yields a final answer
  with ``max_rounds_reached=True``, OmniAgent appends a ``<system>``
  directive after the tool_responses so the next LLM call sees a
  "don't re-delegate" hint.
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.agents.message_schemas import final_answer_props
from magentic_ui.agents.web_surfer.fara._types import StreamUpdate
from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import OmniAgent
from magentic_ui.types import ContinuationRequest, PauseController


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


def _mock_llm_client(responses: list[str]) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[_make_completion(t) for t in responses]
    )
    return client


async def _build_agent(
    tmp_path: Path,
    client: MagicMock,
    *,
    max_rounds: int,
) -> tuple[OmniAgent, NullSandbox]:
    sandbox = NullSandbox(workspace=tmp_path)
    await sandbox.__aenter__()
    agent = OmniAgent(
        client=client,
        model="test-model",
        host_workspace=tmp_path,
        sandbox=sandbox,
        approval_policy=ApprovalPolicy.AUTO_APPROVE,
        pause_controller=PauseController(),
        max_rounds=max_rounds,
    )
    return agent, sandbox


@pytest.mark.asyncio
async def test_max_rounds_yields_continuation_request(tmp_path: Path) -> None:
    """Reaching the per-batch cap yields a ``ContinuationRequest``."""
    # Round 1 burns the only batch round on a bare-text reply.
    # Cap-hit triggers the request; we resolve it with "no" to drain the
    # generator (then the harness calls _generate_final_answer once more).
    client = _mock_llm_client(
        [
            "just thinking, no tool call",
            "<answer>partial</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client, max_rounds=1)

    saw_continuation = False
    try:
        async for evt in agent.run_stream("task"):
            if isinstance(evt, ContinuationRequest):
                saw_continuation = True
                evt.respond("no")
    finally:
        await sandbox.__aexit__(None, None, None)

    assert saw_continuation, "Expected a ContinuationRequest after the cap"


@pytest.mark.asyncio
async def test_continuation_stop_emits_final_answer_with_flag(
    tmp_path: Path,
) -> None:
    """Choosing Stop emits a final-answer event flagged ``max_rounds_reached=True``."""
    # Round 1: bare text → consumes the only batch round.
    # Cap-hit triggers _generate_final_answer, which makes a non-persisting
    # LLM call ("final_answer"). We provide it as the second mock response.
    client = _mock_llm_client(
        [
            "first round, no tool call",
            "<answer>partial summary</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client, max_rounds=1)

    final_answer_evts: list[StreamUpdate] = []
    try:
        async for evt in agent.run_stream("task"):
            if isinstance(evt, ContinuationRequest):
                evt.respond("no")
                continue
            if (
                isinstance(evt, StreamUpdate)
                and evt.additional_properties.get("type") == "final_answer"
            ):
                final_answer_evts.append(evt)
    finally:
        await sandbox.__aexit__(None, None, None)

    # With max_rounds=1 the cap check fires at the top of round 2 before
    # the bare-text retry can emit its unflagged fallback, so the only
    # final_answer event is the cap-triggered one (Stop path).
    flagged = [
        e
        for e in final_answer_evts
        if e.additional_properties.get("max_rounds_reached")
    ]
    assert len(flagged) == 1, (
        f"Expected exactly one max_rounds_reached final answer; "
        f"got {len(final_answer_evts)} total final_answer events"
    )


@pytest.mark.asyncio
async def test_continuation_continue_resets_counter(tmp_path: Path) -> None:
    """Choosing Continue resets the per-batch counter and runs another batch."""
    # Round 1: bare text (round_num=1, total_rounds=1, no answer).
    # Cap → ContinuationRequest. We answer "yes" → counter resets.
    # Round 2: <answer> ends the loop.
    # We don't send a forced-final-answer call in this scenario, so only
    # 2 LLM calls total are needed.
    client = _mock_llm_client(
        [
            "first round, no tool call",
            "<answer>done</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client, max_rounds=1)

    saw_continuation = False
    saw_final_unflagged = False
    try:
        async for evt in agent.run_stream("task"):
            if isinstance(evt, ContinuationRequest):
                saw_continuation = True
                evt.respond("yes")
                continue
            if (
                isinstance(evt, StreamUpdate)
                and evt.additional_properties.get("type") == "final_answer"
                and not evt.additional_properties.get("max_rounds_reached")
            ):
                saw_final_unflagged = True
    finally:
        await sandbox.__aexit__(None, None, None)

    assert saw_continuation, "Expected the cap to trigger a ContinuationRequest"
    assert saw_final_unflagged, (
        "Expected a final_answer without max_rounds_reached after Continue "
        "(the agent should reach <answer> in round 2)"
    )
    assert (
        client.chat.completions.create.await_count == 2
    ), "Expected exactly 2 LLM calls (one per batch)"


@pytest.mark.asyncio
async def test_subagent_user_stop_appends_no_redelegate_directive(
    tmp_path: Path,
) -> None:
    """Sub-agent user-stop adds a ``<system>`` directive to the next LLM call."""
    # We don't go through the real registry — replace the dispatch with a
    # stub agent whose run_stream yields a max_rounds_reached final answer.
    # Two LLM calls: round 1 emits the delegate_cua tool call, round 2 ends.
    client = _mock_llm_client(
        [
            '<tool_call>{"name": "delegate_cua", "arguments": '
            '{"task": "browse"}}</tool_call>',
            "<answer>done</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client, max_rounds=10)

    class _StubSubAgent:
        async def run_stream(self, **_: object) -> AsyncIterator[StreamUpdate]:
            yield StreamUpdate(
                text="partial result",
                additional_properties=dict(
                    final_answer_props(source="web_surfer", max_rounds_reached=True)
                ),
            )

    # Patch the registry lookup so delegate_cua dispatches to the stub.
    agent._agent_registry = MagicMock()  # pyright: ignore[reportPrivateUsage]
    agent._agent_registry.get = MagicMock(  # pyright: ignore[reportPrivateUsage]
        return_value=MagicMock(agent=_StubSubAgent())
    )
    agent._tool_map = {"delegate_cua": MagicMock()}  # pyright: ignore[reportPrivateUsage]

    try:
        async for _ in agent.run_stream("task"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    # Round 2's user message should contain both the tool_response and
    # the orchestrator-only "do not re-delegate" directive.
    second_call = client.chat.completions.create.call_args_list[1]
    user_msgs = [
        m["content"] for m in second_call.kwargs["messages"] if m["role"] == "user"
    ]
    combined = "\n".join(user_msgs)
    assert "do not re-delegate" in combined.lower() or "re-delegate" in combined.lower()


@pytest.mark.asyncio
async def test_subagent_user_stop_aborts_rest_of_batch(tmp_path: Path) -> None:
    """If a sub-agent user-stops, sibling tool calls in the same response are skipped.

    Otherwise a model that emits two ``delegate_cua`` calls in one
    response would re-run the just-stopped task before the
    "don't re-delegate" directive (only appended after the batch) is
    ever sent to the model.
    """
    client = _mock_llm_client(
        [
            # Round 1 emits TWO delegate_cua calls in one response.
            # The first one user-stops; the second must NOT execute.
            '<tool_call>{"name": "delegate_cua", "arguments": '
            '{"task": "first task"}}</tool_call>'
            '<tool_call>{"name": "delegate_cua", "arguments": '
            '{"task": "second task"}}</tool_call>',
            # Round 2: orchestrator wraps up.
            "<answer>done</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client, max_rounds=10)

    call_count = 0

    class _StubSubAgent:
        async def run_stream(self, **_: object) -> AsyncIterator[StreamUpdate]:
            nonlocal call_count
            call_count += 1
            yield StreamUpdate(
                text=f"sub call {call_count}",
                additional_properties=dict(
                    final_answer_props(source="web_surfer", max_rounds_reached=True)
                ),
            )

    agent._agent_registry = MagicMock()  # pyright: ignore[reportPrivateUsage]
    agent._agent_registry.get = MagicMock(  # pyright: ignore[reportPrivateUsage]
        return_value=MagicMock(agent=_StubSubAgent())
    )
    agent._tool_map = {"delegate_cua": MagicMock()}  # pyright: ignore[reportPrivateUsage]

    try:
        async for _ in agent.run_stream("task"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    assert call_count == 1, (
        f"Expected the sub-agent to be invoked exactly once "
        f"(second call should be skipped); got {call_count}"
    )
