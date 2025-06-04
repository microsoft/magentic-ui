from typing import List

from autogen_agentchat.agents._assistant_agent import AssistantAgentConfig

from ...tools.mcp import NamedMcpServerParams


class McpAgentConfig(AssistantAgentConfig):
    mcp_servers: List[NamedMcpServerParams]
    tool_call_summary_format: str = "{tool_name}({arguments}): {result}"
