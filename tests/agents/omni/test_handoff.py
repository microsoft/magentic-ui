"""Unit tests for the OmniAgent sub-agent handoff envelope builder."""

from __future__ import annotations


from magentic_ui.agents.message_schemas import HandoffReason, HandoffStatus
from magentic_ui.teams.omniagent._handoff import (
    build_handoff,
    build_handoff_from_info,
)


def test_completed_no_extras_is_bare_summary():
    summary = "I booked the table for 4 at 7pm."
    body, info = build_handoff(
        summary,
        status=HandoffStatus.COMPLETED,
        reason=HandoffReason.TERMINATE,
        last_url=None,
        facts=[],
    )
    assert body == summary  # no SUMMARY: label, no NOTE
    assert info == {
        "status": "completed",
        "reason": "terminate",
        "last_url": None,
        "facts": [],
    }


def test_url_on_top_and_summary_labeled_when_extras():
    body, _ = build_handoff(
        "Found it.",
        status=HandoffStatus.COMPLETED,
        reason=HandoffReason.TERMINATE,
        last_url="https://x.test/p",
        facts=[],
    )
    assert body == "LAST URL: https://x.test/p\n\nSUMMARY:\nFound it."


def test_full_order_note_url_summary_facts():
    body, _ = build_handoff(
        "partial answer",
        status=HandoffStatus.INCOMPLETE,
        reason=HandoffReason.MAX_ROUNDS,
        last_url="https://x.test/p",
        facts=["f1", "f2"],
    )
    lines = body.split("\n\n")
    assert lines[0].startswith("NOTE:")
    assert "max rounds" in lines[0].lower()
    assert lines[1] == "LAST URL: https://x.test/p"
    assert lines[2] == "SUMMARY:\npartial answer"
    assert lines[3] == "FACTS:\n- f1\n- f2"


def test_facts_only_labels_summary():
    body, _ = build_handoff(
        "answer",
        status=HandoffStatus.COMPLETED,
        reason=HandoffReason.TERMINATE,
        last_url=None,
        facts=["a"],
    )
    assert body == "SUMMARY:\nanswer\n\nFACTS:\n- a"


def test_facts_stripped_and_deduped():
    body, info = build_handoff(
        "S",
        status=HandoffStatus.COMPLETED,
        reason=HandoffReason.TERMINATE,
        last_url=None,
        facts=["  a  ", "", "   ", "a", "b"],
    )
    assert body == "SUMMARY:\nS\n\nFACTS:\n- a\n- b"
    assert info["facts"] == ["a", "b"]


def test_non_completed_no_extras_note_then_bare_summary():
    body, _ = build_handoff(
        "stopped text",
        status=HandoffStatus.ERROR,
        reason=HandoffReason.CONSECUTIVE_ERRORS,
        last_url=None,
        facts=[],
    )
    first = body.splitlines()[0]
    assert first.startswith("NOTE:")
    assert "repeated errors" in first.lower()
    assert body == f"{first}\n\nstopped text"  # bare, no SUMMARY label


def test_completed_never_has_note():
    body, _ = build_handoff(
        "ok",
        status=HandoffStatus.COMPLETED,
        reason=HandoffReason.TERMINATE,
        last_url=None,
        facts=[],
    )
    assert "NOTE:" not in body


def test_empty_sections_omitted():
    body, _ = build_handoff(
        "only",
        status=HandoffStatus.COMPLETED,
        reason=HandoffReason.TERMINATE,
        last_url=None,
        facts=[],
    )
    assert "FACTS:" not in body
    assert "LAST URL:" not in body
    assert "SUMMARY:" not in body


def test_build_handoff_from_info_maps_str_values():
    info = {
        "status": "incomplete",
        "reason": "orphan_recovery",
        "last_url": "https://u",
        "facts": ["k"],
    }
    body = build_handoff_from_info("recap text", info)
    assert body.splitlines()[0].startswith("NOTE:")
    assert "interrupted" in body.splitlines()[0].lower()
    assert "LAST URL: https://u" in body
    assert "SUMMARY:\nrecap text" in body
    assert "FACTS:\n- k" in body


def test_build_handoff_from_info_orphan_minimal():
    body = build_handoff_from_info(
        "best-effort recap",
        {
            "status": "incomplete",
            "reason": "orphan_recovery",
            "last_url": None,
            "facts": [],
        },
    )
    first = body.splitlines()[0]
    assert first.startswith("NOTE:")
    assert body == f"{first}\n\nbest-effort recap"


def test_enum_string_values():
    assert HandoffStatus.COMPLETED.value == "completed"
    assert HandoffStatus.INCOMPLETE.value == "incomplete"
    assert HandoffStatus.ERROR.value == "error"
    assert HandoffReason.TERMINATE.value == "terminate"
    assert HandoffReason.MAX_ROUNDS.value == "max_rounds"
    assert HandoffReason.ORPHAN_RECOVERY.value == "orphan_recovery"
    assert HandoffReason.CONSECUTIVE_ERRORS.value == "consecutive_errors"
