from typing import AsyncGenerator, Sequence, List, Literal
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    TextMessage,
)
from autogen_core.model_context import TokenLimitedChatCompletionContext
from autogen_core import CancellationToken
from autogen_core.models import (
    ChatCompletionClient,
    UserMessage,
    LLMMessage,
    SystemMessage,
    AssistantMessage,
)
from ...utils import thread_to_context


SYSTEM_MESSAGE_PLANNING_PHASE_STRICT = """
**Context:**
You are tasked with role playing as a human user who is interacting with an AI to solve a task for you. 

The task is: {task} 

The AI will provide a plan for the task in the past messages.

{helpful_task_hints}

The AI has no knowledge of the helpful hints. 

**INSTRUCTIONS:**

You need to provide a response to the AI's plan as the user.

Case 1: If you believe the plan is perfect and will enable the AI to solve the task, respond with the following  string only: accept. The word "accept" only should be your response.

Case 2: If you have feedback that can improve the plan and the chance of success, then write a response with natural language feedback to improve the plan.
The helpful hints can be useful to improve the plan. 

Phrase your response as if you are a user who is providing feedback to the AI. You are the user in this conversation.
"""


SYSTEM_MESSAGE_PLANNING_PHASE_SOFT = """
**Context:**
You are tasked with role playing as a human user who is interacting with an AI to solve a task for you. 

The task is: {task} 

The AI will provide a plan for the task in the past messages.

{helpful_task_hints}

{answer}

The AI has no knowledge of the answer to the task or the helpful hints. 

**INSTRUCTIONS:**

You need to provide a response to the AI's plan as the user.

Case 1: If you believe the plan is perfect and will enable the AI to solve the task, respond with the following  string only: accept. The word "accept" only should be your response.

Case 2: If you have feedback that can improve the plan and the chance of success, then write a response with natural language feedback to improve the plan.
The helpful hints can be useful to improve the plan. Do not reveal the answer to the task directly.

Phrase your response as if you are a user who is providing feedback to the AI. You are the user in this conversation.
"""


SYSTEM_MESSAGE_EXECUTION_PHASE_SOFT = """
**Context:**

You are tasked with role playing as a human user who is interacting with an AI to solve a task for you.

The task is: {task} 

{helpful_task_hints}

{answer}

The AI has no knowledge of the answer to the task or the helpful hints. 

The above messages include steps the AI has taken to solve the task.

The last message is a question the AI is asking you for help.

**INSTRUCTIONS:**
Provide a response to the AI's question to help them solve the task.
"""


SYSTEM_MESSAGE_EXECUTION_PHASE_STRICT = """
**Context:**

You are tasked with role playing as a human user who is interacting with an AI to solve a task for you.

The task is: {task} 

{helpful_task_hints}

The AI has no knowledge of the helpful hints. 

The above messages include steps the AI has taken to solve the task.

The last message is a question the AI is asking you for help.

**INSTRUCTIONS:**
Provide a response to the AI's question to help them solve the task.
"""

SYSTEM_MESSAGE_PLANNING_PHASE_NO_HINTS = """
**Context:**
You are tasked with role playing as a human user who is interacting with an AI to solve a task for you.

The task is: {task}

The AI will provide a plan for the task in the past messages.

**INSTRUCTIONS:**

You need to provide a response to the AI's plan as the user.

Case 1: If you believe the plan is perfect and will enable the AI to solve the task, respond with the following string only: accept. The word "accept" only should be your response.

Case 2: If you have feedback that can improve the plan and the chance of success, then write a response with natural language feedback to improve the plan.
Phrase your response as if you are a user who is providing feedback to the AI. You are the user in this conversation.
"""

SYSTEM_MESSAGE_EXECUTION_PHASE_NO_HINTS = """
**Context:**

You are tasked with role playing as a human user who is interacting with an AI to solve a task for you.

The task is: {task}

The above messages include steps the AI has taken to solve the task.

The last message is a question the AI is asking you for help.

**INSTRUCTIONS:**
Provide a response to the AI's question to help them solve the task. 
"""


