"""Unit tests for shared types in magentic_ui.types."""

from __future__ import annotations

import pytest

from magentic_ui.types import PauseController


class TestPauseControllerFlags:
    def test_initial_state_is_unpaused_and_not_cancelled(self) -> None:
        pc = PauseController()
        assert pc.is_paused is False
        assert pc.is_cancelled is False

    def test_pause_then_resume(self) -> None:
        pc = PauseController()
        pc.pause()
        assert pc.is_paused is True
        pc.resume()
        assert pc.is_paused is False

    def test_cancel_clears_pause_and_sets_cancelled(self) -> None:
        pc = PauseController()
        pc.pause()
        pc.cancel()
        assert pc.is_paused is False
        assert pc.is_cancelled is True


class TestPauseControllerInbox:
    def test_inbox_starts_empty(self) -> None:
        pc = PauseController()
        assert pc.has_queued_messages is False
        assert pc.drain_messages(reader="test") == []

    def test_queue_then_drain_returns_fifo(self) -> None:
        pc = PauseController()
        pc.queue_message("first")
        pc.queue_message("second")
        pc.queue_message("third")
        assert pc.has_queued_messages is True
        assert pc.drain_messages(reader="test") == ["first", "second", "third"]

    def test_drain_clears_inbox(self) -> None:
        pc = PauseController()
        pc.queue_message("hi")
        pc.drain_messages(reader="test")
        assert pc.has_queued_messages is False
        assert pc.drain_messages(reader="test") == []

    def test_inbox_independent_of_pause_flag(self) -> None:
        # Queueing a message should not pause the controller, and pausing
        # should not affect queued messages.
        pc = PauseController()
        pc.queue_message("hello")
        assert pc.is_paused is False
        pc.pause()
        assert pc.has_queued_messages is True
        pc.resume()
        assert pc.drain_messages(reader="test") == ["hello"]


class TestPauseControllerDrainLog:
    """Reader-tagged drain log enables cross-agent steering detection.

    When OmniAgent and a sub-agent (Fara) share a controller, OmniAgent
    needs to know about messages that the sub-agent already drained,
    otherwise it will mistake the sub-agent's off-spec output for a
    failure and try to redo the original task.
    """

    def test_messages_drained_by_others_skips_my_reader(self) -> None:
        pc = PauseController()
        pc.queue_message("hi")
        pc.drain_messages(reader="OmniAgent")
        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=0
        )
        assert msgs == []
        assert cursor == 1  # cursor still advances past the entry

    def test_messages_drained_by_fara_visible_to_omniagent(self) -> None:
        pc = PauseController()
        pc.queue_message("steer to fara")
        pc.drain_messages(reader="web_surfer")
        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=0
        )
        assert msgs == ["steer to fara"]
        assert cursor == 1

    def test_cursor_prevents_double_surfacing(self) -> None:
        pc = PauseController()
        pc.queue_message("first")
        pc.drain_messages(reader="web_surfer")
        msgs1, cursor1 = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=0
        )
        assert msgs1 == ["first"]

        # Second poll with the returned cursor — no new messages.
        msgs2, cursor2 = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=cursor1
        )
        assert msgs2 == []
        assert cursor2 == cursor1

        # New message drained by the sub-agent — second poll picks it up.
        pc.queue_message("second")
        pc.drain_messages(reader="web_surfer")
        msgs3, cursor3 = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=cursor2
        )
        assert msgs3 == ["second"]
        assert cursor3 == 2

    def test_interleaved_readers_are_filtered_correctly(self) -> None:
        pc = PauseController()
        # OmniAgent drains its own steering.
        pc.queue_message("to omni 1")
        pc.drain_messages(reader="OmniAgent")
        # Then the sub-agent takes over and drains a steering.
        pc.queue_message("to sub 1")
        pc.drain_messages(reader="web_surfer")
        # Then control returns to OmniAgent and another steering arrives.
        pc.queue_message("to omni 2")
        pc.drain_messages(reader="OmniAgent")

        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=0
        )
        # OmniAgent only needs to learn about the sub-agent's steering;
        # its own drains are already in its conversation history.
        assert msgs == ["to sub 1"]
        assert cursor == 3

    def test_multiple_messages_drained_in_one_call_all_logged(self) -> None:
        pc = PauseController()
        pc.queue_message("a")
        pc.queue_message("b")
        pc.queue_message("c")
        pc.drain_messages(reader="web_surfer")
        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=0
        )
        assert msgs == ["a", "b", "c"]
        assert cursor == 3

    def test_empty_drain_does_not_log(self) -> None:
        pc = PauseController()
        pc.drain_messages(reader="web_surfer")  # empty inbox
        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=0
        )
        assert msgs == []
        assert cursor == 0

    def test_drain_log_cursor_skips_prior_entries(self) -> None:
        """Initializing a reader's cursor at ``drain_log_cursor`` lets a
        new task on a reused controller skip drains from prior tasks."""
        pc = PauseController()

        # Simulate a prior task: sub-agent drained one steering.
        pc.queue_message("steer in prior task")
        pc.drain_messages(reader="web_surfer")

        # New task starts: snapshot the cursor and use it as since_index.
        new_task_cursor = pc.drain_log_cursor
        assert new_task_cursor == 1

        # Initial poll right at task start sees nothing — prior drains
        # are correctly skipped.
        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=new_task_cursor
        )
        assert msgs == []
        assert cursor == 1

        # A fresh sub-agent steering during the new task surfaces.
        pc.queue_message("steer in new task")
        pc.drain_messages(reader="web_surfer")
        msgs, cursor = pc.messages_drained_by_others(
            my_reader="OmniAgent", since_index=new_task_cursor
        )
        assert msgs == ["steer in new task"]
        assert cursor == 2

    def test_negative_since_index_raises(self) -> None:
        """Negative ``since_index`` would silently slice from the end of
        the log and drop earlier entries, breaking the
        "surface exactly once" guarantee. Reject it explicitly."""
        pc = PauseController()
        pc.queue_message("m")
        pc.drain_messages(reader="web_surfer")
        with pytest.raises(ValueError):
            pc.messages_drained_by_others(my_reader="OmniAgent", since_index=-1)
