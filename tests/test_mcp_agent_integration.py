import subprocess
import time
from pathlib import Path
from typing import Any, Generator, List

import pytest
import requests
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import BaseTextChatMessage
from autogen_core import ComponentModel
from autogen_ext.tools.mcp import SseServerParams
from magentic_ui.agents.mcp import McpAgentConfig
from magentic_ui.magentic_ui_config import MagenticUIConfig, ModelClientConfigs
from magentic_ui.task_team import RunPaths, get_task_team
from magentic_ui.tools.mcp import NamedMcpServerParams


def _start_npx_everything_server():
    proc = subprocess.Popen(
        ["npx", "-y", "@modelcontextprotocol/server-everything", "sse"],
    )
    _wait_for_server_ready()
    return proc


def _wait_for_server_ready(
    timeout: int = 30,
    url: str = "http://localhost:3001/health",
) -> None:
    for i in range(timeout):
        try:
            requests.get(url)
            print(f"[MCP everything server] Ready after {i+1} seconds.")
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("everything server did not start in time")


@pytest.fixture(scope="module")
def everything_server() -> Generator[None, None, None]:
    proc = None
    try:
        proc = _start_npx_everything_server()
        yield
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()


@pytest.fixture
def model_client_configs() -> ModelClientConfigs:
    return ModelClientConfigs()


@pytest.fixture
def mcp_agent_config(
    everything_server: Any, model_client_configs: ModelClientConfigs
) -> List[McpAgentConfig]:
    params = [
        NamedMcpServerParams(
            server_name="MCPServer",
            server_params=SseServerParams(url="http://localhost:3001/sse"),
        ),
    ]
    return [
        McpAgentConfig(
            name="mcp_agent",
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


@pytest.mark.asyncio
async def test_mcp_agent_integration(mcp_agent_config: List[McpAgentConfig]):
    # Create MagenticUIConfig with MCP agent config
    config = MagenticUIConfig(
        mcp_agent_configs=mcp_agent_config,
        cooperative_planning=False,
        autonomous_execution=True,
        user_proxy_type="dummy",
        headless=True,
        inside_docker=False,
    )
    team = await get_task_team(magentic_ui_config=config, paths=_dummy_paths())
    # Send a test message to the team and get a response
    try:
        async for event in team.run_stream(task="List the MCP tools."):
            if isinstance(event, BaseTextChatMessage):
                print(f"[ {event.source} ]")
                print(event.content)
                print()
            if isinstance(event, TaskResult):
                break
    finally:
        await team.close()
