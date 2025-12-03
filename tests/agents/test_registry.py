"""Tests for AgentRegistry and AgentEntry."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from magentic_ui.agents.base import Capability
from magentic_ui.agents.registry import AgentEntry, AgentRegistry
from magentic_ui.agents.web_surfer.fara._types import StreamUpdate
from magentic_ui.types import InputRequest


# -- Helpers ----------------------------------------------------------------


class FakeAgent:
    """Minimal SubAgentProtocol implementation for testing."""

    def __init__(self) -> None:
        self.closed = False

    async def run_stream(
        self, task: str, **kwargs: Any
    ) -> AsyncIterator[StreamUpdate | InputRequest]:
        yield StreamUpdate(text=f"done: {task}")

    async def summarize_progress(self) -> tuple[str, dict[str, Any]]:
        return "fake summary", {
            "status": "incomplete",
            "reason": "orphan_recovery",
            "last_url": None,
            "facts": [],
        }

    async def close(self) -> None:
        self.closed = True


def _make_entry(
    name: str = "fake_tool",
    caps: frozenset[Capability] = frozenset(),
    agent: FakeAgent | None = None,
) -> AgentEntry:
    tool_def = {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Tool {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    return AgentEntry(
        agent=agent or FakeAgent(),
        tool_definition=tool_def,
        capabilities=caps,
    )


# -- AgentEntry tests -------------------------------------------------------


class TestAgentEntry:
    def test_name_derived_from_definition(self) -> None:
        entry = _make_entry("my_agent")
        assert entry.name == "my_agent"

    def test_frozen(self) -> None:
        entry = _make_entry()
        with pytest.raises(AttributeError):
            entry.agent = FakeAgent()  # type: ignore[misc]


# -- AgentRegistry tests ----------------------------------------------------


class TestAgentRegistry:
    def test_register_and_get(self) -> None:
        reg = AgentRegistry()
        entry = _make_entry("delegate_cua")
        reg.register(entry)
        assert reg.get("delegate_cua") is entry

    def test_get_missing_returns_none(self) -> None:
        reg = AgentRegistry()
        assert reg.get("nonexistent") is None

    def test_has(self) -> None:
        reg = AgentRegistry()
        reg.register(_make_entry("delegate_cua"))
        assert reg.has("delegate_cua")
        assert not reg.has("other")

    def test_duplicate_raises(self) -> None:
        reg = AgentRegistry()
        reg.register(_make_entry("delegate_cua"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_entry("delegate_cua"))

    def test_capabilities_union(self) -> None:
        reg = AgentRegistry()
        reg.register(_make_entry("a", frozenset({Capability.WEB_BROWSING})))
        reg.register(_make_entry("b", frozenset()))
        assert reg.capabilities() == frozenset({Capability.WEB_BROWSING})

    def test_has_capability(self) -> None:
        reg = AgentRegistry()
        reg.register(_make_entry("a", frozenset({Capability.WEB_BROWSING})))
        assert reg.has_capability(Capability.WEB_BROWSING)

    def test_tool_definitions(self) -> None:
        reg = AgentRegistry()
        entry = _make_entry("my_tool")
        reg.register(entry)
        defs = reg.tool_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "my_tool"

    def test_iter_and_len(self) -> None:
        reg = AgentRegistry()
        reg.register(_make_entry("a"))
        reg.register(_make_entry("b"))
        assert len(reg) == 2
        names = [e.name for e in reg]
        assert set(names) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_close_all(self) -> None:
        agent1 = FakeAgent()
        agent2 = FakeAgent()
        reg = AgentRegistry()
        reg.register(_make_entry("a", agent=agent1))
        reg.register(_make_entry("b", agent=agent2))
        await reg.close_all()
        assert agent1.closed
        assert agent2.closed

    @pytest.mark.asyncio
    async def test_close_all_dedupes(self) -> None:
        """Same agent registered under two names is closed only once."""
        agent = FakeAgent()
        reg = AgentRegistry()
        reg.register(_make_entry("a", agent=agent))
        reg.register(_make_entry("b", agent=agent))
        await reg.close_all()
        assert agent.closed

    def test_empty_registry(self) -> None:
        reg = AgentRegistry()
        assert len(reg) == 0
        assert reg.capabilities() == frozenset()
        assert reg.tool_definitions() == []

    def test_register_rejects_missing_function(self) -> None:
        reg = AgentRegistry()
        bad = AgentEntry(agent=FakeAgent(), tool_definition={"type": "function"})
        with pytest.raises(ValueError, match="function"):
            reg.register(bad)

    def test_register_rejects_empty_name(self) -> None:
        reg = AgentRegistry()
        bad = AgentEntry(
            agent=FakeAgent(),
            tool_definition={"type": "function", "function": {"name": ""}},
        )
        with pytest.raises(ValueError, match="non-empty"):
            reg.register(bad)
