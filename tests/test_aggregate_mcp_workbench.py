import asyncio
import subprocess
import time
from typing import Generator, List, Set

import pytest
import requests
from autogen_ext.tools.mcp import SseServerParams, StdioServerParams
from magentic_ui.tools.mcp import (
    AggregateMcpWorkbench,
    NamedMcpServerParams,
)


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
def named_server_params(everything_server: None) -> List[NamedMcpServerParams]:
    """
    Returns two NamedMcpServerParams with different server names, one using StdioServerParams and one using SseServerParams, both pointing to the same 'everything' MCP server.
    """
    params1 = NamedMcpServerParams(
        server_name="server1",
        server_params=StdioServerParams(
            command="npx", args=["-y", "@modelcontextprotocol/server-everything"]
        ),
    )
    params2 = NamedMcpServerParams(
        server_name="server2",
        server_params=SseServerParams(url="http://localhost:3001/sse"),
    )
    return [params1, params2]


def test_init_creates_workbenches(named_server_params: List[NamedMcpServerParams]):
    workbench = AggregateMcpWorkbench(named_server_params)
    # Check that all the keys are there
    expected_keys: Set[str] = set(params.server_name for params in named_server_params)
    actual_keys: Set[str] = set(workbench._workbenches.keys())  # type: ignore
    assert expected_keys == actual_keys


def test_init_duplicate_server_name_raises():
    params = [
        NamedMcpServerParams(
            server_name="dup",
            server_params=StdioServerParams(
                command="npx", args=["-y", "@modelcontextprotocol/server-everything"]
            ),
        ),
        NamedMcpServerParams(
            server_name="dup",
            server_params=StdioServerParams(
                command="npx", args=["-y", "@modelcontextprotocol/server-everything"]
            ),
        ),
    ]
    with pytest.raises(ValueError):
        AggregateMcpWorkbench(params)


def test_list_tools_namespaces_tools(named_server_params: List[NamedMcpServerParams]):
    workbench = AggregateMcpWorkbench(named_server_params)
    # Essentially just a test to see if this doesn't error
    tools = asyncio.run(workbench.list_tools())
    assert len(tools) > 0


def test_call_tool_invalid_name_raises(named_server_params: List[NamedMcpServerParams]):
    workbench = AggregateMcpWorkbench(named_server_params)
    # Pass an invalid tool name (missing server_name)
    with pytest.raises(ValueError):
        asyncio.run(workbench.call_tool("notnamespacedtool"))

    # Pass an invalid server name
    with pytest.raises(KeyError):
        asyncio.run(workbench.call_tool("unknownserver-tool", {}))
