"""Tests for OmniAgent response parsing.

Covers single-call, multi-call, ast fallback, parse errors, and the
answer-vs-tool-call precedence rule.
"""

from magentic_ui.teams.omniagent._parse import (
    ParsedResponse,
    ParsedToolCall,
    ParseError,
    extract_answer,
    parse_response,
)


def _calls(parsed: ParsedResponse) -> list[dict]:
    return [b.call for b in parsed.tool_call_blocks if isinstance(b, ParsedToolCall)]


def _errors(parsed: ParsedResponse) -> list[str]:
    return [b.message for b in parsed.tool_call_blocks if isinstance(b, ParseError)]


# ---------------------------------------------------------------------------
# Single-call (regression: previous behavior preserved)
# ---------------------------------------------------------------------------


class TestSingleCall:
    def test_single_tool_call(self) -> None:
        resp = (
            "I need to list files.\n"
            '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>'
        )
        parsed = parse_response(resp)
        assert parsed.thoughts == "I need to list files."
        assert _calls(parsed) == [{"name": "bash", "arguments": {"command": "ls"}}]
        assert parsed.answer is None
        assert _errors(parsed) == []

    def test_no_tool_call_no_answer(self) -> None:
        parsed = parse_response("just some thoughts")
        assert parsed.thoughts == "just some thoughts"
        assert parsed.tool_call_blocks == []
        assert parsed.answer is None


# ---------------------------------------------------------------------------
# Multi-call
# ---------------------------------------------------------------------------


class TestMultiCall:
    def test_two_tool_calls_in_order(self) -> None:
        resp = (
            "Plan: list then count.\n"
            '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>\n'
            '<tool_call>{"name": "bash", "arguments": {"command": "wc -l"}}</tool_call>'
        )
        parsed = parse_response(resp)
        assert parsed.thoughts == "Plan: list then count."
        calls = _calls(parsed)
        assert len(calls) == 2
        assert calls[0]["arguments"]["command"] == "ls"
        assert calls[1]["arguments"]["command"] == "wc -l"
        assert _errors(parsed) == []

    def test_three_calls_middle_malformed_preserves_order(self) -> None:
        """One malformed block does not abort the rest. Original block
        order is preserved in tool_call_blocks (valid, error, valid)."""
        resp = (
            '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>\n'
            "<tool_call>{not valid json</tool_call>\n"
            '<tool_call>{"name": "bash", "arguments": {"command": "pwd"}}</tool_call>'
        )
        parsed = parse_response(resp)
        # Order preserved: ParsedToolCall, ParseError, ParsedToolCall
        assert len(parsed.tool_call_blocks) == 3
        assert isinstance(parsed.tool_call_blocks[0], ParsedToolCall)
        assert isinstance(parsed.tool_call_blocks[1], ParseError)
        assert isinstance(parsed.tool_call_blocks[2], ParsedToolCall)
        assert parsed.tool_call_blocks[0].call["arguments"]["command"] == "ls"
        assert "block 1" in parsed.tool_call_blocks[1].message
        assert parsed.tool_call_blocks[2].call["arguments"]["command"] == "pwd"

    def test_unclosed_tool_call_is_error(self) -> None:
        resp = '<tool_call>{"name": "bash"'  # no closing tag
        parsed = parse_response(resp)
        assert _calls(parsed) == []
        errors = _errors(parsed)
        assert len(errors) == 1
        assert "missing closing" in errors[0]


# ---------------------------------------------------------------------------
# ast fallback (single-quoted dicts)
# ---------------------------------------------------------------------------


class TestAstFallback:
    def test_single_quoted_dict_recovered(self) -> None:
        resp = "<tool_call>{'name': 'bash', 'arguments': {'command': 'ls'}}</tool_call>"
        parsed = parse_response(resp)
        assert _calls(parsed) == [{"name": "bash", "arguments": {"command": "ls"}}]
        assert _errors(parsed) == []

    def test_unrecoverable_garbage(self) -> None:
        resp = "<tool_call>not even a dict-like thing</tool_call>"
        parsed = parse_response(resp)
        assert _calls(parsed) == []
        assert len(_errors(parsed)) == 1


# ---------------------------------------------------------------------------
# Answer precedence
# ---------------------------------------------------------------------------


class TestAnswer:
    def test_answer_only(self) -> None:
        parsed = parse_response("done.<answer>final result</answer>")
        assert parsed.thoughts == "done."
        assert parsed.tool_call_blocks == []
        assert parsed.answer == "final result"

    def test_answer_wins_over_tool_call(self) -> None:
        """When both <answer> and <tool_call> are present, answer terminates the turn."""
        resp = (
            '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>'
            "<answer>i am done</answer>"
        )
        parsed = parse_response(resp)
        assert parsed.tool_call_blocks == []
        assert parsed.answer == "i am done"

    def test_answer_without_closing_tag(self) -> None:
        parsed = parse_response("ok<answer>tail content")
        assert parsed.answer == "tail content"


# ---------------------------------------------------------------------------
# extract_answer (existing helper, kept for direct callers)
# ---------------------------------------------------------------------------


class TestExtractAnswer:
    def test_simple(self) -> None:
        assert extract_answer("<answer>hi</answer>") == "hi"

    def test_no_answer(self) -> None:
        assert extract_answer("nope") is None

    def test_no_close(self) -> None:
        assert extract_answer("<answer>tail") == "tail"


# ---------------------------------------------------------------------------
# ParsedResponse shape (regression guard)
# ---------------------------------------------------------------------------


def test_parsed_response_fields() -> None:
    """Lock the shape: any future field changes show up here first."""
    pr = ParsedResponse(thoughts="t", tool_call_blocks=[], answer=None)
    assert pr._fields == ("thoughts", "tool_call_blocks", "answer")
