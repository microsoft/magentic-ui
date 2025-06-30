from typing import List, Set

import pytest
from autogen_ext.tools.mcp import SseServerParams, StdioServerParams
from magentic_ui.tools.mcp import (
    AggregateMcpWorkbench,
    NamedMcpServerParams,
)

from magentic_ui.tools.mcp._aggregate_workbench import (
    escape_tool_name,
    unescape_tool_name,
    NAMESPACE_ESCAPE,
    NAMESPACE_SEPARATOR,
)


@pytest.fixture
def named_server_params() -> List[NamedMcpServerParams]:
    """
    Returns two NamedMcpServerParams with different server names.
    """
    params1 = NamedMcpServerParams(
        server_name="server1",
        server_params=StdioServerParams(
            command="python", args=["-m", "mcp_server_time"]
        ),
    )
    params2 = NamedMcpServerParams(
        server_name="server2",
        server_params=StdioServerParams(
            command="python", args=["-m", "mcp_server_time"]
        ),
    )
    return [params1, params2]


def test_escape_tool_name_roundtrip():
    assert (
        escape_tool_name(f"abc{NAMESPACE_SEPARATOR}123") == f"abc{NAMESPACE_ESCAPE}123"
    )
    assert (
        unescape_tool_name(f"abc{NAMESPACE_ESCAPE}123")
        == f"abc{NAMESPACE_SEPARATOR}123"
    )


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
            # This won't actually be used
            server_params=SseServerParams(url="http://localhost:3001/sse"),
        ),
        NamedMcpServerParams(
            server_name="dup",
            # This won't actually be used
            server_params=SseServerParams(url="http://localhost:3002/sse"),
        ),
    ]
    with pytest.raises(ValueError):
        AggregateMcpWorkbench(params)


@pytest.mark.npx  # Requires npx available on the system to launch the MCP servers
@pytest.mark.asyncio
async def test_list_tools_namespaces_tools(
    named_server_params: List[NamedMcpServerParams],
):
    workbench = AggregateMcpWorkbench(named_server_params)
    # Essentially just a test to see if this doesn't error
    tools = await workbench.list_tools()
    assert len(tools) > 0


@pytest.mark.asyncio
async def test_call_tool_bad_format_tool_name_raises(
    named_server_params: List[NamedMcpServerParams],
):
    workbench = AggregateMcpWorkbench(named_server_params)
    # Pass an invalid tool name (missing server_name)
    with pytest.raises(ValueError):
        await workbench.call_tool("notnamespacedtool")


@pytest.mark.asyncio
async def test_call_tool_missing_server_name_raises(
    named_server_params: List[NamedMcpServerParams],
):
    workbench = AggregateMcpWorkbench(named_server_params)

    # Pass an invalid server name
    with pytest.raises(KeyError):
        await workbench.call_tool("unknownserver-tool", {})


@pytest.mark.npx  # Requires npx available on the system to launch the MCP servers
@pytest.mark.asyncio
async def test_call_tool_missing_tool_name_raises(
    named_server_params: List[NamedMcpServerParams],
):
    workbench = AggregateMcpWorkbench(named_server_params)

    # Pass an invalid server name
    with pytest.raises(KeyError):
        await workbench.call_tool("server1-unknowntool", {})