class MetadataUserProxy(BaseChatAgent):
    def __init__(
        self,
        name: str,
        description: str,
        model_client: ChatCompletionClient,
        task: str = "",
        helpful_task_hints: str = "",
        task_answer: str = "",
        simulated_user_type: Literal[
            "co-planning", "co-execution", "co-planning-and-execution", "none"
        ] = "none",
        max_co_planning_rounds: int | None = 1,
        max_co_execution_rounds: int | None = 3,
        model_context_token_limit: int = 110000,
        how_helpful: Literal["strict", "soft", "no_hints"] = "soft",
    ):
        """
        Initialize a MetadataUserProxy agent that simulates a human user with access to task metadata.

        Args:
            name (str): Name of the agent
            description (str): Description of the agent's role
            model_client (ChatCompletionClient): Client for interacting with the language model
            task (str, optional): The task to be solved. Default: empty string.
            helpful_task_hints (str, optional): Additional hints to help solve the task. Default: empty string.
            task_answer (str, optional): The known answer to the task. Default: empty string.
            simulated_user_type (Literal["co-planning", "co-execution", "co-planning-and-execution", "none"], optional):
                Type of user simulation. Default: "none".
            max_co_planning_rounds (int | None, optional): Maximum number of planning rounds. None means unlimited. Default: 1.
            max_co_execution_rounds (int | None, optional): Maximum number of execution rounds. None means unlimited. Default: 1.
            model_context_token_limit (int, optional): Token limit for model context. Default: 128000.
            how_helpful (Literal["strict", "soft", "no_hints"], optional): How helpful the user is. Default: "soft".
                "strict": simulated user does not have access to answer and rewrites hints to remove answer
                "soft": simulated user has access to answer and helpful hints
                "no_hints": simulated user does not have access to hints or answer
        """

        super().__init__(name, description)
        self.task = task
        self.helpful_task_hints = (
            (
                "We have access to helpful hints that helps in solving the task: "
                + helpful_task_hints
            )
            if helpful_task_hints
            else ""
        )
        self.task_answer = (
            ("We know the answer to the task and it is: " + task_answer)
            if task_answer
            else ""
        )
        self._model_client = model_client
        self._model_context = TokenLimitedChatCompletionContext(
            model_client,
            token_limit=model_context_token_limit,
        )
        self.simulated_user_type = simulated_user_type
        self.in_planning_phase = True
        self.max_co_planning_rounds = max_co_planning_rounds
        self.current_co_planning_round = 0
        self.max_co_execution_rounds = max_co_execution_rounds
        self.current_co_execution_round = 0
        self._chat_history: List[LLMMessage] = []
        self.how_helpful = how_helpful
        self.rewritten_helpful_task_hints = None
        self.have_encountered_plan_message = False

    def _get_system_message(self) -> str:
        """
        Generate the appropriate system message based on the current phase and helpfulness level.

        Returns:
            str: The system message for the current phase and helpfulness level.
        """
        if self.in_planning_phase:
            if self.how_helpful == "strict":
                return SYSTEM_MESSAGE_PLANNING_PHASE_STRICT.format(
                    task=self.task,
                    helpful_task_hints=self.rewritten_helpful_task_hints,
                )
            elif self.how_helpful == "no_hints":
                return SYSTEM_MESSAGE_PLANNING_PHASE_NO_HINTS.format(
                    task=self.task,
                )
            else:
                return SYSTEM_MESSAGE_PLANNING_PHASE_SOFT.format(
                    task=self.task,
                    helpful_task_hints=self.helpful_task_hints,
                    answer=self.task_answer,
                )
        else:
            if self.how_helpful == "strict":
                return SYSTEM_MESSAGE_EXECUTION_PHASE_STRICT.format(
                    task=self.task,
                    helpful_task_hints=self.rewritten_helpful_task_hints,
                )
            elif self.how_helpful == "no_hints":
                return SYSTEM_MESSAGE_EXECUTION_PHASE_NO_HINTS.format(
                    task=self.task,
                )
            else:
                return SYSTEM_MESSAGE_EXECUTION_PHASE_SOFT.format(
                    task=self.task,
                    helpful_task_hints=self.helpful_task_hints,
                    answer=self.task_answer,
                )

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        """Get the types of messages produced by the agent."""
        return (TextMessage,)

    async def on_messages(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        response: Response | None = None
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                response = message
        assert response is not None
        return response

    async def _rewrite_helpful_hints(
        self, cancellation_token: CancellationToken
    ) -> str:
        """
        Use the LLM to rewrite the helpful_task_hints to remove any information that directly reveals the answer.
        Returns the rewritten hints as a string.
        """
        if not self.helpful_task_hints or self.helpful_task_hints == "":
            return self.helpful_task_hints
        prompt = f"""Rewrite the following helpful hints to help solve the task, but remove any information that directly reveals the answer. 
Keep the hints as close to the original as possible but remove any information that directly reveals the answer.
Helpful hints: {self.helpful_task_hints}

Answer: {self.task_answer}

Do not include anything else in your response except the rewritten hints.
Rewritten helpful hints:"""
        result = await self._model_client.create(
            messages=[UserMessage(content=prompt, source="user")],
            cancellation_token=cancellation_token,
        )
        assert isinstance(result.content, str)
        return (
            "We have access to helpful hints that helps in solving the task: "
            + result.content.strip()
        )

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        # In strict mode, if helpful_task_hints is not empty, rewrite the hints to remove the answer
        if (
            self.how_helpful == "strict"
            and self.helpful_task_hints
            and self.helpful_task_hints
            != "Helpful hints are not available for this task."
            and self.rewritten_helpful_task_hints is None
        ):
            self.rewritten_helpful_task_hints = await self._rewrite_helpful_hints(
                cancellation_token
            )
        chat_messages = thread_to_context(
            list(messages),
            agent_name=self.name,
            is_multimodal=self._model_client.model_info["vision"],
        )
        self._chat_history.extend(chat_messages)
        if (
            "type" in messages[-1].metadata
            and messages[-1].metadata["type"] == "plan_message"
        ):
            self.have_encountered_plan_message = True
            self.in_planning_phase = True
        else:
            if self.have_encountered_plan_message:
                self.in_planning_phase = False
            else:
                self.in_planning_phase = True

        # Re-initialize model context to meet token limit quota
        await self._model_context.clear()

        # Create system message
        system_message = SystemMessage(content=self._get_system_message())

        # Add system message at start
        await self._model_context.add_message(system_message)

        # Add all chat history
        for msg in self._chat_history:
            await self._model_context.add_message(msg)

        # Add system message again at end
        user_system_message = UserMessage(
            content=self._get_system_message(), source="user"
        )
        await self._model_context.add_message(user_system_message)

        # Get token limited history
        token_limited_history = await self._model_context.get_messages()

        if self.in_planning_phase:
            if self.simulated_user_type in ["co-planning", "co-planning-and-execution"]:
                if (
                    self.max_co_planning_rounds is None
                    or self.current_co_planning_round < self.max_co_planning_rounds
                ):
                    result = await self._model_client.create(
                        messages=token_limited_history,
                        cancellation_token=cancellation_token,
                    )
                    assert isinstance(result.content, str)

                    yield Response(
                        chat_message=TextMessage(
                            content=result.content,
                            source=self.name,
                            metadata={
                                "co_planning_round": str(
                                    self.current_co_planning_round
                                ),
                                "user_plan_reply": "llm",
                                "helpful_task_hints": self.rewritten_helpful_task_hints
                                if self.rewritten_helpful_task_hints
                                else self.helpful_task_hints,
                            },
                        ),
                        inner_messages=[],
                    )
                    self._chat_history.append(
                        AssistantMessage(
                            content=result.content,
                            source=self.name,
                        )
                    )
                    if "accept" in result.content:
                        self.in_planning_phase = False
                    self.current_co_planning_round += 1
                else:
                    yield Response(
                        chat_message=TextMessage(
                            content="accept",
                            source=self.name,
                            metadata={
                                "co_planning_round": str(
                                    self.current_co_planning_round
                                ),
                                "user_plan_reply": "accept",
                            },
                        ),
                        inner_messages=[],
                    )
                    self._chat_history.append(
                        AssistantMessage(
                            content="accept",
                            source=self.name,
                        )
                    )
                    self.in_planning_phase = False
            else:
                yield Response(
                    chat_message=TextMessage(
                        content="accept",
                        source=self.name,
                        metadata={
                            "co_planning_round": str(self.current_co_planning_round),
                            "user_plan_reply": "accept",
                        },
                    ),
                    inner_messages=[],
                )

                self.in_planning_phase = False
        else:
            if self.simulated_user_type in [
                "co-execution",
                "co-planning-and-execution",
            ]:
                if (
                    self.max_co_execution_rounds is None
                    or self.current_co_execution_round < self.max_co_execution_rounds
                ):
                    result = await self._model_client.create(
                        messages=token_limited_history,
                        cancellation_token=cancellation_token,
                    )

                    assert isinstance(result.content, str)

                    yield Response(
                        chat_message=TextMessage(
                            content=result.content,
                            source=self.name,
                            metadata={
                                "user_execution_reply": "llm",
                            },
                        ),
                        inner_messages=[],
                    )
                    self._chat_history.append(
                        AssistantMessage(
                            content=result.content,
                            source=self.name,
                        )
                    )
                    self.current_co_execution_round += 1
                else:
                    yield Response(
                        chat_message=TextMessage(
                            content="I don't know, you figure it out, don't ask me again.",
                            source=self.name,
                        ),
                    )
            else:
                yield Response(
                    chat_message=TextMessage(
                        content="I don't know, you figure it out, don't ask me again.",
                        source=self.name,
                        metadata={
                            "user_execution_reply": "idk",
                        },
                    ),
                )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """
        Reset the model context.
        """
        self._chat_history = []

    async def close(self) -> None:
        await self._model_client.close()
