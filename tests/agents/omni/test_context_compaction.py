"""Unit tests for OmniResponses context compaction.

Tests exercise OmniResponses in isolation with a mocked AsyncOpenAI
client — no sandbox, no tools, no WebSocket. The goal is to verify the
compaction algorithm and emergency handler behave correctly across
threshold edge cases, hoisting, history reconstruction, prev-handoff
chaining, and error propagation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import openai
import pytest

from magentic_ui.agents.message_schemas import MessageType
from magentic_ui.teams.omniagent._compaction import (
    HANDOFF_PREFIX,
    build_handoff_message,
    extract_opened_files,
    extract_summary,
)
from magentic_ui.teams.omniagent._responses import OmniResponses


# ---------------------------------------------------------------------------
# Helpers — plain module-level functions, no pytest fixtures
# ---------------------------------------------------------------------------


def _make_completion(text: str, total_tokens: int = 10) -> MagicMock:
    """Build a minimal MagicMock that quacks like a ChatCompletion."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage = MagicMock(
        prompt_tokens=total_tokens - 2,
        completion_tokens=2,
        total_tokens=total_tokens,
    )
    return response


def _bad_request(code: str | int, message: str = "") -> openai.BadRequestError:
    """Build a BadRequestError with a specific code."""
    response = MagicMock()
    response.status_code = 400
    response.request = MagicMock()
    err = openai.BadRequestError(
        message=message or code,
        response=response,
        body={"code": code, "message": message or code},
    )
    err.code = code  # ensure the attribute is set (openai SDK exposes this)
    return err


def _mock_llm_client(responses: list[Any]) -> MagicMock:
    """Build a MagicMock AsyncOpenAI client with canned responses.

    Successive calls to ``client.chat.completions.stream()`` consume
    ``responses`` in order. Each element is either a string (returned
    as a completion with ``total_tokens=10``), a ``(text, total_tokens)``
    tuple, or an exception instance (raised from the stream context
    manager when that call happens).
    """
    from ._stream_mock import install_stream_mock

    client = MagicMock()
    items: list[Any] = []
    for item in responses:
        if isinstance(item, Exception):
            items.append(item)
        elif isinstance(item, tuple):
            text, tokens = item
            items.append(_make_completion(text, tokens))
        else:
            items.append(_make_completion(item))
    install_stream_mock(client, items)
    return client


def _build_chat(
    client: MagicMock,
    *,
    threshold: int | None = 100_000,
    system: str = "You are a helpful agent.",
    transcripts_dir: Path | None = None,
    observability_dir: Path | None = None,
    guest_transcripts_dir: Path | None = None,
) -> OmniResponses:
    """Wrap a mock client in an OmniResponses with sensible test defaults."""
    if transcripts_dir is not None and observability_dir is None:
        observability_dir = transcripts_dir
    return OmniResponses(
        client=client,
        model="gpt-test",
        system_prompt=system,
        compaction_threshold=threshold,
        source_name="OmniAgent",
        transcripts_dir=transcripts_dir,
        observability_dir=observability_dir,
        guest_transcripts_dir=guest_transcripts_dir,
    )


