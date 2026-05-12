import asyncio
import json
import os
import aiofiles
import logging
import datetime
from PIL import Image
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple, Optional
from autogen_core.models import ChatCompletionClient
from autogen_core import Image as AGImage
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import AgentMessage, ChatMessage, TextMessage, ToolCallMessage, ToolCallResultMessage
from autogen_agentchat.teams import BaseGroupChat, RoundRobinGroupChat
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.ui import Console

logger = logging.getLogger(__name__)

class MagenticOneSystem(BaseModel):
    """System for Magentic-One benchmark evaluation."""
    client: ChatCompletionClient
    max_turns: int = 10

    def __init__(self, client: ChatCompletionClient, max_turns: int = 10):
        super().__init__(client=client, max_turns=max_turns)
        self.client = client
        self.max_turns = max_turns

    def _parse_thoughts_and_action(self, response: str) -> Tuple[str, str]:
        """Parse model response into thoughts and action.
        
        Expected format: "Thoughts: <thoughts>\nAction: <action>"
        Falls back to empty strings on missing content or index errors.
        """
        if not response or not response.strip():
            logger.warning("Empty response received, returning empty thoughts and action")
            return "", ""

        try:
            # Look for markers with flexible parsing
            thoughts_marker = "Thoughts:"
            action_marker = "Action:"

            # Find the index of markers
            thought_start = response.find(thoughts_marker)
            action_start = response.find(action_marker)

            if thought_start == -1 and action_start == -1:
                # No markers found, treat entire response as action
                return "", response.strip()

            if thought_start != -1:
                thought_start += len(thoughts_marker)
                if action_start != -1:
                    thoughts = response[thought_start:action_start].strip()
                else:
                    thoughts = response[thought_start:].strip()
            else:
                thoughts = ""

            if action_start != -1:
                action_start += len(action_marker)
                action = response[action_start:].strip()
            else:
                action = ""

            return thoughts, action
        except (IndexError, ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse thoughts/action: {e}. Response: {response[:100]}...")
            return "", ""

    async def run(self, task: str) -> Dict[str, Any]:
        """Execute a single task and return result."""
        # Simplified run logic for demonstration
        messages = [
            {"role": "system", "content": "You are Magentic-One. Always output thoughts and action."},
            {"role": "user", "content": task}
        ]
        try:
            response = await self.client.create(messages)
            content = response.content if response and hasattr(response, 'content') else ""
            if not content:
                logger.error("Empty response from model")
                return {"success": False, "error": "Empty model response"}
            thoughts, action = self._parse_thoughts_and_action(content)
            return {"success": True, "thoughts": thoughts, "action": action, "raw_response": content}
        except Exception as e:
            logger.exception(f"Run failed: {e}")
            return {"success": False, "error": str(e)}