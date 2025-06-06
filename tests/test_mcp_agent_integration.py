from pathlib import Path
from typing import List

import pytest
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import BaseTextChatMessage
from autogen_core import CancellationToken, ComponentModel
from autogen_ext.tools.mcp import StdioServerParams
from magentic_ui.agents.mcp import McpAgentConfig
from magentic_ui.magentic_ui_config import MagenticUIConfig, ModelClientConfigs
from magentic_ui.task_team import RunPaths, get_task_team
from magentic_ui.tools.mcp import NamedMcpServerParams


MCP_AGENT_NAME = "mcp_agent"
MAX_MESSAGES = 10


@pytest.fixture
def model_client_configs() -> ModelClientConfigs:
    return ModelClientConfigs()


@pytest.fixture
def mcp_agent_config(model_client_configs: ModelClientConfigs) -> List[McpAgentConfig]:
    params = [
        NamedMcpServerParams(
            server_name="MCPServer",
            server_params=StdioServerParams(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-everything"],
            ),
        ),
    ]
    return [
        McpAgentConfig(
            name=MCP_AGENT_NAME,
            description="An agent with access to an MCP server that has additional tools.",
            system_message="You have access to a list of tools available on one or more MCP servers. Use the tools to solve user tasks.",
            mcp_servers=params,
            model_client=ComponentModel(
                **model_client_configs.get_default_client_config()
            ),
            reflect_on_tool_use=False,
        )
    ]


def _dummy_paths():
    # Provide RunPaths for testing (adjust as needed for your environment)
    return RunPaths(
        internal_run_dir=Path("/tmp"),
        external_run_dir=Path("/tmp"),
        internal_root_dir=Path("/tmp"),
        external_root_dir=Path("/tmp"),
        run_suffix="test_run",
    )


@pytest.mark.npx  # Requires npx available on the system to launch the MCP servers
@pytest.mark.asyncio
async def test_mcp_agent_integration(mcp_agent_config: List[McpAgentConfig]):
    # Create MagenticUIConfig with MCP agent config
    config = MagenticUIConfig(
        mcp_agent_configs=mcp_agent_config,
        cooperative_planning=False,
        autonomous_execution=True,
        user_proxy_type="dummy",
        inside_docker=False,
        browser_headless=True,
        browser_local=True,
    )

    team = await get_task_team(magentic_ui_config=config, paths=_dummy_paths())
    cancellation_token = CancellationToken()
    # Send a test message to the team and get a response
    try:
        message_counter = 0
        async for event in team.run_stream(
            task=f"Ask the {MCP_AGENT_NAME} to list its tools. Then ask it to compute 5 + 3.",
            cancellation_token=cancellation_token,
        ):
            if isinstance(event, BaseTextChatMessage):
                message_counter += 1
                if event.source == MCP_AGENT_NAME:
                    break

            elif isinstance(event, TaskResult):
                break

            # stop this test from getting stuck in a loop
            if message_counter > MAX_MESSAGES:
                assert False, f"Test failed: No {MCP_AGENT_NAME} messages were received within the first {MAX_MESSAGES} messages."
    finally:
        cancellation_token.cancel()
