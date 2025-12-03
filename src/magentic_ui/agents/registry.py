"""Agent registry for delegatable sub-agents.

Provides a single source of truth for delegation tools: each entry bundles the
runtime agent instance, the tool schema shown to the LLM, and capability tags
used for prompt gating.

Usage::

    from magentic_ui.agents.base import Capability
    from magentic_ui.agents.registry import AgentRegistry, AgentEntry

    registry = AgentRegistry()
    registry.register(AgentEntry(
        agent=web_surfer,
        tool_definition=DELEGATE_CUA_DEF,
        capabilities=frozenset({Capability.WEB_BROWSING}),
    ))

    # OmniAgent uses this for dispatch + prompt construction
    omni = OmniAgent(..., agent_registry=registry)
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

from .base import Capability, SubAgentProtocol

_log = logging.getLogger(__name__)


def _validate_tool_definition(tool_def: dict[str, Any]) -> None:
    """Check the tool schema is well-formed enough for dispatch."""
    raw_fn = tool_def.get("function")
    if not isinstance(raw_fn, dict):
        raise ValueError("tool_definition must have a 'function' dict")
    fn = cast(dict[str, Any], raw_fn)
    name = fn.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("tool_definition.function.name must be a non-empty string")


@dataclass(frozen=True)
class AgentEntry:
    """A registered delegatable agent with its tool schema.

    Attributes:
        agent: Runtime agent instance satisfying :class:`SubAgentProtocol`.
        tool_definition: OpenAI-style tool schema dict shown in the system
            prompt so the LLM knows how to call this agent.  The tool name
            is derived from ``tool_definition["function"]["name"]``.
        capabilities: Tags for prompt gating (e.g.
            ``{Capability.WEB_BROWSING}``).  The system prompt uses these
            to decide which guidelines to include.
    """

    agent: SubAgentProtocol
    tool_definition: dict[str, Any]
    capabilities: frozenset[Capability] = frozenset()

    @property
    def name(self) -> str:
        """Tool name derived from the tool schema."""
        return self.tool_definition["function"]["name"]


class AgentRegistry:
    """Registry of delegatable sub-agents.

    OmniAgent consults this registry to:
    1. Build its tool list (core tools + agent-backed delegation tools).
    2. Dispatch tool calls to the correct agent at runtime.
    3. Gate system-prompt guidelines based on available capabilities.
    4. Close all registered agents on shutdown.
    """

    def __init__(self) -> None:
        self._entries: dict[str, AgentEntry] = {}

    # -- Registration -------------------------------------------------------

    def register(self, entry: AgentEntry) -> None:
        """Register a delegatable agent.

        Raises ``ValueError`` if the tool schema is malformed or the tool
        name is already registered.
        """
        _validate_tool_definition(entry.tool_definition)
        if entry.name in self._entries:
            raise ValueError(f"Agent tool '{entry.name}' is already registered")
        self._entries[entry.name] = entry
        _log.info(
            "Registered agent '%s' (capabilities=%s)",
            entry.name,
            entry.capabilities,
        )

    # -- Lookup -------------------------------------------------------------

    def get(self, tool_name: str) -> AgentEntry | None:
        """Return the entry for *tool_name*, or ``None``."""
        return self._entries.get(tool_name)

    def has(self, tool_name: str) -> bool:
        """Check whether *tool_name* is registered."""
        return tool_name in self._entries

    def has_capability(self, capability: Capability) -> bool:
        """Check whether any registered agent advertises *capability*."""
        return any(capability in entry.capabilities for entry in self._entries.values())

    # -- Tool definitions ---------------------------------------------------

    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return tool schemas for all registered agents.

        These are appended to the core tool list so the LLM can see and
        call delegation tools.
        """
        return [entry.tool_definition for entry in self._entries.values()]

    # -- Capabilities -------------------------------------------------------

    def capabilities(self) -> frozenset[Capability]:
        """Return the union of all registered agent capabilities."""
        caps: set[Capability] = set()
        for entry in self._entries.values():
            caps.update(entry.capabilities)
        return frozenset(caps)

    # -- Lifecycle ----------------------------------------------------------

    async def close_all(self) -> None:
        """Close all registered agents, deduped by identity.

        Safe to call multiple times.  Agents that share the same
        identity (e.g. registered under two tool names) are closed
        only once.
        """
        seen: set[int] = set()
        for entry in self._entries.values():
            agent_id = id(entry.agent)
            if agent_id in seen:
                continue
            seen.add(agent_id)
            try:
                await entry.agent.close()
            except Exception:
                _log.warning("Error closing agent '%s'", entry.name, exc_info=True)

    # -- Iteration ----------------------------------------------------------

    def __iter__(self) -> Iterator[AgentEntry]:
        return iter(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)
