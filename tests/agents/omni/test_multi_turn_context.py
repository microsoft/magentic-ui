"""Conversation history is preserved across run_stream calls."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import _PATH_QUOTING_NUDGE, OmniAgent


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
    state_dir: Path | None = None,
) -> tuple[OmniAgent, NullSandbox]:
    sandbox = NullSandbox(workspace=tmp_path)
    await sandbox.__aenter__()
    agent = OmniAgent(
        client=client,
        model="test-model",
        host_workspace=tmp_path,
        sandbox=sandbox,
        approval_policy=ApprovalPolicy.AUTO_APPROVE,
        state_dir=state_dir,
    )
    return agent, sandbox


@pytest.mark.asyncio
async def test_second_run_stream_sees_first_turn_history(tmp_path: Path) -> None:
    """After a final answer in turn 1, turn 2's LLM call must include
    both the prior task and the prior answer."""
    client = _mock_llm_client(
        [
            "<answer>first answer</answer>",
            "<answer>second answer</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client)
    try:
        async for _ in agent.run_stream("first task"):
            pass
        async for _ in agent.run_stream("second task"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    calls = client.chat.completions.create.call_args_list
    assert len(calls) == 2

    # The first user message of a session is prepended with a one-shot
    # bash path-quoting nudge; subsequent user messages are unchanged.
    first_task_msg = f"{_PATH_QUOTING_NUDGE}\nfirst task"

    # Turn 1: just system + first task
    turn1_msgs = calls[0].kwargs["messages"]
    turn1_roles = [m["role"] for m in turn1_msgs]
    assert turn1_roles == ["system", "user"]
    assert turn1_msgs[1]["content"] == first_task_msg

    # Turn 2: system + first task + first answer + second task
    turn2_msgs = calls[1].kwargs["messages"]
    turn2_roles = [m["role"] for m in turn2_msgs]
    assert turn2_roles == ["system", "user", "assistant", "user"]
    assert turn2_msgs[1]["content"] == first_task_msg
    assert turn2_msgs[2]["content"] == "<answer>first answer</answer>"
    assert turn2_msgs[3]["content"] == "second task"

    # Same system prompt across turns (built once)
    assert turn1_msgs[0]["content"] == turn2_msgs[0]["content"]


@pytest.mark.asyncio
async def test_chat_attribute_reused_across_runs(tmp_path: Path) -> None:
    """The OmniResponses instance is the same object across run_stream calls."""
    client = _mock_llm_client(
        [
            "<answer>a</answer>",
            "<answer>b</answer>",
        ]
    )
    agent, sandbox = await _build_agent(tmp_path, client)
    try:
        assert agent._chat is None
        async for _ in agent.run_stream("first"):
            pass
        chat_after_first = agent._chat
        assert chat_after_first is not None

        async for _ in agent.run_stream("second"):
            pass
        assert agent._chat is chat_after_first
    finally:
        await sandbox.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_state_persisted_to_disk_after_turn(tmp_path: Path) -> None:
    """A finished turn writes ``omni_state.json`` containing the conversation."""
    state_dir = tmp_path / "session"
    state_dir.mkdir()
    workspace = tmp_path / "run"
    workspace.mkdir()
    client = _mock_llm_client(["<answer>done</answer>"])
    agent, sandbox = await _build_agent(workspace, client, state_dir=state_dir)
    try:
        async for _ in agent.run_stream("first task"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    state_path = state_dir / "omni_state.json"
    assert state_path.exists()
    payload = json.loads(state_path.read_text())
    assert isinstance(payload["messages"], list)
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert payload["messages"][1]["content"].endswith("first task")
    assert payload["messages"][2]["content"] == "<answer>done</answer>"
    assert payload["compaction_count"] == 0


@pytest.mark.asyncio
async def test_second_agent_resumes_from_disk(tmp_path: Path) -> None:
    """A new OmniAgent pointed at the same state_dir sees prior history."""
    state_dir = tmp_path / "session"
    state_dir.mkdir()
    workspace = tmp_path / "run"
    workspace.mkdir()

    client_a = _mock_llm_client(["<answer>first answer</answer>"])
    agent_a, sandbox_a = await _build_agent(workspace, client_a, state_dir=state_dir)
    try:
        async for _ in agent_a.run_stream("first task"):
            pass
    finally:
        await sandbox_a.__aexit__(None, None, None)

    client_b = _mock_llm_client(["<answer>second answer</answer>"])
    agent_b, sandbox_b = await _build_agent(workspace, client_b, state_dir=state_dir)
    try:
        async for _ in agent_b.run_stream("second task"):
            pass
    finally:
        await sandbox_b.__aexit__(None, None, None)

    calls = client_b.chat.completions.create.call_args_list
    assert len(calls) == 1

    # Turn 1 nudged the original task; turn 2 in a new agent must keep that
    # nudged first message verbatim and append a plain follow-up.
    nudged_first = f"{_PATH_QUOTING_NUDGE}\nfirst task"
    resumed_msgs = calls[0].kwargs["messages"]
    roles = [m["role"] for m in resumed_msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert resumed_msgs[1]["content"] == nudged_first
    assert resumed_msgs[2]["content"] == "<answer>first answer</answer>"
    assert resumed_msgs[3]["content"] == "second task"


@pytest.mark.asyncio
async def test_resume_preserves_delegate_cua_tool_response(tmp_path: Path) -> None:
    """A persisted ``<tool_response>`` from delegate_cua survives resume as plain text."""
    state_dir = tmp_path / "session"
    state_dir.mkdir()
    workspace = tmp_path / "run"
    workspace.mkdir()

    nudged_first = f"{_PATH_QUOTING_NUDGE}\nbrowse to example.com"
    seeded = {
        "messages": [
            {"role": "system", "content": "ignored — replaced by current prompt"},
            {"role": "user", "content": nudged_first},
            {
                "role": "assistant",
                "content": "<tool_call>delegate_cua...</tool_call>",
            },
            {
                "role": "user",
                "content": "<tool_response>Fara opened example.com and found the headline</tool_response>",
            },
            {"role": "assistant", "content": "<answer>headline found</answer>"},
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

    client = _mock_llm_client(["<answer>followed up</answer>"])
    agent, sandbox = await _build_agent(workspace, client, state_dir=state_dir)
    try:
        async for _ in agent.run_stream("what else did you see?"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    messages = client.chat.completions.create.call_args_list[0].kwargs["messages"]
    contents = [m["content"] for m in messages]
    # Fresh system prompt at index 0 — should not equal the seeded placeholder.
    assert contents[0] != "ignored — replaced by current prompt"
    # Delegate-cua tool_call and tool_response survive round-trip as plain text.
    assert any("delegate_cua" in c for c in contents)
    assert any("<tool_response>Fara opened example.com" in c for c in contents)
    # Follow-up appears without the nudge prefix on the resumed turn.
    assert contents[-1] == "what else did you see?"


@pytest.mark.asyncio
async def test_resume_restores_viewport(tmp_path: Path) -> None:
    """Persisted viewport values are restored on the next run_stream."""
    state_dir = tmp_path / "session"
    state_dir.mkdir()
    workspace = tmp_path / "run"
    workspace.mkdir()

    seeded = {
        "messages": [
            {"role": "system", "content": "old"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "<answer>done</answer>"},
        ],
        "total_tokens": 0,
        "prev_handoff": None,
        "compaction_count": 0,
        "viewport": {
            "current_file": "/workspace/notes.md",
            "current_line": 42,
            "scroll_count": 3,
        },
    }
    (state_dir / "omni_state.json").write_text(json.dumps(seeded))

    client = _mock_llm_client(["<answer>noop</answer>"])
    agent, sandbox = await _build_agent(workspace, client, state_dir=state_dir)
    try:
        # Restoration happens during run_stream's lazy-init, so viewport is
        # empty until the first turn opens. After that, prior values are
        # available to tool calls.
        async for _ in agent.run_stream("follow-up"):
            pass
        assert agent._viewport.current_file == "/workspace/notes.md"
        assert agent._viewport.current_line == 42
        assert agent._viewport.scroll_count == 3
    finally:
        await sandbox.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_resume_with_corrupted_state_starts_fresh(tmp_path: Path) -> None:
    """A garbage state file leaves the agent in a normal fresh-start path."""
    state_dir = tmp_path / "session"
    state_dir.mkdir()
    (state_dir / "omni_state.json").write_text("not json {{{")
    workspace = tmp_path / "run"
    workspace.mkdir()

    client = _mock_llm_client(["<answer>ok</answer>"])
    agent, sandbox = await _build_agent(workspace, client, state_dir=state_dir)
    try:
        async for _ in agent.run_stream("hello"):
            pass
    finally:
        await sandbox.__aexit__(None, None, None)

    # Fresh start: the first user message should carry the nudge prefix,
    # exactly like a never-resumed agent.
    msgs = client.chat.completions.create.call_args_list[0].kwargs["messages"]
    assert msgs[1]["content"] == f"{_PATH_QUOTING_NUDGE}\nhello"


@pytest.mark.asyncio
async def test_no_state_dir_disables_persistence(tmp_path: Path) -> None:
    """With ``state_dir=None`` no file is written and behavior is unchanged."""
    client = _mock_llm_client(["<answer>ok</answer>"])
    agent, sandbox = await _build_agent(tmp_path, client, state_dir=None)
    try:
        async for _ in agent.run_stream("hello"):
            pass
        assert agent._state_path is None
    finally:
        await sandbox.__aexit__(None, None, None)
    # No omni_state.json anywhere under tmp_path
    assert list(tmp_path.rglob("omni_state.json")) == []
