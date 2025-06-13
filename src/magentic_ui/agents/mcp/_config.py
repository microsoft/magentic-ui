from typing import List

from autogen_agentchat.agents._assistant_agent import AssistantAgentConfig

from ...tools.mcp import NamedMcpServerParams


class McpAgentConfig(AssistantAgentConfig):
    mcp_servers: List[NamedMcpServerParams]
    model_context_token_limit: int | None = None
    tool_call_summary_format: str = "{tool_name}({arguments}): {result}"
    reflect_on_tool_use: bool = False