def _read_trace(path: Path) -> list[dict[str, Any]]:
    """Parse a trace.jsonl file into a list of event dicts."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


# ---------------------------------------------------------------------------
# build_handoff_message — helper in _compaction.py
# ---------------------------------------------------------------------------


class TestBuildHandoffMessage:
    def test_first_compaction_has_no_prev(self):
        out = build_handoff_message(prev_handoff=None, summary="task progress so far")
        assert out.startswith(HANDOFF_PREFIX)
        assert "task progress so far" in out
        assert "Previous handoff" not in out

    def test_chains_previous_handoff(self):
        out = build_handoff_message(
            prev_handoff="earlier summary",
            summary="latest summary",
        )
        assert HANDOFF_PREFIX in out
        assert "Previous handoff" in out
        assert "earlier summary" in out
        assert "latest summary" in out
        # Order matters: prev comes before fresh summary
        assert out.index("earlier summary") < out.index("latest summary")

    def test_includes_transcript_path_when_provided(self):
        out = build_handoff_message(
            prev_handoff=None,
            summary="latest summary",
            transcript_path=Path("/workspace/.agent/transcripts/transcript.md"),
        )
        assert "/workspace/.agent/transcripts/transcript.md" in out
        assert "grep" in out  # pointer mentions grep as a lookup option
        # Pointer prose should describe the file as the agent's own log,
        # not as a generic "transcript" — that overload caused models to
        # confuse it with task-domain transcripts in real evals.
        assert "agent's own log" in out
        assert "action log" in out

    def test_omits_transcript_pointer_when_path_is_none(self):
        out = build_handoff_message(
            prev_handoff=None,
            summary="latest summary",
            transcript_path=None,
        )
        assert "action log" not in out.lower()
        assert "grep" not in out.lower()

    def test_includes_files_reviewed_block_when_provided(self):
        out = build_handoff_message(
            prev_handoff=None,
            summary="latest summary",
            files_reviewed=["foo.docx", "bar.txt"],
        )
        assert "Files already reviewed:" in out
        assert "- foo.docx" in out
        assert "- bar.txt" in out

    def test_omits_files_reviewed_block_when_empty(self):
        out = build_handoff_message(
            prev_handoff=None,
            summary="latest summary",
            files_reviewed=[],
        )
        assert "Files already reviewed:" not in out

    def test_omits_files_reviewed_block_when_none(self):
        out = build_handoff_message(
            prev_handoff=None,
            summary="latest summary",
        )
        assert "Files already reviewed:" not in out


# ---------------------------------------------------------------------------
# extract_opened_files — file-path extraction from `open` tool calls
# ---------------------------------------------------------------------------


class TestExtractOpenedFiles:
    def test_extracts_paths_from_open_calls(self):
        messages = [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "do work"},
            {
                "role": "assistant",
                "content": (
                    'thinking...\n<tool_call>{"name":"open",'
                    '"arguments":{"path":"foo.docx"}}</tool_call>'
                ),
            },
            {"role": "user", "content": "<tool_response>...</tool_response>"},
            {
                "role": "assistant",
                "content": (
                    '<tool_call>{"name":"open",'
                    '"arguments":{"path":"bar.txt"}}</tool_call>'
                ),
            },
        ]
        assert extract_opened_files(messages) == ["bar.txt", "foo.docx"]

    def test_dedupes_repeated_opens(self):
        messages = [
            {
                "role": "assistant",
                "content": (
                    '<tool_call>{"name":"open",'
                    '"arguments":{"path":"foo.docx"}}</tool_call>'
                ),
            },
            {
                "role": "assistant",
                "content": (
                    '<tool_call>{"name":"open",'
                    '"arguments":{"path":"foo.docx"}}</tool_call>'
                ),
            },
        ]
        assert extract_opened_files(messages) == ["foo.docx"]

    def test_skips_non_open_tool_calls(self):
        messages = [
            {
                "role": "assistant",
                "content": (
                    '<tool_call>{"name":"bash","arguments":{"command":"ls"}}</tool_call>'
                ),
            },
        ]
        assert extract_opened_files(messages) == []

    def test_skips_user_and_system_messages(self):
        messages = [
            {
                "role": "user",
                "content": (
                    '<tool_call>{"name":"open",'
                    '"arguments":{"path":"foo.docx"}}</tool_call>'
                ),
            },
            {"role": "system", "content": "system text"},
        ]
        assert extract_opened_files(messages) == []

    def test_handles_assistant_without_tool_calls(self):
        messages = [{"role": "assistant", "content": "just thinking, no tools"}]
        assert extract_opened_files(messages) == []

    def test_skips_internal_agent_paths(self):
        messages = [
            {
                "role": "assistant",
                "content": (
                    '<tool_call>{"name":"open","arguments":'
                    '{"path":"foo.docx"}}</tool_call>\n'
                    '<tool_call>{"name":"open","arguments":'
                    '{"path":"/sessions/X/workspace/.agent/tool_outputs/output_abc"}}'
                    "</tool_call>\n"
                    '<tool_call>{"name":"open","arguments":'
                    '{"path":".agent/transcripts/transcript.md"}}</tool_call>\n'
                    '<tool_call>{"name":"open","arguments":'
                    '{"path":"bar.txt"}}</tool_call>'
                ),
            },
        ]
        # Spill files and transcript log filtered out; task data files kept.
        assert extract_opened_files(messages) == ["bar.txt", "foo.docx"]


# ---------------------------------------------------------------------------
# extract_summary — tolerant tag extraction for compaction summaries
# ---------------------------------------------------------------------------


class TestExtractSummary:
    def test_both_tags(self):
        assert extract_summary("<summary>foo</summary>") == "foo"

    def test_open_tag_only(self):
        assert extract_summary("<summary>foo bar") == "foo bar"

    def test_close_tag_only(self):
        assert extract_summary("foo bar</summary>") == "foo bar"

    def test_no_tags_falls_back_to_raw(self):
        assert extract_summary("just prose") == "just prose"

    def test_whitespace_stripped(self):
        assert extract_summary("<summary>\n  foo  \n</summary>") == "foo"

    def test_extra_content_after_close_dropped(self):
        out = extract_summary("<summary>real content</summary>trailing junk")
        assert out == "real content"

    def test_close_before_open_tag_does_not_misfire(self):
        # If a stray ``</summary>`` appears before the real wrapper open,
        # we should still anchor on the open tag and find the close after it.
        out = extract_summary("noise</summary><summary>real</summary>")
        assert out == "real"

    def test_stray_close_before_open_with_no_close_after(self):
        # ``str.index`` would raise ``ValueError`` here because the only
        # ``</summary>`` is before the ``<summary>``. ``str.find``-based
        # implementation should fall through to the open-only branch
        # and return everything after ``<summary>``.
        out = extract_summary("noise</summary><summary>real")
        assert out == "real"


# ---------------------------------------------------------------------------
# maybe_compact — threshold edge cases
# ---------------------------------------------------------------------------


class TestMaybeCompact:
    @pytest.mark.asyncio
    async def test_skips_when_threshold_none(self):
        client = _mock_llm_client(["resp"])
        chat = _build_chat(client, threshold=None)
        await chat.generate("hi")
        events = [evt async for evt in chat.maybe_compact()]
        assert events == []

    @pytest.mark.asyncio
    async def test_skips_below_threshold(self):
        client = _mock_llm_client([("resp", 50)])
        chat = _build_chat(client, threshold=100)
        await chat.generate("hi")
        events = [evt async for evt in chat.maybe_compact()]
        assert events == []
        # History unchanged: system + user + assistant
        assert len(chat.messages) == 3

    @pytest.mark.asyncio
    async def test_triggers_at_threshold(self):
        # First call: exceeds threshold. Second call: the compaction summary.
        client = _mock_llm_client([("long response", 150), ("SUMMARY TEXT", 20)])
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        events = [evt async for evt in chat.maybe_compact()]
        assert len(events) == 2
        start_props = events[0].additional_properties
        end_props = events[1].additional_properties
        assert start_props is not None and start_props["type"] == "compaction_start"
        assert start_props["tokens_before"] == 150
        assert end_props is not None and end_props["type"] == "compaction_end"

    @pytest.mark.asyncio
    async def test_event_source_name(self):
        client = _mock_llm_client([("resp", 200), ("summary", 20)])
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        events = [evt async for evt in chat.maybe_compact()]
        assert events[0].additional_properties["source"] == "OmniAgent"
        assert events[1].additional_properties["source"] == "OmniAgent"


# ---------------------------------------------------------------------------
# _compact — history reconstruction
# ---------------------------------------------------------------------------


class TestCompactHistoryShape:
    @pytest.mark.asyncio
    async def test_preserves_system_message(self):
        client = _mock_llm_client([("resp", 200), ("SUMMARY", 20)])
        chat = _build_chat(client, threshold=100, system="You are ROLE X.")
        await chat.generate("task")
        _ = [evt async for evt in chat.maybe_compact()]
        assert chat.messages[0]["role"] == "system"
        assert chat.messages[0]["content"] == "You are ROLE X."

    @pytest.mark.asyncio
    async def test_preserves_real_user_messages(self):
        client = _mock_llm_client([("resp", 200), ("SUMMARY", 20)])
        chat = _build_chat(client, threshold=100)
        await chat.generate("original task")
        _ = [evt async for evt in chat.maybe_compact()]
        msgs = chat.messages
        user_contents = [m["content"] for m in msgs if m["role"] == "user"]
        assert "original task" in user_contents

    @pytest.mark.asyncio
    async def test_drops_tool_response_messages(self):
        client = _mock_llm_client(
            [("resp1", 20), ("resp2", 40), ("resp3", 200), ("SUMMARY", 20)]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        # Simulate a tool response being queued + sent
        await chat.generate("<tool_response>tool result 1</tool_response>")
        await chat.generate("<tool_response>tool result 2</tool_response>")
        # Now we're over threshold, trigger compaction
        _ = [evt async for evt in chat.maybe_compact()]
        # Tool responses should NOT appear verbatim — only summarized
        for m in chat.messages:
            content = m.get("content", "")
            if isinstance(content, str):
                assert not content.startswith(
                    "<tool_response>"
                ), f"tool_response leaked verbatim into compacted history: {content}"

    @pytest.mark.asyncio
    async def test_drops_tool_response_with_leading_whitespace(self):
        """Regression: leading whitespace must not bypass the filter.

        Earlier versions used plain ``startswith`` which allowed any
        leading newline or space to smuggle a ``<tool_response>``
        payload into compacted history. The filter now normalizes with
        ``lstrip()`` before matching.
        """
        client = _mock_llm_client(
            [("resp1", 20), ("resp2", 40), ("resp3", 200), ("SUMMARY", 20)]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        await chat.generate("\n<tool_response>tool result with newline</tool_response>")
        await chat.generate("   <tool_response>tool result with spaces</tool_response>")
        _ = [evt async for evt in chat.maybe_compact()]
        for m in chat.messages:
            content = m.get("content", "")
            if isinstance(content, str):
                assert "<tool_response>" not in content, (
                    f"whitespace-prefixed tool_response leaked into "
                    f"compacted history: {content!r}"
                )

    @pytest.mark.asyncio
    async def test_appends_handoff_as_user_message(self):
        client = _mock_llm_client([("resp", 200), ("FRESH SUMMARY", 20)])
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        _ = [evt async for evt in chat.maybe_compact()]
        msgs = chat.messages
        # The last non-hoisted user message should contain the handoff
        handoff_msgs = [
            m
            for m in msgs
            if m["role"] == "user"
            and isinstance(m["content"], str)
            and HANDOFF_PREFIX in m["content"]
        ]
        assert len(handoff_msgs) == 1
        assert "FRESH SUMMARY" in handoff_msgs[0]["content"]

    @pytest.mark.asyncio
    async def test_resets_total_tokens_to_zero(self):
        client = _mock_llm_client([("resp", 200), ("SUMMARY", 20)])
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        assert chat.total_tokens == 200
        _ = [evt async for evt in chat.maybe_compact()]
        assert chat.total_tokens == 0


# ---------------------------------------------------------------------------
# _compact — prev_handoff chaining across multiple compactions
# ---------------------------------------------------------------------------


class TestPrevHandoffChaining:
    @pytest.mark.asyncio
    async def test_second_compaction_includes_first_summary(self):
        client = _mock_llm_client(
            [
                ("resp1", 200),  # triggers first compaction
                ("FIRST SUMMARY", 20),  # first compaction summary
                ("resp2", 300),  # triggers second compaction
                ("SECOND SUMMARY", 20),  # second compaction summary
            ]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        _ = [evt async for evt in chat.maybe_compact()]
        # At this point, prev_handoff == "FIRST SUMMARY"
        assert chat._prev_handoff == "FIRST SUMMARY"

        await chat.generate("follow-up")
        _ = [evt async for evt in chat.maybe_compact()]
        # Second compaction's handoff should chain the first
        handoff_msgs = [
            m
            for m in chat.messages
            if m["role"] == "user"
            and isinstance(m["content"], str)
            and HANDOFF_PREFIX in m["content"]
        ]
        assert len(handoff_msgs) == 1  # only the latest handoff remains
        latest = handoff_msgs[0]["content"]
        assert "FIRST SUMMARY" in latest
        assert "SECOND SUMMARY" in latest
        assert "Previous handoff" in latest


# ---------------------------------------------------------------------------
# _compact — hoisting pending tool calls
# ---------------------------------------------------------------------------


class TestHoisting:
    @pytest.mark.asyncio
    async def test_hoists_pending_tool_call(self):
        # First assistant message contains a tool call. Second call is the
        # compaction summary. We push enough tokens to trigger compaction
        # right after the first generate.
        client = _mock_llm_client(
            [
                (
                    "planning\n"
                    '<tool_call>{"name": "bash", "arguments": {"cmd": "ls"}}</tool_call>',
                    200,
                ),
                ("SUMMARY", 20),
            ]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        _ = [evt async for evt in chat.maybe_compact()]
        # The trailing assistant-with-tool-call should still be present
        last = chat.messages[-1]
        assert last["role"] == "assistant"
        assert "<tool_call>" in last["content"]

    @pytest.mark.asyncio
    async def test_no_hoist_on_plain_assistant_text(self):
        client = _mock_llm_client(
            [
                ("just some text", 200),
                ("SUMMARY", 20),
            ]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        _ = [evt async for evt in chat.maybe_compact()]
        # Assistant had no <tool_call>; should NOT be hoisted
        # Trailing message should be the handoff
        assert chat.messages[-1]["role"] == "user"
        assert HANDOFF_PREFIX in chat.messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_restores_hoisted_on_summary_failure(self):
        """Regression: if the summarize call raises, the popped tool_call
        assistant message must be restored to history.

        Without the try/except in ``_compact``, a transient failure
        during summarization would silently drop the agent's pending
        tool action, leaving history inconsistent for the next step.
        """
        tool_call_msg = (
            "planning\n"
            '<tool_call>{"name": "bash", "arguments": {"cmd": "ls"}}</tool_call>'
        )
        client = _mock_llm_client(
            [
                (tool_call_msg, 200),
                # Compaction summary call (persist=False) fails with a
                # non-context-length BadRequestError so it propagates
                # straight out of generate() into _compact()'s handler.
                _bad_request("invalid_request", "simulated summary failure"),
            ]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        history_before = list(chat.messages)
        assert "<tool_call>" in history_before[-1]["content"]

        with pytest.raises(openai.BadRequestError):
            async for _ in chat.maybe_compact():
                pass

        # Hoisted message restored verbatim at the tail.
        assert chat.messages[-1]["role"] == "assistant"
        assert "<tool_call>" in chat.messages[-1]["content"]
        assert chat.messages == history_before
        # Commit path did not run: prev_handoff unset, tokens unchanged.
        assert chat._prev_handoff is None
        assert chat.total_tokens == 200


# ---------------------------------------------------------------------------
# Emergency handler — context_length_exceeded
# ---------------------------------------------------------------------------


class TestEmergencyHandler:
    @pytest.mark.asyncio
    async def test_lowers_threshold_and_retries(self):
        # Build history via an initial successful call, then the second
        # call raises context_length_exceeded and triggers the emergency
        # handler: compaction (persist=False summary) followed by a
        # retry of the original call.
        client = _mock_llm_client(
            [
                "priming response",  # initial generate succeeds
                _bad_request(
                    "context_length_exceeded",
                    "This model's maximum context length is 128000 tokens.",
                ),
                "EMERGENCY SUMMARY",
                "recovery response",
            ]
        )
        chat = _build_chat(client, threshold=10_000)
        await chat.generate("task")
        # Now call again — the second call raises, triggering emergency
        result = await chat.generate("another task")
        assert result == "recovery response"
        # Threshold should have been lowered to 75% of 128000
        assert chat._compaction_threshold == int(128_000 * 0.75)

    @pytest.mark.asyncio
    async def test_falls_back_when_regex_no_match(self):
        client = _mock_llm_client(
            [
                "priming",
                _bad_request(
                    "context_length_exceeded",
                    "Some error without a parseable max",
                ),
                "SUMMARY",
                "recovery",
            ]
        )
        chat = _build_chat(client, threshold=10_000)
        await chat.generate("task")
        await chat.generate("trigger")
        # 10_000 * 0.75 = 7_500 (unified fraction — same as the parsed-max path)
        assert chat._compaction_threshold == 7_500

    @pytest.mark.asyncio
    async def test_retry_preserves_new_input(self):
        """The retried generate call must include the triggering input.

        Regression test for a bug where the emergency handler retried
        with ``self._messages`` (history only), dropping the ``extra``
        from the original call. That made the model respond to the
        wrong prompt.
        """
        client = _mock_llm_client(
            [
                "priming",
                _bad_request(
                    "context_length_exceeded",
                    "This model's maximum context length is 32768 tokens.",
                ),
                "EMERGENCY SUMMARY",
                "recovery response",
            ]
        )
        chat = _build_chat(client, threshold=10_000)
        await chat.generate("initial task")

        # Resolve the underlying mock so we can inspect its call history.
        mock_stream = chat._client.chat.completions.stream

        result = await chat.generate("follow-up with important detail")
        assert result == "recovery response"

        # Four stream() calls should have been made:
        #   1. priming (succeeded)
        #   2. follow-up with important detail (raised 400)
        #   3. compaction summary (persist=False)
        #   4. retry of follow-up with important detail (after compact)
        assert mock_stream.call_count == 4
        retry_call = mock_stream.call_args_list[3]
        retry_messages = retry_call.kwargs["messages"]
        # The retry must contain the triggering user input verbatim.
        assert any(
            m.get("role") == "user"
            and m.get("content") == "follow-up with important detail"
            for m in retry_messages
        ), "retry dropped the triggering user input; got messages: " f"{retry_messages}"

    @pytest.mark.asyncio
    async def test_detects_vllm_integer_code_via_message(self):
        """vLLM sets error.code = 400 (int); detection must match via message.

        vLLM's OpenAI-compatible shim doesn't populate error.code as a
        string — it uses the integer HTTP status. The emergency
        handler must still fire by recognizing the "maximum context
        length" phrase in the error message.
        """
        vllm_error = _bad_request(
            code=400,  # integer, not string — mimics vLLM format
            message=(
                "This model's maximum context length is 32768 tokens. "
                "However, your request has 50000 input tokens."
            ),
        )
        client = _mock_llm_client(
            ["priming", vllm_error, "EMERGENCY SUMMARY", "recovery"]
        )
        chat = _build_chat(client, threshold=10_000)
        await chat.generate("task")
        result = await chat.generate("trigger")
        assert result == "recovery"
        # Threshold recomputed from parsed max: int(32768 * 0.75)
        assert chat._compaction_threshold == int(32_768 * 0.75)

    @pytest.mark.asyncio
    async def test_does_not_fire_on_persist_false(self):
        # When the compaction summary call itself (which is persist=False)
        # hits a BadRequestError, it must propagate instead of recursing.
        client = _mock_llm_client(
            [
                ("response", 200),  # initial call, triggers threshold
                _bad_request(
                    "context_length_exceeded",
                    "maximum context length is 128000 tokens",
                ),  # persist=False summary call — this one should propagate
            ]
        )
        chat = _build_chat(client, threshold=100)
        await chat.generate("task")
        with pytest.raises(openai.BadRequestError):
            # maybe_compact → _compact → generate(persist=False) → BadRequestError
            async for _ in chat.maybe_compact():
                pass

    @pytest.mark.asyncio
    async def test_propagates_other_bad_request_errors(self):
        # A non-context-length BadRequestError should still propagate
        # even when persist=True.
        client = _mock_llm_client([_bad_request("invalid_request", "Bad input")])
        chat = _build_chat(client, threshold=100)
        with pytest.raises(openai.BadRequestError):
            await chat.generate("task")

    @pytest.mark.asyncio
    async def test_caps_emergency_retries(self):
        """After _MAX_EMERGENCY_COMPACTIONS attempts with persistent
        context_length_exceeded, generate re-raises instead of looping.

        Regression: without the cap, a request whose ``new_input``
        alone exceeds the model's context would trigger compaction
        forever.

        The mock provides extra unused slots so a broken cap would
        visibly overrun the expected call count rather than hitting
        StopAsyncIteration and confusing the failure mode.
        """

        def ctx_err() -> openai.BadRequestError:
            return _bad_request(
                "context_length_exceeded",
                "This model's maximum context length is 32768 tokens.",
            )

        # Expected sequence:
        #   1. priming        — generate("task") succeeds
        #   2. ctx_err        — follow-up attempt 1, raises
        #   3. SUMMARY 1      — 1st emergency compaction (persist=False)
        #   4. ctx_err        — follow-up attempt 2, raises
        #   5. SUMMARY 2      — 2nd emergency compaction
        #   6. ctx_err        — follow-up attempt 3, cap hits, re-raise
        # Slots 7-10 are extras: if the cap were broken, the loop
        # would consume them and call_count would exceed 6.
        client = _mock_llm_client(
            [
                "priming",
                ctx_err(),
                "SUMMARY 1",
                ctx_err(),
                "SUMMARY 2",
                ctx_err(),
                # unused slots — cap must prevent these from firing
                "SUMMARY 3",
                ctx_err(),
                "SUMMARY 4",
                ctx_err(),
            ]
        )
        chat = _build_chat(client, threshold=10_000)
        await chat.generate("task")

        with pytest.raises(openai.BadRequestError):
            await chat.generate("trigger overflow")

        # Exactly 6 API calls: 1 priming + 3 failing attempts + 2
        # successful compaction summaries. Anything > 6 would mean the
        # cap did not engage and we attempted a 3rd compaction.
        assert chat._client.chat.completions.stream.call_count == 6


# ---------------------------------------------------------------------------
# Streaming I/O: agent_state transition + usage accounting
# ---------------------------------------------------------------------------


class TestStreaming:
    @pytest.mark.asyncio
    async def test_stream_requests_usage(self):
        """``include_usage`` must be set or streamed completions carry no
        usage block, which would silently zero out token accounting and
        keep ``maybe_compact`` from ever firing."""
        client = _mock_llm_client(["response"])
        chat = _build_chat(client, threshold=None)
        await chat.generate("task")
        _, kwargs = client.chat.completions.stream.call_args
        assert kwargs["stream_options"] == {"include_usage": True}

    @pytest.mark.asyncio
    async def test_usage_flows_into_total_tokens(self):
        """The streamed completion's usage drives ``total_tokens`` so the
        compaction threshold can be evaluated against real token counts."""
        client = _mock_llm_client([("response", 4242)])
        chat = _build_chat(client, threshold=None)
        await chat.generate("task")
        assert chat.total_tokens == 4242

    @pytest.mark.asyncio
    async def test_generating_emitted_once_first_token_arrives(self):
        """A delta event triggers exactly one ``("state", "generating")``
        before the final ``("result", text)``."""
        from ._stream_mock import content_delta, StreamScript, install_stream_mock

        client = MagicMock()
        script = StreamScript(
            events=[content_delta(), content_delta()],  # two token deltas
            completion=_make_completion("hello"),
        )
        install_stream_mock(client, [script])
        chat = _build_chat(client, threshold=None)

        events = [
            (kind, payload) async for kind, payload in chat.generate_streaming("task")
        ]
        # generating emitted once (not per delta), then a single result.
        assert events == [("state", "generating"), ("result", "hello")]

    @pytest.mark.asyncio
    async def test_no_generating_state_when_stream_has_no_tokens(self):
        """With no token events the call still produces a result and never
        claims the model started replying."""
        client = _mock_llm_client(["response"])
        chat = _build_chat(client, threshold=None)
        events = [
            (kind, payload) async for kind, payload in chat.generate_streaming("task")
        ]
        assert [k for k, _ in events] == ["result"]
        assert events[0][1] == "response"


# ---------------------------------------------------------------------------
# Protocol: MessageType literal includes compaction events
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_message_type_includes_compaction_events(self):
        # MessageType is a Literal — check that our new entries are present
        # by inspecting its __args__.
        args = set(MessageType.__args__)  # type: ignore[attr-defined]
        assert "compaction_start" in args
        assert "compaction_end" in args


# ---------------------------------------------------------------------------
# Transcript + trace + snapshot on-disk logging
# ---------------------------------------------------------------------------


class TestTranscriptAndTrace:
    @pytest.mark.asyncio
    async def test_no_writes_when_transcripts_dir_none(self, tmp_path):
        """Default case: no on-disk artifacts when the dir is not set."""
        client = _mock_llm_client(["resp"])
        chat = _build_chat(client, threshold=None)
        await chat.generate("hi")
        # tmp_path is untouched because we didn't pass it
        assert list(tmp_path.iterdir()) == []
        assert chat._transcript_md_path is None  # type: ignore[attr-defined]
        assert chat._trace_jsonl_path is None  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_transcript_starts_with_user_turn_not_system(self, tmp_path):
        """transcript.md omits the system message and starts with the first user turn."""
        client = _mock_llm_client(["reply"])
        chat = _build_chat(
            client,
            threshold=None,
            system="You are AGENT X.",
            transcripts_dir=tmp_path,
        )
        transcript = tmp_path / "transcript.md"
        assert not transcript.exists()
        assert not (tmp_path / "trace.jsonl").exists()

        await chat.generate("hi")
        assert transcript.exists()
        content = transcript.read_text(encoding="utf-8")
        assert "### System" not in content
        assert "You are AGENT X." not in content
        assert content.startswith("### User")
        assert "hi" in content
        assert "### Assistant" in content
        assert "reply" in content

    @pytest.mark.asyncio
    async def test_init_clobbers_stale_files(self, tmp_path):
        """Stale transcript.md and trace.jsonl from a prior run are wiped."""
        (tmp_path / "transcript.md").write_text("STALE CONTENT FROM PRIOR RUN")
        (tmp_path / "trace.jsonl").write_text('{"event":"stale"}\n')
        client = _mock_llm_client(["reply"])
        chat = _build_chat(client, threshold=None, transcripts_dir=tmp_path)
        assert not (tmp_path / "transcript.md").exists()
        assert not (tmp_path / "trace.jsonl").exists()
        await chat.generate("hi")
        transcript_text = (tmp_path / "transcript.md").read_text(encoding="utf-8")
        assert "STALE CONTENT" not in transcript_text
        assert "### User" in transcript_text

    @pytest.mark.asyncio
    async def test_generate_appends_delta_and_trace(self, tmp_path):
        """Each persistent generate() appends new items to transcript and a trace event."""
        client = _mock_llm_client(["hello back"])
        chat = _build_chat(client, threshold=None, transcripts_dir=tmp_path)
        await chat.generate("hello")

        content = (tmp_path / "transcript.md").read_text(encoding="utf-8")
        assert "### System" not in content
        assert "### User" in content
        assert "hello" in content
        assert "### Assistant" in content
        assert "hello back" in content

        events = _read_trace(tmp_path / "trace.jsonl")
        assert len(events) == 1
        assert events[0]["event"] == "llm_call"
        assert events[0]["round"] == 1
        assert events[0]["response"] == "hello back"
        assert "prompt_messages" in events[0]
        assert "tokens" in events[0]
        assert "ts" in events[0]

    @pytest.mark.asyncio
    async def test_persist_false_skips_transcript_but_logs_trace(self, tmp_path):
        """persist=False calls leave history/transcript untouched but DO write to trace.

        Trace logging is observability and intentionally decoupled from
        ``persist`` so auxiliary calls (compaction, final-answer) are
        still visible in trace.jsonl for post-mortem inspection.
        """
        client = _mock_llm_client(["side-effect-free"])
        chat = _build_chat(client, threshold=None, transcripts_dir=tmp_path)
        await chat.generate("aux prompt", persist=False, call_type="compaction")
        # transcript.md is lazily written on first persisted append; persist=False
        # leaves it absent.
        assert not (tmp_path / "transcript.md").exists()
        # trace.jsonl, in contrast, captures every API call regardless of persist.
        assert (tmp_path / "trace.jsonl").exists()
        events = _read_trace(tmp_path / "trace.jsonl")
        assert len(events) == 1
        assert events[0]["event"] == "llm_call"
        assert events[0]["type"] == "compaction"
        assert events[0]["response"] == "side-effect-free"

    @pytest.mark.asyncio
    async def test_compaction_snapshots_and_records_event(self, tmp_path):
        """Compaction takes a snapshot, appends handoff, emits compaction trace."""
        client = _mock_llm_client(
            [
                ("original response", 200),  # crosses threshold
                ("SUMMARY TEXT", 20),  # compaction summary (persist=False)
            ]
        )
        chat = _build_chat(
            client,
            threshold=100,
            transcripts_dir=tmp_path,
            guest_transcripts_dir=Path("/workspace/.agent/transcripts"),
        )
        await chat.generate("do the task")
        _ = [evt async for evt in chat.maybe_compact()]

        # Snapshot created with pre-compaction content
        snapshot = tmp_path / "transcript.compaction_1.md"
        assert snapshot.exists()
        snapshot_text = snapshot.read_text(encoding="utf-8")
        assert "do the task" in snapshot_text
        assert "original response" in snapshot_text

        # Live transcript has the handoff appended after the snapshot
        live = (tmp_path / "transcript.md").read_text(encoding="utf-8")
        assert HANDOFF_PREFIX in live
        assert "SUMMARY TEXT" in live
        # Handoff pointer uses the guest path, not the host path
        assert "/workspace/.agent/transcripts/transcript.md" in live
        assert str(tmp_path) not in live.split(HANDOFF_PREFIX, 1)[1]

        # Trace has: round llm_call, compaction llm_call (the meta summary
        # call), then the compaction marker event. Trace logging is
        # decoupled from persist, so the meta call is visible too.
        events = _read_trace(tmp_path / "trace.jsonl")
        assert [e["event"] for e in events] == [
            "llm_call",
            "llm_call",
            "compaction",
        ]
        assert events[0]["type"] == "round"
        assert events[1]["type"] == "compaction"
        assert events[1]["response"] == "SUMMARY TEXT"  # raw, pre-extract
        compaction_evt = events[2]
        assert compaction_evt["compaction_n"] == 1
        assert compaction_evt["tokens_before"] == 200
        assert compaction_evt["summary"] == "SUMMARY TEXT"
        assert compaction_evt["snapshot"] == str(snapshot)
        # New: handoff field captures the full injected user message so
        # consumers don't have to reconstruct it from prompt_messages.
        assert HANDOFF_PREFIX in compaction_evt["handoff"]
        assert "SUMMARY TEXT" in compaction_evt["handoff"]

    @pytest.mark.asyncio
    async def test_multiple_compactions_produce_numbered_snapshots(self, tmp_path):
        """Each compaction gets its own transcript.compaction_N.md file."""
        client = _mock_llm_client(
            [
                ("resp1", 200),  # triggers #1
                ("SUMMARY 1", 20),
                ("resp2", 300),  # triggers #2
                ("SUMMARY 2", 20),
            ]
        )
        chat = _build_chat(
            client,
            threshold=100,
            transcripts_dir=tmp_path,
            guest_transcripts_dir=tmp_path,
        )
        await chat.generate("task one")
        _ = [evt async for evt in chat.maybe_compact()]
        await chat.generate("task two")
        _ = [evt async for evt in chat.maybe_compact()]

        assert (tmp_path / "transcript.compaction_1.md").exists()
        assert (tmp_path / "transcript.compaction_2.md").exists()
        events = _read_trace(tmp_path / "trace.jsonl")
        compaction_events = [e for e in events if e["event"] == "compaction"]
        assert [e["compaction_n"] for e in compaction_events] == [1, 2]

    @pytest.mark.asyncio
    async def test_non_string_content_serialized_as_json(self, tmp_path):
        """Content that isn't a string (e.g. multimodal parts) is JSON-dumped."""
        client = _mock_llm_client(["response"])
        chat = _build_chat(client, threshold=None, transcripts_dir=tmp_path)
        # Feed a message with list content
        multimodal: list[dict[str, Any]] = [
            {"type": "text", "text": "caption"},
            {"type": "image_url", "image_url": {"url": "http://x"}},
        ]
        await chat.generate([{"role": "user", "content": multimodal}])  # type: ignore[arg-type]
        content = (tmp_path / "transcript.md").read_text(encoding="utf-8")
        # The list-content should be serialized as JSON on disk
        assert '"type": "text"' in content
        assert '"caption"' in content
