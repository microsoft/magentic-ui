"""CLI-related components for magentic-ui."""

from autogen_agentchat.ui import (
    Console,
)  # Default Console to render stream of messages from Agents
from .pretty_console import (
    PrettyConsole,
)  # Console to render the same stream of messages but prettier

__all__ = ["Console", "PrettyConsole"]
