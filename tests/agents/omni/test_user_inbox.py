"""Tests for OmniAgent's mid-run user-message inbox.

When the user types while the agent is actively running (no InputRequest
open), the message is queued on the shared PauseController and drained
at the top of the next round, becoming a plain user_msg in the LLM
request.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import OmniAgent
from magentic_ui.types import PauseController


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
    pause_controller: PauseController,
) -> tuple[OmniAgent, NullSandbox]:
    sandbox = NullSandbox(workspace=tmp_path)
    await sandbox.__aenter__()
    agent = OmniAgent(
        client=client,
        model="test-model",
        host_workspace=tmp_path,
        sandbox=sandbox,
        approval_policy=ApprovalPolicy.AUTO_APPROVE,
        pause_controller=pause_controller,
    )
    return agent, sandbox


def _user_messages_in_call(client: MagicMock, call_index: int) -> list[str]:
    """Return the content strings of every user-role message in the Nth LLM call."""
    call = client.chat.completions.create.call_args_list[call_index]
    return [m["content"] for m in call.kwargs["messages"] if m["role"] == "user"]


class TestUserInbox:
    @pytest.mark.asyncio
    async def test_queued_message_appears_as_user_msg_next_round(
        self, tmp_path: Path
    ) -> None:
        """A message queued mid-run is delivered to the next LLM call."""
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                # Round 1: model emits a bash call. Caller queues a message
                # while we're between rounds.
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo hi"}}</tool_call>',
                # Round 2: model wraps up.
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            stream = agent.run_stream("initial task")
            # Pull events until the first tool_result emerges. This is past
            # the LLM call and the bash exec, but before round 2 starts.
            async for evt in stream:
                if (
                    getattr(evt, "additional_properties", {}).get("type")
                    == "tool_result"
                ):
                    pause_controller.queue_message("interjection: also do X")
                    break
            # Drain the rest of the stream.
            async for _ in stream:
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        # Round 2's LLM call should include the queued message as a
        # plain user-role message.
        round_2_user_msgs = _user_messages_in_call(client, 1)
        assert any(
            "interjection: also do X" in m for m in round_2_user_msgs
        ), f"queued message missing from round 2 user messages: {round_2_user_msgs}"

        # Inbox should be empty after the agent drained it.
        assert pause_controller.has_queued_messages is False

    @pytest.mark.asyncio
    async def test_multiple_queued_messages_each_become_separate_user_msg(
        self, tmp_path: Path
    ) -> None:
        """Several mid-run messages each become their own user-role entry."""
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo hi"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            stream = agent.run_stream("task")
            async for evt in stream:
                if (
                    getattr(evt, "additional_properties", {}).get("type")
                    == "tool_result"
                ):
                    pause_controller.queue_message("first nudge")
                    pause_controller.queue_message("second nudge")
                    break
            async for _ in stream:
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        # Each queued message becomes its own user-role message — not coalesced.
        round_2_user_msgs = _user_messages_in_call(client, 1)
        assert any("first nudge" in m for m in round_2_user_msgs)
        assert any("second nudge" in m for m in round_2_user_msgs)

        # And they are distinct messages, not concatenated into one.
        first_idx = next(
            i for i, m in enumerate(round_2_user_msgs) if "first nudge" in m
        )
        second_idx = next(
            i for i, m in enumerate(round_2_user_msgs) if "second nudge" in m
        )
        assert first_idx != second_idx
        assert first_idx < second_idx  # FIFO order preserved

    @pytest.mark.asyncio
    async def test_empty_inbox_does_not_inject_anything(self, tmp_path: Path) -> None:
        """With no queued messages, round 2 has only the original task plus
        the tool_response — no spurious extras from the drain step."""
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo hi"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            async for _ in agent.run_stream("the original task"):
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        round_1_user_msgs = _user_messages_in_call(client, 0)
        round_2_user_msgs = _user_messages_in_call(client, 1)
        # Round 2 should add exactly one user message (the tool_response).
        assert len(round_2_user_msgs) == len(round_1_user_msgs) + 1
        new_msg = round_2_user_msgs[-1]
        assert "<tool_response>" in new_msg


class TestSubAgentSteeringSurface:
    """OmniAgent must surface steerings drained by sub-agents.

    When OmniAgent has delegated work to a sub-agent (e.g. Fara via
    ``delegate_cua``) and the user types a steering message during that
    delegation, the sub-agent — not OmniAgent — drains the message. If
    OmniAgent later only sees the sub-agent's off-spec output, it
    misreads it as a tool failure and tends to retry the original task,
    silently overriding the user's redirect. The agent therefore polls
    the controller's drain-log for messages drained by other readers
    and surfaces them as ``<user_interjection_to_subagent>`` messages.
    """

    @pytest.mark.asyncio
    async def test_message_drained_by_other_reader_surfaces_next_round(
        self, tmp_path: Path
    ) -> None:
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                # Round 1: model emits a bash call (stand-in for any
                # tool that, in real use, might delegate to a sub-agent).
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo hi"}}</tool_call>',
                # Round 2: model wraps up.
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            stream = agent.run_stream("initial task")
            async for evt in stream:
                if (
                    getattr(evt, "additional_properties", {}).get("type")
                    == "tool_result"
                ):
                    # Simulate a sub-agent (e.g. Fara) draining a user
                    # steering while OmniAgent was waiting on its tool.
                    pause_controller.queue_message("steer the sub-agent")
                    pause_controller.drain_messages(reader="web_surfer")
                    break
            async for _ in stream:
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        round_2_user_msgs = _user_messages_in_call(client, 1)
        # OmniAgent should see the sub-agent steering wrapped so it
        # knows the sub-agent already acted on it.
        assert any(
            "<user_interjection_to_subagent>" in m and "steer the sub-agent" in m
            for m in round_2_user_msgs
        ), f"sub-agent steering missing: {round_2_user_msgs}"

    @pytest.mark.asyncio
    async def test_subagent_steering_surfaced_only_once(self, tmp_path: Path) -> None:
        """The cursor must prevent surfacing the same steering twice.

        We can't just check round-2/3 user messages for the steering
        text — the chat history accumulates, so the round-1 surfacing
        will still appear in subsequent calls. Instead, check that the
        TOTAL number of ``<user_interjection_to_subagent>`` blocks
        across all calls equals 1 (one surfacing in round 2, then
        carried in history but never re-emitted).
        """
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                # 3 rounds: each does a bash call, last one finalizes.
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo r1"}}</tool_call>',
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo r2"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            stream = agent.run_stream("task")
            # Drain a sub-agent steering after round 1's tool_result
            # (i.e. after run_stream has captured its initial cursor).
            async for evt in stream:
                if (
                    getattr(evt, "additional_properties", {}).get("type")
                    == "tool_result"
                ):
                    pause_controller.queue_message("one-shot steer")
                    pause_controller.drain_messages(reader="web_surfer")
                    break
            async for _ in stream:
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        # Across the whole final-round conversation history, the
        # sub-agent steering wrapper should appear exactly once. If the
        # cursor were broken, it would re-emit on every round and we'd
        # see >=2 occurrences.
        round_3_user_msgs = _user_messages_in_call(client, 2)
        wrapper_count = sum(
            1 for m in round_3_user_msgs if "<user_interjection_to_subagent>" in m
        )
        assert wrapper_count == 1, (
            f"sub-agent steering should appear exactly once in history, "
            f"got {wrapper_count} occurrences"
        )

    @pytest.mark.asyncio
    async def test_omniagent_own_drain_uses_user_interjection_wrapper(
        self, tmp_path: Path
    ) -> None:
        """OmniAgent's own drained messages use the standalone wrapper."""
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo hi"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            stream = agent.run_stream("task")
            async for evt in stream:
                if (
                    getattr(evt, "additional_properties", {}).get("type")
                    == "tool_result"
                ):
                    pause_controller.queue_message("direct interjection")
                    break
            async for _ in stream:
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        round_2_user_msgs = _user_messages_in_call(client, 1)
        assert any(
            "<user_interjection>" in m and "direct interjection" in m
            for m in round_2_user_msgs
        )
        # Must NOT use the sub-agent wrapper for OmniAgent's own drains.
        assert not any(
            "<user_interjection_to_subagent>" in m for m in round_2_user_msgs
        )

        # Lock in ordering: the literal user text appears immediately
        # after the opening tag (before any framing/IMPORTANT prose), so
        # the model can't skim past it.
        wrapper_msg = next(m for m in round_2_user_msgs if "<user_interjection>" in m)
        body = wrapper_msg.split("<user_interjection>\n", 1)[1]
        first_nonblank = next(line for line in body.splitlines() if line.strip())
        assert (
            first_nonblank == "direct interjection"
        ), f"User text must appear first in the wrapper; got: {first_nonblank!r}"

    @pytest.mark.asyncio
    async def test_multiple_subagent_drains_combined_into_one_wrapper(
        self, tmp_path: Path
    ) -> None:
        """Multiple sub-agent drains in one batch share a single wrapper.

        This matches FaraWebSurfer, which joins multiple queued user
        messages into one combined response per step. Surfacing them as
        a single ``<user_interjection_to_subagent>`` block (with all
        messages inside) keeps the framing consistent with how the
        sub-agent actually processed them, and avoids paying the
        wrapper-prompt cost N times.
        """
        pause_controller = PauseController()
        client = _mock_llm_client(
            [
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo r1"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client, pause_controller)

        try:
            stream = agent.run_stream("task")
            # Drain three sub-agent-drained messages after round 1's
            # tool_result so they post-date the cursor init.
            async for evt in stream:
                if (
                    getattr(evt, "additional_properties", {}).get("type")
                    == "tool_result"
                ):
                    for msg in ("steer A", "steer B", "steer C"):
                        pause_controller.queue_message(msg)
                        pause_controller.drain_messages(reader="web_surfer")
                    break
            async for _ in stream:
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        round_2_user_msgs = _user_messages_in_call(client, 1)
        # Exactly one wrapper, containing all three messages.
        wrappers = [
            m for m in round_2_user_msgs if "<user_interjection_to_subagent>" in m
        ]
        assert len(wrappers) == 1, f"expected one combined wrapper, got {len(wrappers)}"
        wrapper = wrappers[0]
        assert "steer A" in wrapper
        assert "steer B" in wrapper
        assert "steer C" in wrapper
        # FIFO order preserved.
        assert (
            wrapper.index("steer A")
            < wrapper.index("steer B")
            < wrapper.index("steer C")
        )
