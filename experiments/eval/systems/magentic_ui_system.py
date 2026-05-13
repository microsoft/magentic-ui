import asyncio
import json
import os
import aiofiles
import logging
import datetime
from pathlib import Path
from PIL import Image
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple, Optional, Union
from autogen_core.models import ChatCompletionClient, AssistantMessage, FunctionExecutionResult, UserMessage
from autogen_core import Image as AGImage
from autogen_agentchat.messages import TextMessage, ToolCallMessage, ToolCallResultMessage, MultiModalMessage
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.state import AgentState
from autogen_core import CancellationToken, ComponentModel

logger = logging.getLogger(__name__)


class MagenticUIAgent(BaseChatAgent):
    def __init__(self, name: str, model_client: ChatCompletionClient, system_message: str = "You are a helpful assistant.", max_consecutive_empty_replies: int = 3, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._model_client = model_client
        self._system_message = system_message
        self._max_consecutive_empty_replies = max_consecutive_empty_replies
        self._consecutive_empty_replies = 0
        self._pending_tool_calls: List[Dict[str, Any]] = []
        self._tool_execution_history: List[Dict[str, Any]] = []

    async def on_messages(self, messages: List[Union[TextMessage, MultiModalMessage, ToolCallMessage, ToolCallResultMessage]], cancellation_token: CancellationToken) -> Response:
        # Build context from messages
        context = []
        for msg in messages:
            if isinstance(msg, TextMessage):
                context.append({"role": "user", "content": msg.content})
            elif isinstance(msg, MultiModalMessage):
                context.append({"role": "user", "content": msg.content})
            elif isinstance(msg, ToolCallMessage):
                context.append({"role": "assistant", "tool_calls": msg.tool_calls})
            elif isinstance(msg, ToolCallResultMessage):
                context.append({"role": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id})
        # Add system message
        full_context = [{"role": "system", "content": self._system_message}] + context
        # Call model
        response = await self._model_client.create(full_context)
        # Parse response
        thought, action = self._parse_thoughts_and_action(response)
        # Build output messages
        output_messages = []
        if action.get("type") == "tool_call":
            tool_call = action["tool_call"]
            output_messages.append(ToolCallMessage(content=tool_call.get("name", ""), tool_calls=[tool_call]))
            self._consecutive_empty_replies = 0
        elif action.get("type") == "text":
            output_messages.append(TextMessage(content=action.get("content", "")))
            self._consecutive_empty_replies = 0
        elif action.get("type") == "empty":
            self._consecutive_empty_replies += 1
            if self._consecutive_empty_replies >= self._max_consecutive_empty_replies:
                output_messages.append(TextMessage(content="I'm sorry, I cannot answer that."))
                self._consecutive_empty_replies = 0
            else:
                # Retry with a prompt to continue
                retry_context = full_context + [{"role": "assistant", "content": "Please continue."}]
                retry_response = await self._model_client.create(retry_context)
                thought_retry, action_retry = self._parse_thoughts_and_action(retry_response)
                if action_retry.get("type") == "tool_call":
                    output_messages.append(ToolCallMessage(content=action_retry["tool_call"].get("name", ""), tool_calls=[action_retry["tool_call"]]))
                elif action_retry.get("type") == "text":
                    output_messages.append(TextMessage(content=action_retry.get("content", "")))
                else:
                    output_messages.append(TextMessage(content="I'm sorry, I cannot answer that."))
                self._consecutive_empty_replies = 0
        else:
            logger.warning(f"Unexpected action type: {action.get('type')}")
            output_messages.append(TextMessage(content="I'm sorry, I cannot answer that."))
        return Response(chat_message=output_messages[0] if output_messages else TextMessage(content=""))

    def _parse_thoughts_and_action(self, response: AssistantMessage) -> Tuple[str, Dict[str, Any]]:
        """Parse the model response into thought and action.  
        Returns a tuple (thought, action) where action is a dict with keys 'type' and possibly 'tool_call' or 'content'.  
        Handles empty responses gracefully to avoid IndexError."""
        thought = ""
        action: Dict[str, Any] = {}

        # Handle case where response is None or missing content
        if response is None or response.content is None:
            logger.warning("Empty response received from model.")
            return (thought, {"type": "empty"})

        # Try to extract tool calls
        tool_calls = getattr(response, "tool_calls", None) or []

        if tool_calls:
            # We have tool calls - use the first one
            tool_call = tool_calls[0]  # This is safe now because we checked non-empty
            # Extract tool call details
            function_name = tool_call.get("function", {}).get("name", "")
            arguments_str = tool_call.get("function", {}).get("arguments", "{}")
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}
            action = {
                "type": "tool_call",
                "tool_call": {
                    "name": function_name,
                    "arguments": arguments,
                    "id": tool_call.get("id", "call_" + str(hash(function_name)))
                }
            }
            thought = response.content or ""
        else:
            # No tool calls - treat as text response
            content = response.content or ""
            if not content.strip():
                # Empty text response
                action = {"type": "empty"}
            else:
                thought = content
                action = {"type": "text", "content": content}

        return (thought, action)