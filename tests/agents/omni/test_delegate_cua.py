"""Tests for the delegate_cua harness layer.

Covers:
- DELEGATE_CUA_DEF schema shape (task / context / files params)
- build_delegate_cua_task helper: structure, error handling, truncation
- run_stream dispatch wires delegate_cua args through build_delegate_cua_task
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from magentic_ui.agents.base import Capability
from magentic_ui.agents.registry import AgentEntry, AgentRegistry
from magentic_ui.magentic_ui_config import ApprovalPolicy
from magentic_ui.sandbox._null import NullSandbox
from magentic_ui.teams.omniagent._omni_agent import OmniAgent
from magentic_ui.teams.omniagent._registry import (
    DELEGATE_CUA_DEF,
    _DELEGATE_CUA_FILE_PREVIEW_CHARS,
    _DELEGATE_CUA_FILES_TOTAL_CHARS,
    build_delegate_cua_task,
)


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


class TestSchema:
    def test_required_param_is_task_only(self) -> None:
        params = DELEGATE_CUA_DEF["function"]["parameters"]
        assert params["required"] == ["task"]
        assert set(params["properties"].keys()) == {"task", "context", "files"}

    def test_files_is_array_of_strings(self) -> None:
        files_def = DELEGATE_CUA_DEF["function"]["parameters"]["properties"]["files"]
        assert files_def["type"] == "array"
        assert files_def["items"] == {"type": "string"}

    def test_description_includes_when_to_use(self) -> None:
        desc = DELEGATE_CUA_DEF["function"]["description"]
        assert "WHEN TO USE" in desc
        assert "WHEN NOT TO USE" in desc


# ---------------------------------------------------------------------------
# build_delegate_cua_task — unit tests with mocked _read_file
# ---------------------------------------------------------------------------


def _patch_read(side_effect: list[dict[str, Any]] | dict[str, Any]):
    """Patch _read_file in _registry to return canned responses."""
    return patch(
        "magentic_ui.teams.omniagent._registry._read_file",
        new=AsyncMock(
            side_effect=side_effect if isinstance(side_effect, list) else None,
            return_value=None if isinstance(side_effect, list) else side_effect,
        ),
    )


class TestBuildDelegateCuaTask:
    @pytest.mark.asyncio
    async def test_task_only(self) -> None:
        result = await build_delegate_cua_task(
            MagicMock(), task="Look up the weather", context="", file_paths=[]
        )
        assert result == "Look up the weather"

    @pytest.mark.asyncio
    async def test_task_plus_context(self) -> None:
        result = await build_delegate_cua_task(
            MagicMock(),
            task="Apply for the role",
            context="URL is https://example.com/jobs/eng",
            file_paths=[],
        )
        assert "Apply for the role" in result
        assert "Background:\nURL is https://example.com/jobs/eng" in result
        assert result.index("Apply for the role") < result.index("Background:")

    @pytest.mark.asyncio
    async def test_files_inlined(self) -> None:
        with _patch_read(
            {"content": "Cheng Tan, software engineer.", "total_lines": 1}
        ):
            result = await build_delegate_cua_task(
                MagicMock(),
                task="Apply with my resume",
                context="",
                file_paths=["./resume.docx"],
            )
        assert "Apply with my resume" in result
        assert "File ./resume.docx (extracted to text):" in result
        assert "Cheng Tan, software engineer." in result

    @pytest.mark.asyncio
    async def test_missing_file_emits_inline_error(self) -> None:
        with _patch_read({"error": "file not found"}):
            result = await build_delegate_cua_task(
                MagicMock(),
                task="Open it",
                context="",
                file_paths=["./missing.txt"],
            )
        assert "[File ./missing.txt: file not found]" in result

    @pytest.mark.asyncio
    async def test_per_file_truncation(self) -> None:
        """File over per-file cap is head-truncated with a char-count marker."""
        big = "x" * (_DELEGATE_CUA_FILE_PREVIEW_CHARS + 1000)
        with _patch_read({"content": big, "total_lines": 1}):
            result = await build_delegate_cua_task(
                MagicMock(), task="t", context="", file_paths=["./big.txt"]
            )
        # Truncated body present
        assert "x" * _DELEGATE_CUA_FILE_PREVIEW_CHARS in result
        # Marker mentions actual size
        assert f"{_DELEGATE_CUA_FILE_PREVIEW_CHARS + 1000} total chars" in result
        # Full untruncated content NOT present
        assert "x" * (_DELEGATE_CUA_FILE_PREVIEW_CHARS + 500) not in result

    @pytest.mark.asyncio
    async def test_total_budget_exhausted_stops_iteration(self) -> None:
        """Many files exceed the total cap; later files are skipped or partially included."""
        # Three files each at the per-file cap → 3 * 8K = 24K, exceeds 16K total.
        per_file = "a" * _DELEGATE_CUA_FILE_PREVIEW_CHARS
        with _patch_read(
            [
                {"content": per_file, "total_lines": 1},
                {"content": per_file, "total_lines": 1},
                {"content": per_file, "total_lines": 1},
            ]
        ):
            result = await build_delegate_cua_task(
                MagicMock(),
                task="t",
                context="",
                file_paths=["a.txt", "b.txt", "c.txt"],
            )
        # First two files appear; total rendered output capped near budget.
        assert "File a.txt" in result
        assert "File b.txt" in result
        # Measure the actual rendered output size rather than counting only
        # "a" chars, which would ignore headers, separators, and markers.
        # Allow a small fixed overhead for task text and per-file headers.
        assert len(result) <= _DELEGATE_CUA_FILES_TOTAL_CHARS + 200


# ---------------------------------------------------------------------------
# Dispatch integration — run_stream → build_delegate_cua_task → fara stub
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
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[_make_completion(t) for t in responses]
    )
    return client


class _FaraStub:
    """Minimal sub-agent stub that records what it was called with."""

    def __init__(self) -> None:
        self.received_task: str | None = None

    async def run_stream(self, task: str = "", **_: Any):
        self.received_task = task
        from magentic_ui.agents.web_surfer.fara._types import StreamUpdate

        yield StreamUpdate(text="weather is sunny", additional_properties={})

    async def close(self) -> None:
        pass


class TestDispatchWiring:
    @pytest.mark.asyncio
    async def test_delegate_cua_call_routes_through_builder(
        self, tmp_path: Path
    ) -> None:
        """LLM emits delegate_cua with task/context/files; fara stub receives
        the assembled string with all three pieces inlined."""
        client = _mock_llm_client(
            [
                # Round 1: model delegates with all three params
                '<tool_call>{"name": "delegate_cua", "arguments": '
                '{"task": "Look up news", "context": "User in NYC", '
                '"files": ["./note.txt"]}}</tool_call>',
                # Round 2: model wraps up
                "<answer>done</answer>",
            ]
        )
        sandbox = NullSandbox(workspace=tmp_path)
        await sandbox.__aenter__()
        try:
            fara = _FaraStub()
            registry = AgentRegistry()
            registry.register(
                AgentEntry(
                    agent=fara,  # pyright: ignore[reportArgumentType]
                    tool_definition=DELEGATE_CUA_DEF,
                    capabilities=frozenset({Capability.WEB_BROWSING}),
                )
            )
            agent = OmniAgent(
                client=client,
                model="m",
                host_workspace=tmp_path,
                sandbox=sandbox,
                agent_registry=registry,
                approval_policy=ApprovalPolicy.AUTO_APPROVE,
            )

            with patch(
                "magentic_ui.teams.omniagent._registry._read_file",
                new=AsyncMock(return_value={"content": "user note", "total_lines": 1}),
            ):
                async for _ in agent.run_stream("test"):
                    pass
        finally:
            await sandbox.__aexit__(None, None, None)

        assert fara.received_task is not None
        assert "Look up news" in fara.received_task
        assert "Background:\nUser in NYC" in fara.received_task
        assert "File ./note.txt" in fara.received_task
        assert "user note" in fara.received_task

    @pytest.mark.asyncio
    async def test_delegate_cua_malformed_args_do_not_crash(
        self, tmp_path: Path
    ) -> None:
        """Model-emitted tool args may have wrong types (string instead of
        list, dict instead of string). Dispatch coerces to safe defaults
        rather than aborting the run."""
        client = _mock_llm_client(
            [
                # files is a string (not a list); context is a dict (not a
                # string). Without coercion, files would be iterated
                # char-by-char and context.strip() would raise.
                '<tool_call>{"name": "delegate_cua", "arguments": '
                '{"task": "go", "context": {"oops": 1}, '
                '"files": "./single.txt"}}</tool_call>',
                "<answer>done</answer>",
            ]
        )
        sandbox = NullSandbox(workspace=tmp_path)
        await sandbox.__aenter__()
        try:
            fara = _FaraStub()
            registry = AgentRegistry()
            registry.register(
                AgentEntry(
                    agent=fara,  # pyright: ignore[reportArgumentType]
                    tool_definition=DELEGATE_CUA_DEF,
                    capabilities=frozenset({Capability.WEB_BROWSING}),
                )
            )
            agent = OmniAgent(
                client=client,
                model="m",
                host_workspace=tmp_path,
                sandbox=sandbox,
                agent_registry=registry,
                approval_policy=ApprovalPolicy.AUTO_APPROVE,
            )

            read_mock = AsyncMock(return_value={"content": "x", "total_lines": 1})
            with patch(
                "magentic_ui.teams.omniagent._registry._read_file",
                new=read_mock,
            ):
                async for _ in agent.run_stream("test"):
                    pass
        finally:
            await sandbox.__aexit__(None, None, None)

        # Helper got the task; bad context/files were dropped, not iterated.
        assert fara.received_task == "go"
        read_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Pool-full handling — sub-agent raises BrowserSlotPoolFullError, OmniAgent
# yields an InputRequest and retries WITHOUT losing its in-memory state
# (issue #587).
# ---------------------------------------------------------------------------


class _PoolFullThenSucceedFara:
    """Sub-agent that fails the first run with BrowserSlotPoolFullError,
    then succeeds on the retry. Records the call count so we can assert
    OmniAgent retries instead of giving up.
    """

    def __init__(self) -> None:
        self.call_count = 0
        self.received_tasks: list[str] = []

    async def run_stream(self, task: str = "", **_: Any):
        from magentic_ui.agents.web_surfer.fara._types import StreamUpdate
        from magentic_ui.tools.playwright.browser import BrowserSlotPoolFullError

        self.call_count += 1
        self.received_tasks.append(task)
        if self.call_count == 1:
            raise BrowserSlotPoolFullError("pool full")
        yield StreamUpdate(text="weather is sunny", additional_properties={})

    async def close(self) -> None:
        pass


class TestPoolFullRetry:
    @pytest.mark.asyncio
    async def test_pool_full_yields_input_request_and_retries(
        self, tmp_path: Path
    ) -> None:
        """When delegate_cua hits a full browser pool, OmniAgent yields an
        InputRequest, awaits the user's reply, then retries the sub-agent
        call. OmniAgent's chat history / viewport / tool outputs are
        intentionally preserved across the retry — that's the whole point
        of handling this inside OmniAgent rather than tearing down the TM.
        """
        from magentic_ui.types import InputRequest

        client = _mock_llm_client(
            [
                # Round 1: model delegates a single web task.
                '<tool_call>{"name": "delegate_cua", "arguments": '
                '{"task": "Look up news"}}</tool_call>',
                # Round 2 (after successful retry): model wraps up.
                "<answer>done</answer>",
            ]
        )
        sandbox = NullSandbox(workspace=tmp_path)
        await sandbox.__aenter__()
        try:
            fara = _PoolFullThenSucceedFara()
            registry = AgentRegistry()
            registry.register(
                AgentEntry(
                    agent=fara,  # pyright: ignore[reportArgumentType]
                    tool_definition=DELEGATE_CUA_DEF,
                    capabilities=frozenset({Capability.WEB_BROWSING}),
                )
            )
            agent = OmniAgent(
                client=client,
                model="m",
                host_workspace=tmp_path,
                sandbox=sandbox,
                agent_registry=registry,
                approval_policy=ApprovalPolicy.AUTO_APPROVE,
            )

            input_requests: list[InputRequest] = []
            async for event in agent.run_stream("test"):
                if isinstance(event, InputRequest):
                    input_requests.append(event)
                    # Simulate the user replying — content doesn't matter,
                    # OmniAgent retries regardless (the abort path is Stop).
                    event.respond("continue")
        finally:
            await sandbox.__aexit__(None, None, None)

        # Exactly one InputRequest was emitted, with the user-facing text.
        assert len(input_requests) == 1
        assert "web browser" in input_requests[0].prompt.lower()
        assert "continue" in input_requests[0].prompt.lower()

        # Sub-agent was retried after the user reply: 1st call raised, 2nd
        # call ran. Both received the same task — OmniAgent didn't mangle it.
        assert fara.call_count == 2
        assert fara.received_tasks == ["Look up news", "Look up news"]
