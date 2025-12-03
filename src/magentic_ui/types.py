from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

# Async callback for agent-initiated questions.
InputFunc = Callable[[str], Awaitable[str]]


# Prompt shown when no Quicksand browser slot is available.
LIVE_BROWSER_POOL_FULL_PROMPT = (
    "Too many tasks are using the web browser. Wait for another task "
    'to finish, then reply "continue" here.'
)


@dataclass
class InputRequest:
    """Agent is requesting user input. Yield from run_stream(), await the future."""

    prompt: str
    respond: Callable[[str], None]  # future.set_result


def _default_tool_args() -> dict[str, Any]:
    """Typed factory so pyright can infer the type without suppression."""
    return {}


@dataclass
class ApprovalRequest(InputRequest):
    """Agent is requesting user approval before executing a tool.

    Extends InputRequest with tool metadata so the frontend can render
    an approval card with command details and category information.

    ``respond`` should be called with ``"approve"`` / ``"deny"`` (from buttons),
    ``"yes"`` / ``"no"`` (from buttons or input box), or any other string (alternative
    instructions from the input box).
    """

    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=_default_tool_args)
    category: str = ""  # ApprovalCategory value
    reason: str = ""


@dataclass
class ContinuationRequest(InputRequest):
    """Agent hit its per-batch ``max_rounds`` cap and is asking the user
    whether to keep going or stop here.

    Yielded by ``FaraWebSurfer`` and ``OmniAgent`` from their action
    loops. The frontend renders a dedicated card with ``Continue`` /
    ``Stop`` buttons (input_type=``"continuation"``).

    ``respond`` is called with the binary sentinel produced by the
    connection layer (see ``WebSocketManager.handle_input_response`` and
    ``handle_continuation_response``):

    - ``"yes"`` — keep going for another batch.
    - ``"no"`` — terminate gracefully with a best-effort answer.

    The connection layer maps Continue button clicks (and typed
    ``"yes"`` / ``"continue"`` in the chat) to ``"yes"``, and everything
    else (Stop button, typed ``"no"`` / ``"stop"``, empty input, free
    text) to ``"no"``. Free-text "steer" replies are intentionally not
    plumbed through this channel — the agent only sees the binary
    decision.
    """


class PauseController:
    """Pause/cancel flags and mid-run user-message inbox shared between TeamManager and agents."""

    def __init__(self) -> None:
        self._is_paused: bool = False
        self._cancelled: bool = False
        self._inbox: list[str] = []
        self._drain_log: list[tuple[str, str]] = []

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def cancel(self) -> None:
        self._cancelled = True
        self._is_paused = False

    def queue_message(self, message: str) -> None:
        """Queue a user message for the running agent to pick up."""
        self._inbox.append(message)

    def drain_messages(self, reader: str) -> list[str]:
        """Take and clear all queued messages, FIFO. Tag drains with ``reader``."""
        messages = self._inbox
        self._inbox = []
        for m in messages:
            self._drain_log.append((reader, m))
        return messages

    def messages_drained_by_others(
        self, my_reader: str, since_index: int
    ) -> tuple[list[str], int]:
        """Return messages drained by other readers since ``since_index``.

        Returns ``(messages, new_cursor)`` — pass ``new_cursor`` back as
        ``since_index`` next time so each entry surfaces exactly once.
        """
        if since_index < 0:
            raise ValueError(f"since_index must be >= 0, got {since_index}")
        new_msgs = [msg for r, msg in self._drain_log[since_index:] if r != my_reader]
        return new_msgs, len(self._drain_log)

    @property
    def drain_log_cursor(self) -> int:
        """Current end-of-log index, for use as an initial ``since_index``."""
        return len(self._drain_log)

    @property
    def has_queued_messages(self) -> bool:
        return bool(self._inbox)
