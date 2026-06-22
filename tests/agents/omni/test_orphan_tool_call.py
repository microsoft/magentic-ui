"""Orphan tool_call detection on the next user turn after a Stop."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from magentic_ui.agents.base import Capability
from magentic_ui.agents.registry import AgentEntry, AgentRegistry
from magentic_ui.agents.web_surfer.fara._types import StreamUpdate
from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import _PATH_QUOTING_NUDGE, OmniAgent


class _FakeSubAgent:
    """Sub-agent stub returning a canned recap + structured handoff info."""

    def __init__(
        self,
        summary: str = "Found gift A and gift B.",
        last_url: str = "https://example.com/last-page",
        facts: list[str] | None = None,
    ) -> None:
        self._summary = summary
        self._last_url = last_url
        self._facts = facts if facts is not None else ["gift A is age-appropriate"]
        self.summarize_calls = 0

    async def run_stream(
        self, task: str, **kwargs: Any
    ):  # pragma: no cover - not exercised
        yield StreamUpdate(text=f"done: {task}")

    async def summarize_progress(self) -> tuple[str, dict[str, Any]]:
        self.summarize_calls += 1
        return self._summary, {
            "status": "incomplete",
            "reason": "orphan_recovery",
            "last_url": self._last_url,
            "facts": self._facts,
        }

    async def close(self) -> None:
        return None


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


def _make_delegate_tool_def() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "delegate_cua",
            "description": "Delegate to web agent",
            "parameters": {"type": "object", "properties": {}},
        },
    }


async def _build_agent(
    tmp_path: Path,
    client: MagicMock,
    *,
    state_dir: Path | None = None,
    sub_agent: _FakeSubAgent | None = None,
) -> tuple[OmniAgent, NullSandbox]:
    sandbox = NullSandbox(workspace=tmp_path)
    await sandbox.__aenter__()
    registry = AgentRegistry()
    if sub_agent is not None:
        registry.register(
            AgentEntry(
                agent=sub_agent,
                tool_definition=_make_delegate_tool_def(),
                capabilities=frozenset({Capability.WEB_BROWSING}),
            )
        )
    agent = OmniAgent(
        client=client,
        model="test-model",
        host_workspace=tmp_path,
        sandbox=sandbox,
        agent_registry=registry,
        approval_policy=ApprovalPolicy.AUTO_APPROVE,
        state_dir=state_dir,
    )
    return agent, sandbox


@pytest.mark.asyncio
async def test_orphan_delegate_cua_injects_subagent_summary(tmp_path: Path) -> None:
    """An assistant message with delegate_cua tool_call and no tool_response
    must trigger summarize_progress and inject the recap as a synthetic
    <tool_response> on the next turn."""
    sub = _FakeSubAgent(summary="Snap Circuits Jr. is the top candidate.")
    client = _mock_llm_client(["<answer>here you go</answer>"])
    agent, sandbox = await _build_agent(tmp_path, client, sub_agent=sub)
    try:
        # Pump one prior turn so _chat is constructed, then plant an
        # orphan as the last entry in its message log.
        async for _ in agent.run_stream("seed"):
            pass
        assert agent._chat is not None
        agent._chat._messages.append(  # noqa: SLF001
            {
                "role": "assistant",
                "content": '<tool_call>{"name":"delegate_cua","arguments":{"task":"find stem gifts"}}</tool_call>',
            }
        )
        from ._stream_mock import install_stream_mock

        install_stream_mock(client, [_make_completion("<answer>resumed</answer>")])

        async for _ in agent.run_stream("where are we?"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    assert sub.summarize_calls == 1
    sent = client.chat.completions.stream.call_args.kwargs["messages"]
    # Final user-role message before any new assistant turn must include
    # both the synthetic tool_response and the new user task.
    contents = [m["content"] for m in sent if m["role"] == "user"]
    # Omni assembles the envelope from the sub-agent's (text, info):
    # NOTE (orphan) + LAST URL + SUMMARY + FACTS, inside <tool_response>.
    assert any(
        "<tool_response>" in c
        and "NOTE:" in c
        and "Snap Circuits Jr. is the top candidate." in c
        and "LAST URL: https://example.com/last-page" in c
        and "FACTS:" in c
        for c in contents
    )
    assert any("where are we?" in c for c in contents)


@pytest.mark.asyncio
async def test_orphan_non_subagent_uses_generic_fallback(tmp_path: Path) -> None:
    """An orphan bash tool_call gets a generic fallback message — no
    summarize_progress to call since bash isn't a registered sub-agent."""
    client = _mock_llm_client(["<answer>ok</answer>"])
    agent, sandbox = await _build_agent(tmp_path, client)
    try:
        async for _ in agent.run_stream("seed"):
            pass
        assert agent._chat is not None
        agent._chat._messages.append(  # noqa: SLF001
            {
                "role": "assistant",
                "content": '<tool_call>{"name":"bash","arguments":{"command":"sleep 60"}}</tool_call>',
            }
        )
        from ._stream_mock import install_stream_mock

        install_stream_mock(client, [_make_completion("<answer>ok</answer>")])

        async for _ in agent.run_stream("retry?"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    sent = client.chat.completions.stream.call_args.kwargs["messages"]
    user_contents = [m["content"] for m in sent if m["role"] == "user"]
    assert any("previous `bash` call was interrupted" in c for c in user_contents)
    assert any("retry?" in c for c in user_contents)


@pytest.mark.asyncio
async def test_no_orphan_when_last_message_is_answer(tmp_path: Path) -> None:
    """Clean completion (assistant message ends with <answer>) must not
    trigger orphan-detection on the next turn."""
    sub = _FakeSubAgent()
    client = _mock_llm_client(["<answer>first</answer>", "<answer>second</answer>"])
    agent, sandbox = await _build_agent(tmp_path, client, sub_agent=sub)
    try:
        async for _ in agent.run_stream("hello"):
            pass
        async for _ in agent.run_stream("again"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    assert sub.summarize_calls == 0
    sent_second = client.chat.completions.stream.call_args_list[1].kwargs["messages"]
    user_contents = [m["content"] for m in sent_second if m["role"] == "user"]
    # Only the nudged first task and the plain follow-up appear; no synthetic
    # tool_response sneaked in.
    assert not any("<tool_response>" in c for c in user_contents)


@pytest.mark.asyncio
async def test_fresh_session_no_orphan_injection(tmp_path: Path) -> None:
    """Day-one session with no prior history must not inject a synthetic
    response — there's nothing in _messages besides the system prompt."""
    sub = _FakeSubAgent()
    client = _mock_llm_client(["<answer>hi</answer>"])
    agent, sandbox = await _build_agent(tmp_path, client, sub_agent=sub)
    try:
        async for _ in agent.run_stream("first task"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    assert sub.summarize_calls == 0
    sent = client.chat.completions.stream.call_args.kwargs["messages"]
    user_contents = [m["content"] for m in sent if m["role"] == "user"]
    assert not any("<tool_response>" in c for c in user_contents)
    assert user_contents[0] == f"{_PATH_QUOTING_NUDGE}\nfirst task"


@pytest.mark.asyncio
async def test_orphan_detected_on_resume_from_disk(tmp_path: Path) -> None:
    """A new OmniAgent constructed from omni_state.json finds the orphan
    and calls the registered sub-agent's summarize_progress — proving
    the resume path works without the original instance alive."""
    import json

    state_dir = tmp_path / "session"
    state_dir.mkdir()
    workspace = tmp_path / "run"
    workspace.mkdir()

    seeded = {
        "messages": [
            {"role": "system", "content": "old prompt"},
            {"role": "user", "content": f"{_PATH_QUOTING_NUDGE}\nfind gifts"},
            {
                "role": "assistant",
                "content": '<tool_call>{"name":"delegate_cua","arguments":{"task":"find gifts"}}</tool_call>',
            },
        ],
        "total_tokens": 0,
        "prev_handoff": None,
        "compaction_count": 0,
        "viewport": {
            "current_file": None,
            "current_line": 0,
            "scroll_count": 0,
        },
    }
    (state_dir / "omni_state.json").write_text(json.dumps(seeded))

    sub = _FakeSubAgent(summary="Found Snap Circuits Jr. and rejected Gravity Maze.")
    client = _mock_llm_client(["<answer>resumed</answer>"])
    agent, sandbox = await _build_agent(
        workspace, client, state_dir=state_dir, sub_agent=sub
    )
    try:
        async for _ in agent.run_stream("where are we?"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    assert sub.summarize_calls == 1
    sent = client.chat.completions.stream.call_args.kwargs["messages"]
    user_contents = [m["content"] for m in sent if m["role"] == "user"]
    # Resume-from-disk path also builds the full envelope Omni-side.
    assert any(
        "<tool_response>" in c
        and "NOTE:" in c
        and "Found Snap Circuits Jr. and rejected Gravity Maze." in c
        and "LAST URL: https://example.com/last-page" in c
        for c in user_contents
    )


@pytest.mark.asyncio
async def test_summarize_failure_falls_back_to_generic(tmp_path: Path) -> None:
    """If summarize_progress raises, the orphan still gets closed with a
    generic stop notice — no exception propagates to the caller."""

    class Broken(_FakeSubAgent):
        async def summarize_progress(self) -> tuple[str, dict[str, Any]]:
            raise RuntimeError("summarizer is down")

    sub = Broken()
    client = _mock_llm_client(["<answer>ok</answer>"])
    agent, sandbox = await _build_agent(tmp_path, client, sub_agent=sub)
    try:
        async for _ in agent.run_stream("seed"):
            pass
        assert agent._chat is not None
        agent._chat._messages.append(  # noqa: SLF001
            {
                "role": "assistant",
                "content": '<tool_call>{"name":"delegate_cua","arguments":{"task":"x"}}</tool_call>',
            }
        )
        from ._stream_mock import install_stream_mock

        install_stream_mock(client, [_make_completion("<answer>ok</answer>")])

        async for _ in agent.run_stream("retry?"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    sent = client.chat.completions.stream.call_args.kwargs["messages"]
    user_contents = [m["content"] for m in sent if m["role"] == "user"]
    assert any(
        "previous `delegate_cua` call was interrupted" in c for c in user_contents
    )
