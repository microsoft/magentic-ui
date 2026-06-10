"""Integration tests for OmniAgent.run_stream multi-tool-call execution.

Covers:
- Multiple <tool_call> blocks per LLM turn execute sequentially
- Per-call results concatenate into a single user message of
  <tool_response>...</tool_response> blocks
- request_user_input mid-batch aborts remaining calls (state changed)
- Decline-with-alt-instructions mid-batch aborts remaining calls
- Per-call tool_call_id and tool_call_props/tool_result_props events
  fire once per call
- Parser errors get surfaced back as <tool_response>Error parsing...
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import OmniAgent
from magentic_ui.types import ApprovalRequest, InputRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    from ._stream_mock import install_stream_mock

    client = MagicMock()
    install_stream_mock(client, [_make_completion(t) for t in responses])
    return client


async def _build_agent(
    tmp_path: Path,
    client: MagicMock,
    *,
    approval_policy: ApprovalPolicy = ApprovalPolicy.AUTO_APPROVE,
) -> tuple[OmniAgent, NullSandbox]:
    sandbox = NullSandbox(workspace=tmp_path)
    await sandbox.__aenter__()
    agent = OmniAgent(
        client=client,
        model="test-model",
        host_workspace=tmp_path,
        sandbox=sandbox,
        approval_policy=approval_policy,
    )
    return agent, sandbox


def _last_user_response(client: MagicMock) -> str:
    """Grab the second LLM call's most-recent user-role <tool_response> message."""
    calls = client.chat.completions.stream.call_args_list
    assert len(calls) >= 2, "expected at least two LLM calls"
    msgs = calls[1].kwargs["messages"]
    user_responses = [
        m["content"]
        for m in msgs
        if m["role"] == "user" and "<tool_response>" in m.get("content", "")
    ]
    assert user_responses, "no <tool_response> user message found"
    return user_responses[-1]


# ---------------------------------------------------------------------------
# Multi-call success path
# ---------------------------------------------------------------------------


