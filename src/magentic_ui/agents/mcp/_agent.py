from typing import Any, AsyncGenerator, List, Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    BaseTextChatMessage,
    ToolCallRequestEvent,
    ToolCallExecutionEvent,
)
from autogen_core import CancellationToken
from autogen_core.model_context import TokenLimitedChatCompletionContext
from autogen_core.models import ChatCompletionClient

from ...tools.mcp import AggregateMcpWorkbench, NamedMcpServerParams
from ._config import McpAgentConfig


class McpAgent(AssistantAgent):
    """A general agent that can call tools on one or more MCP Servers.

    McpAgent is a thin wrapper around `autogen_agentchat.agents.AssistantAgent`"""

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        *,
        mcp_server_params: List[NamedMcpServerParams] | None = None,
        model_context_token_limit: int | None = None,
        **kwargs: Any,
    ):
        if model_context_token_limit is not None:
            assert (
                "model_context" not in kwargs
            ), "Only one of model_context_token_limit and model_context kwargs are allowed."
            model_context = TokenLimitedChatCompletionContext(
                model_client=self._model_client, token_limit=model_context_token_limit
            )
            kwargs["model_context"] = model_context

        assert mcp_server_params or kwargs.get(
            "workbench", False
        ), "Must provide either mcp_server_params or workbench."
        assert not (
            mcp_server_params and kwargs.get("workbench", False)
        ), "Cannot provide both mcp_server_params and workbench. Only one is allowed."

        if mcp_server_params:
            workbench = AggregateMcpWorkbench(named_server_params=mcp_server_params)
            kwargs["workbench"] = workbench

        super().__init__(name, model_client, **kwargs)  # type: ignore

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        # TODO: Loop through tools until task completed.
        async for event in super().on_messages_stream(messages, cancellation_token):
            # Display some messages to the UI by setting event.metadata = {"internal": False}
            if isinstance(
                event,
                (
                    BaseTextChatMessage,
                    ToolCallRequestEvent,
                    ToolCallExecutionEvent,
                    # ToolCallSummaryMessage,
                ),
            ):
                metadata = getattr(event, "metadata", {})
                metadata = {
                    **metadata,
                    # Display in UI
                    "internal": "no",
                    # Part of a plan step
                    "type": "progress_message",
                }
                setattr(event, "metadata", metadata)

            yield event

    @classmethod
    def _from_config(cls, config: Any):
        if isinstance(config, McpAgentConfig):
            # Build an AggregateMcpWorkbench from the config servers
            # Note, we could build a _single_ McpWorkbench per mcp_server and pass the list of workbenches ot the agent...
            # But then the tools could have name collisions. The AggregateMcpWorkbench scopes each tool within the servers "namespace"
            workbench = AggregateMcpWorkbench(named_server_params=config.mcp_servers)
            # Dump the component so we can load it
            workbench_component = workbench.dump_component()
            # Create a copy of the config with the workbench set to the dumped AggregateMcpWorkbench
            config = config.model_copy(update={"workbench": workbench_component})

        return super()._from_config(config)
