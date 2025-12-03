"""Base protocol and capability definitions for delegatable sub-agents.

Any agent that can receive delegated tasks from OmniAgent must satisfy
:class:`SubAgentProtocol`.  Capabilities are declared via the
:class:`Capability` enum so they're type-checked and discoverable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .message_schemas import HandoffInfo
from .web_surfer.fara._types import StreamUpdate
from ..types import InputRequest


class Capability(StrEnum):
    """Capabilities that sub-agents can advertise.

    Used for prompt gating — the system prompt includes agent-specific
    guidelines only when the matching capability is registered.

    Add new entries here when introducing a new agent type.
    """

    WEB_BROWSING = "web_browsing"


@runtime_checkable
class SubAgentProtocol(Protocol):
    """Protocol for any agent that can receive delegated tasks.

    Implementations must be async-iterable streamers that yield
    ``StreamUpdate`` for progress and ``InputRequest`` when user input
    is needed.
    """

    def run_stream(
        self,
        task: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamUpdate | InputRequest]:
        """Stream task execution updates.

        ``task`` is the primary instruction; extra arguments from the
        agent's tool schema (e.g. ``context``) flow through as
        ``**kwargs``. OmniAgent forwards parsed tool arguments verbatim.
        """
        ...

    async def summarize_progress(self) -> tuple[str, HandoffInfo]:
        """Return a recap of progress so far plus structured handoff info."""
        ...

    async def close(self) -> None:
        """Clean up resources (browser sessions, containers, etc.)."""
        ...
