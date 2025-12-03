"""State persistence I/O tests for OmniAgent resume."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from magentic_ui.teams.omniagent._state_io import (
    DEFAULT_MAX_STATE_BYTES,
    read_state,
    write_state,
)


def test_round_trip(tmp_path: Path) -> None:
    """Payload written and re-read is structurally identical."""
    payload = {
        "messages": [
            {"role": "system", "content": "you are a helpful agent"},
            {"role": "user", "content": "open file foo.txt"},
            {"role": "assistant", "content": "<tool_call>open</tool_call>"},
        ],
        "total_tokens": 1234,
        "prev_handoff": None,
        "compaction_count": 0,
        "viewport": {
            "current_file": "/workspace/foo.txt",
            "current_line": 10,
            "scroll_count": 2,
        },
    }
    state_path = tmp_path / "omni_state.json"
    write_state(state_path, payload)
    assert read_state(state_path) == payload


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    """A nonexistent state path yields an empty dict, no exception."""
    assert read_state(tmp_path / "does_not_exist.json") == {}


def test_empty_file_returns_empty(tmp_path: Path) -> None:
    """A zero-byte state file yields an empty dict."""
    state_path = tmp_path / "omni_state.json"
    state_path.write_text("")
    assert read_state(state_path) == {}


def test_corrupted_file_returns_empty_and_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid JSON yields an empty dict and logs a warning, never raises."""
    state_path = tmp_path / "omni_state.json"
    state_path.write_text("this is not json {{{")
    with caplog.at_level(
        logging.WARNING, logger="magentic_ui.teams.omniagent._state_io"
    ):
        result = read_state(state_path)
    assert result == {}
    assert any("Corrupted omni state" in r.message for r in caplog.records)


def test_non_object_json_returns_empty(tmp_path: Path) -> None:
    """A JSON array (or other non-object) at the top level is rejected."""
    state_path = tmp_path / "omni_state.json"
    state_path.write_text(json.dumps([1, 2, 3]))
    assert read_state(state_path) == {}


def test_size_cap_blocks_write(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Payloads above ``max_bytes`` are skipped with a warning, no file written."""
    state_path = tmp_path / "omni_state.json"
    payload = {"messages": [{"role": "user", "content": "x" * 1024}]}
    with caplog.at_level(
        logging.WARNING, logger="magentic_ui.teams.omniagent._state_io"
    ):
        write_state(state_path, payload, max_bytes=64)
    assert not state_path.exists()
    assert any("skipping persist" in r.message for r in caplog.records)


def test_atomic_write_preserves_prior_file_on_size_cap(tmp_path: Path) -> None:
    """A blocked second write does not damage an existing valid file."""
    state_path = tmp_path / "omni_state.json"
    write_state(state_path, {"messages": [{"role": "user", "content": "ok"}]})
    prior = state_path.read_text()
    write_state(
        state_path,
        {"messages": [{"role": "user", "content": "x" * 1024}]},
        max_bytes=64,
    )
    assert state_path.read_text() == prior


def test_default_max_state_bytes_is_reasonable() -> None:
    """Guard against accidental shrinking of the cap below typical state size."""
    assert DEFAULT_MAX_STATE_BYTES >= 1_000_000


def test_unserializable_payload_is_dropped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Non-JSON-serializable values produce a warning, no file written."""
    state_path = tmp_path / "omni_state.json"
    payload = {"bad": object()}
    with caplog.at_level(
        logging.WARNING, logger="magentic_ui.teams.omniagent._state_io"
    ):
        write_state(state_path, payload)
    assert not state_path.exists()
    assert any("Cannot serialize omni state" in r.message for r in caplog.records)


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    """``write_state`` creates intermediate directories if missing."""
    state_path = tmp_path / "nested" / "dirs" / "omni_state.json"
    write_state(state_path, {"messages": []})
    assert state_path.exists()
    assert json.loads(state_path.read_text()) == {"messages": []}


def test_no_stray_tmp_files_left_on_success(tmp_path: Path) -> None:
    """A clean write leaves only the target file in the directory."""
    state_path = tmp_path / "omni_state.json"
    write_state(state_path, {"messages": [{"role": "user", "content": "hello"}]})
    entries = list(tmp_path.iterdir())
    assert entries == [state_path]
