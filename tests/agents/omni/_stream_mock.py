"""Test helpers for mocking OpenAI streaming chat completions.

The production code path in :class:`OmniResponses._call_api` uses
``client.chat.completions.stream(...)`` (the high-level streaming
helper) so we can detect "first token arrived" without surfacing
individual tokens. Tests that need to canned-respond to LLM calls
should mock the stream entry point — these helpers wrap a synchronous
``ChatCompletion`` (or an exception) in the async-context-manager
shape the production code expects.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from openai.lib.streaming.chat import ContentDeltaEvent


def content_delta(text: str = "x") -> ContentDeltaEvent:
    """Build a real SDK content-delta event.

    Using the concrete SDK class (not a stand-in) keeps the test tied to
    the same event vocabulary ``_call_api`` matches against, so a future
    SDK rename surfaces here instead of silently passing.
    """
    return ContentDeltaEvent(type="content.delta", delta=text, snapshot=text)


class StreamScript:
    """A canned stream: events to yield, then a final completion.

    Use this (instead of a bare completion) when a test needs the
    stream to emit token events so the ``"generating"`` transition fires.
    """

    def __init__(self, events: list[Any], completion: Any) -> None:
        self.events = events
        self.completion = completion


class MockStream:
    """Mimics openai's AsyncChatCompletionStream.

    Iterating replays ``events`` (empty by default — most tests don't
    care about token deltas, only compaction / control flow).
    ``get_final_completion`` returns the canned ChatCompletion.
    """

    def __init__(self, completion: Any, events: list[Any] | None = None) -> None:
        self._completion = completion
        self._events = list(events or [])

    def __aiter__(self) -> "MockStream":
        return self

    async def __anext__(self) -> Any:
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)

    async def get_final_completion(self) -> Any:
        return self._completion


class MockStreamManager:
    """Mimics openai's AsyncChatCompletionStreamManager.

    The production code uses ``async with client.chat.completions.stream(...) as stream:``
    so the return value of ``.stream(...)`` must be an async context
    manager. If the canned target is an exception, raise it from
    ``__aenter__`` so retry logic in :meth:`_call_api` exercises the
    same code path as real OpenAI errors.
    """

    def __init__(self, target: Any) -> None:
        self._target = target

    async def __aenter__(self) -> MockStream:
        if isinstance(self._target, Exception):
            raise self._target
        if isinstance(self._target, StreamScript):
            return MockStream(self._target.completion, self._target.events)
        return MockStream(self._target)

    async def __aexit__(self, *args: Any) -> None:
        return None


def stream_side_effect(items: list[Any]):
    """Build a ``side_effect`` callable for ``client.chat.completions.stream``.

    Each call to ``.stream(...)`` consumes one entry from ``items`` in
    order: a ChatCompletion (or anything else) is wrapped in a manager
    whose stream yields it via ``get_final_completion``; a
    :class:`StreamScript` additionally replays token events first; an
    exception is raised from the manager's ``__aenter__``.
    """
    iterator = iter(items)

    def _side_effect(*args: Any, **kwargs: Any) -> MockStreamManager:
        try:
            return MockStreamManager(next(iterator))
        except StopIteration:
            raise AssertionError(
                f"stream() called more than the {len(items)} canned "
                "response(s); add more items to the mock"
            ) from None

    return _side_effect


def install_stream_mock(client: Any, items: list[Any]) -> MagicMock:
    """Attach a streaming mock to ``client.chat.completions``.

    Returns the ``MagicMock`` installed as ``.stream`` so tests can
    assert on ``call_args_list`` / ``call_count`` the same way they
    previously did against ``.create``.
    """
    stream_mock = MagicMock(side_effect=stream_side_effect(items))
    client.chat.completions.stream = stream_mock
    return stream_mock
