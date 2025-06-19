import asyncio
import warnings
from typing import Any, Dict, List, Literal, Mapping

from autogen_core import CancellationToken, Component
from autogen_core.tools import (
    ToolResult,
    ToolSchema,
    Workbench,
)
from pydantic import BaseModel

from autogen_ext.tools.mcp import (
    McpWorkbench,
    McpServerParams,
)

# According to the OpenAI API tool names can contain "Only letters, numbers, '_' and '-' are allowed."
NAMESPACE_SEPARATOR = "-"
# The 'escape' value to use for NAMESPACE_SEPARATOR (specificaly a value outside of the allowable range)
NAMESPACE_ESCAPE = ":"


def escape_tool_name(name: str) -> str:
    """
    Escapes all occurrences of the NAMESPACE_SEPARATOR in the tool name by replacing them with NAMESPACE_ESCAPE.
    """
    return name.replace(NAMESPACE_SEPARATOR, NAMESPACE_ESCAPE)


def unescape_tool_name(name: str) -> str:
    """
    Unescapes all occurrences of NAMESPACE_ESCAPE in the tool name by replacing them with NAMESPACE_SEPARATOR.
    """
    return name.replace(NAMESPACE_ESCAPE, NAMESPACE_SEPARATOR)


class NamedMcpServerParams(BaseModel):
    """A 'namespaced' McpServer"""

    server_name: str
    """The unique name of the server"""
    server_params: McpServerParams
    """The SseServerParams or StdioServerParams for the server."""


class AggregateMcpWorkbenchConfig(BaseModel):
    named_server_params: List[NamedMcpServerParams]


class AggregateMcpWorkbenchState(BaseModel):
    type: Literal["AggregateMcpWorkbenchState"] = "AggregateMcpWorkbenchState"


class AggregateMcpWorkbench(Workbench, Component[AggregateMcpWorkbenchConfig]):
    """
    A workbench that aggregates multiple named MCP servers, providing a unified interface
    to list and call tools from all servers. Each server is given a unique name, and tools
    from each server are namespaced using this name (e.g., "server1.tool_name").

    Args:
        named_server_params (List[NamedMcpServerParams]):
            A list of server configurations, each with a unique name and corresponding MCP server parameters.

    Examples:

        Here is an example of how to use the aggregate workbench with two MCP servers:

        .. code-block:: python

            import asyncio

            from autogen_ext.tools.mcp import StdioServerParams
            from magentic_ui.tools.mcp import AggregateMcpWorkbench, NamedMcpServerParams

            async def main() -> None:
                server1 = NamedMcpServerParams(
                    server_name="fetch",
                    server_params=StdioServerParams(command="uvx", args=["mcp-server-fetch"]),
                )
                server2 = NamedMcpServerParams(
                    server_name="github",
                    server_params=StdioServerParams(command="docker", args=["run", "ghcr.io/github/github-mcp-server"]),
                )
                async with AggregateMcpWorkbench([server1, server2]) as workbench:
                    tools = await workbench.list_tools()
                    print(tools)  # Tool names will be namespaced, e.g., 'fetch.tool1', 'github.tool2'
                    result = await workbench.call_tool("fetch.some_tool", {"url": "https://github.com/"})
                    print(result)

            asyncio.run(main())

    Notes:
        - Tool names are automatically namespaced with their server name (e.g., 'server_name.tool_name').
        - Use the namespaced tool name when calling tools.
        - All server names must be unique.
    """

    component_provider_override = "magentic_ui.tools.mcp.AggregateMcpWorkbench"
    component_config_schema = AggregateMcpWorkbenchConfig

    def __init__(self, named_server_params: List[NamedMcpServerParams]) -> None:
        # Create a copy of server_params
        self._workbenches: Dict[str, McpWorkbench] = {}
        for params in named_server_params:
            # Check if valid
            if escape_tool_name(params.server_name) != params.server_name:
                raise ValueError(
                    f"Invalid server_name '{params.server_name}'. Server names must not include {NAMESPACE_SEPARATOR} characters."
                )

            if params.server_name in self._workbenches:
                raise ValueError(
                    f"Each server_name in named_server_params must be unique. Encountered duplicate server_name: '{params.server_name}'"
                )
            else:
                self._workbenches[params.server_name] = McpWorkbench(
                    server_params=params.server_params
                )

    @property
    def server_params(self) -> List[NamedMcpServerParams]:
        return [
            NamedMcpServerParams(
                server_name=server_name, server_params=workbench.server_params
            )
            for server_name, workbench in self._workbenches.items()
        ]

    async def list_tools(self) -> List[ToolSchema]:
        schema: List[ToolSchema] = []
        for server_name, workbench in self._workbenches.items():
            workbench_tools = await workbench.list_tools()
            for tool in workbench_tools:
                # Make a copy of the tool updating the name to be escaped and within this server's 'namespace'
                tool_name = escape_tool_name(tool["name"])
                namespaced_tool_name = f"{server_name}{NAMESPACE_SEPARATOR}{tool_name}"
                namespaced_tool = ToolSchema({**tool, "name": namespaced_tool_name})
                schema.append(namespaced_tool)

        return schema

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ToolResult:
        try:
            # Split the server name from teh tool name
            server_name, tool_name = name.split(NAMESPACE_SEPARATOR, 1)
            # Unescape before sending to teh workbench
            tool_name = unescape_tool_name(tool_name)
        except ValueError:
            raise ValueError(
                f"Cannot call tool named '{name}' with AggregateMcpWorkbench. Expected format: '{{server_name}}{NAMESPACE_SEPARATOR}{{tool_name}}'."
            )

        # Get the workbench for that server
        workbench = self._workbenches.get(server_name, None)
        if not workbench:
            raise KeyError(
                f"Cannot call tool named '{tool_name}' on server '{server_name}'. No known servers with that name."
            )

        # Invoke the tool within that namespace
        return await workbench.call_tool(
            tool_name, arguments=arguments, cancellation_token=cancellation_token
        )

    async def start(self) -> None:
        await asyncio.gather(
            *[workbench.start() for workbench in self._workbenches.values()]
        )

    async def stop(self) -> None:
        await asyncio.gather(
            *[workbench.stop() for workbench in self._workbenches.values()]
        )

    async def reset(self) -> None:
        await asyncio.gather(
            *[workbench.reset() for workbench in self._workbenches.values()]
        )

    async def save_state(self) -> Mapping[str, Any]:
        # TODO: McpWorkbenchState is a 'dummy' class so this is okay for now but we will eventually need to aggregate the sub-workbench states
        return AggregateMcpWorkbenchState().model_dump()

    async def load_state(self, state: Mapping[str, Any]) -> None:
        # TODO: No state to save, so nothing to do. Again will need to fix this if it ever changes in the base McpWorkbench
        pass

    def _to_config(self) -> AggregateMcpWorkbenchConfig:
        named_server_params: List[NamedMcpServerParams] = []
        for server_name, workbench in self._workbenches.items():
            params = NamedMcpServerParams(
                server_name=server_name, server_params=workbench.server_params
            )
            named_server_params.append(params)

        return AggregateMcpWorkbenchConfig(named_server_params=named_server_params)

    @classmethod
    def _from_config(cls, config: AggregateMcpWorkbenchConfig):
        return cls(named_server_params=config.named_server_params)

    def __del__(self) -> None:
        for name, workbench in self._workbenches.items():
            try:
                del workbench
            except Exception as ex:
                msg = f"Caught exception deleting workbench for server named '{name}'. {type(ex).__name__}: {ex}"
                warnings.warn(msg, RuntimeWarning, stacklevel=2)