class TestMultiCallSuccess:
    @pytest.mark.asyncio
    async def test_two_calls_executed_in_order_and_concatenated(
        self, tmp_path: Path
    ) -> None:
        client = _mock_llm_client(
            [
                # Round 1: model emits two bash calls
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo first"}}</tool_call>\n'
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo second"}}</tool_call>',
                # Round 2: model wraps up
                "<answer>both done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client)
        try:
            events = [evt async for evt in agent.run_stream("run two bash calls")]
        finally:
            await sandbox.__aexit__(None, None, None)

        # Second LLM call's user message contains both <tool_response>s
        user_msg = _last_user_response(client)
        assert user_msg.count("<tool_response>") == 2
        assert "first" in user_msg
        assert "second" in user_msg
        assert user_msg.index("first") < user_msg.index("second")

        # Two tool_call events + two tool_result events emitted
        tool_call_events = [
            e
            for e in events
            if getattr(e, "additional_properties", {}).get("type") == "tool_call"
        ]
        tool_result_events = [
            e
            for e in events
            if getattr(e, "additional_properties", {}).get("type") == "tool_result"
        ]
        assert len(tool_call_events) == 2
        assert len(tool_result_events) == 2

        # Each call has a unique tool_call_id
        ids = {e.additional_properties["tool_call_id"] for e in tool_call_events}
        assert len(ids) == 2


# ---------------------------------------------------------------------------
# Mid-batch request_user_input aborts remaining calls
# ---------------------------------------------------------------------------


class TestMidBatchUserInput:
    @pytest.mark.asyncio
    async def test_user_input_in_middle_skips_third_call(self, tmp_path: Path) -> None:
        client = _mock_llm_client(
            [
                # Round 1: bash, request_user_input, bash
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo before"}}</tool_call>\n'
                '<tool_call>{"name": "request_user_input", '
                '"arguments": {"prompt": "continue?"}}</tool_call>\n'
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo after"}}</tool_call>',
                # Round 2: model adapts
                "<answer>ok</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client)

        async def consume() -> list[Any]:
            evts: list[Any] = []
            async for evt in agent.run_stream("test"):
                if isinstance(evt, InputRequest):
                    evt.respond("yes go")
                evts.append(evt)
            return evts

        try:
            events = await consume()
        finally:
            await sandbox.__aexit__(None, None, None)

        # InputRequest fired exactly once (for request_user_input)
        input_requests = [e for e in events if isinstance(e, InputRequest)]
        assert len(input_requests) == 1

        # Combined tool_response should have 2 blocks: bash#1 + user_input
        # The third bash call was discarded.
        user_msg = _last_user_response(client)
        assert user_msg.count("<tool_response>") == 2
        assert "before" in user_msg
        assert "User response: yes go" in user_msg
        assert "after" not in user_msg


# ---------------------------------------------------------------------------
# Mid-batch decline-with-alt aborts remaining calls
# ---------------------------------------------------------------------------


class TestMidBatchDeclineAlt:
    @pytest.mark.asyncio
    async def test_decline_with_alt_aborts_remaining_calls(
        self, tmp_path: Path
    ) -> None:
        client = _mock_llm_client(
            [
                # Round 1: three bash calls; user declines #2 with alt instructions
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo first"}}</tool_call>\n'
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "rm -rf /risky"}}</tool_call>\n'
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo third"}}</tool_call>',
                # Round 2: model adapts to alt
                "<answer>adapted</answer>",
            ]
        )
        # REQUIRE_APPROVAL_ALL forces approval for every tool, so we can
        # intercept the second call's prompt and reply with alt instructions.
        agent, sandbox = await _build_agent(
            tmp_path, client, approval_policy=ApprovalPolicy.REQUIRE_APPROVAL_ALL
        )

        approvals_seen = 0
        approval_responses = ["yes", "use ls instead", "yes"]

        async def consume() -> list[Any]:
            nonlocal approvals_seen
            evts: list[Any] = []
            async for evt in agent.run_stream("test"):
                if isinstance(evt, ApprovalRequest):
                    response = approval_responses[approvals_seen]
                    approvals_seen += 1
                    evt.respond(response)
                evts.append(evt)
            return evts

        try:
            await consume()
        finally:
            await sandbox.__aexit__(None, None, None)

        # Approval prompted at most twice — first call (yes) and second
        # (alt). Third should NOT have been prompted because the batch
        # aborted on the alt response.
        assert approvals_seen == 2

        # Combined response contains: bash#1 result + alt instruction note.
        # bash#3 was never executed.
        user_msg = _last_user_response(client)
        assert "first" in user_msg
        assert "alternative instructions: use ls instead" in user_msg
        assert "third" not in user_msg


# ---------------------------------------------------------------------------
# Parser errors surfaced as tool_responses
# ---------------------------------------------------------------------------


class TestParseErrorSurfacing:
    @pytest.mark.asyncio
    async def test_all_blocks_malformed_feeds_errors_back(self, tmp_path: Path) -> None:
        client = _mock_llm_client(
            [
                # Round 1: malformed tool call
                "<tool_call>not json</tool_call>",
                # Round 2: model self-corrects
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo recovered"}}</tool_call>',
                # Round 3: wraps up
                "<answer>ok</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client)
        try:
            async for _ in agent.run_stream("test"):
                pass
        finally:
            await sandbox.__aexit__(None, None, None)

        # Round-1 → Round-2: user message should contain the parse error
        calls = client.chat.completions.stream.call_args_list
        round2_msgs = calls[1].kwargs["messages"]
        last_user = round2_msgs[-1]
        assert last_user["role"] == "user"
        assert "Error parsing block 0" in last_user["content"]
        assert "<tool_response>" in last_user["content"]

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_blocks(self, tmp_path: Path) -> None:
        client = _mock_llm_client(
            [
                # Round 1: valid + malformed + valid
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo a"}}</tool_call>\n'
                "<tool_call>not json</tool_call>\n"
                '<tool_call>{"name": "bash", "arguments": '
                '{"command": "echo c"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        agent, sandbox = await _build_agent(tmp_path, client)
        try:
            _ = [evt async for evt in agent.run_stream("test")]
        finally:
            await sandbox.__aexit__(None, None, None)

        user_msg = _last_user_response(client)
        # Three <tool_response> blocks: parse-error + bash#1 + bash#3
        assert user_msg.count("<tool_response>") == 3
        assert "Error parsing block 1" in user_msg
        assert "a" in user_msg
        assert "c" in user_msg
