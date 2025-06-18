from typing import AsyncGenerator, Sequence, List

from autogen_core.models import (
    LLMMessage,
    AssistantMessage,
)

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, TextMessage
from autogen_core import CancellationToken
from ...utils import thread_to_context


class DummyUserProxy(BaseChatAgent):
    """A dummy user proxy agent that simulates user interactions."""

    def __init__(self, name: str):
        """
        Initialize the DummyUserProxy agent.

        Args:
            name (str): The name of the agent.
        """
        super().__init__(name, "A dummy user proxy agent.")
        self._in_planning_phase = True
        self._chat_history: List[LLMMessage] = []

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        """Get the types of messages produced by the agent."""
        return (TextMessage,)

    async def on_messages(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        """
        Handle incoming messages and return a single response.

        Args:
            messages (Sequence[BaseChatMessage]): A sequence of incoming chat messages.
            cancellation_token (CancellationToken): A token to cancel the operation if needed.

        Returns:
            Response: A single `Response` object generated from the incoming messages.
        """
        # Calls the on_messages_stream.
        response: Response | None = None
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                response = message
        assert response is not None
        return response

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        """
        Handle incoming messages and yield responses as a stream.

        Args:
            messages (Sequence[BaseChatMessage]): A sequence of incoming chat messages.
            cancellation_token (CancellationToken): A token to cancel the operation if needed.

        Yields:
            AsyncGenerator: A stream of `BaseAgentEvent`, `BaseChatMessage`, or `Response`.
        """
        chat_messages = thread_to_context(
            list(messages),
            agent_name=self.name,
            is_multimodal=True,
        )
        self._chat_history.extend(chat_messages)
        if (
            "type" in messages[-1].metadata
            and messages[-1].metadata["type"] == "plan_message"
        ):
            self._in_planning_phase = True
        else:
            self._in_planning_phase = False

        if self._in_planning_phase:
            self._first_response_given = True
            yield Response(
                chat_message=TextMessage(content="accept", source=self.name),
                inner_messages=[],
            )
            self._chat_history.append(
                AssistantMessage(
                    content="accept",
                    source=self.name,
                )
            )
        else:
            yield Response(
                chat_message=TextMessage(
                    content="I don't know. Use your best judgment.", source=self.name
                ),
                inner_messages=[],
            )
            self._chat_history.append(
                AssistantMessage(
                    content="I don't know. Use your best judgment.",
                    source=self.name,
                )
            )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        self._first_response_given = False
        self._chat_history = []
