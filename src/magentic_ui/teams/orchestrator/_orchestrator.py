import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Mapping, Callable
import io
import PIL.Image
from autogen_core import Image as AGImage
import asyncio
from autogen_core import (
    CancellationToken,
    DefaultTopicId,
    MessageContext,
    event,
    rpc,
    AgentId,
)
from autogen_core.models import (
    ChatCompletionClient,
    LLMMessage,
    SystemMessage,
    UserMessage,
)
from autogen_core.model_context import TokenLimitedChatCompletionContext
from autogen_agentchat.base import Response, TerminationCondition
from autogen_agentchat.messages import (
    BaseChatMessage,
    StopMessage,
    TextMessage,
    MultiModalMessage,
    BaseAgentEvent,
    MessageFactory,
)
from autogen_agentchat.teams._group_chat._events import (
    GroupChatAgentResponse,
    GroupChatMessage,
    GroupChatRequestPublish,
    GroupChatStart,
    GroupChatTermination,
)
from autogen_agentchat.teams._group_chat._base_group_chat_manager import (
    BaseGroupChatManager,
)
from autogen_agentchat.state import BaseGroupChatManagerState
from ...learning.memory_provider import MemoryControllerProvider

from ...types import HumanInputFormat, Plan, SentinelPlanStep
from ...utils import dict_to_str, thread_to_context
from ...tools.bing_search import get_bing_search_results
from ...teams.orchestrator.orchestrator_config import OrchestratorConfig
from ._prompts import (
    get_orchestrator_system_message_planning,
    get_orchestrator_system_message_planning_autonomous,
    get_orchestrator_plan_prompt_json,
    get_orchestrator_plan_replan_json,
    get_orchestrator_progress_ledger_prompt,
    ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION,
    ORCHESTRATOR_FINAL_ANSWER_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_FULL_FORMAT,
    INSTRUCTION_AGENT_FORMAT,
    validate_ledger_json,
    validate_plan_json,
)
from ._sentinel_prompts import (
    ORCHESTRATOR_SENTINEL_CONDITION_CHECK_PROMPT,
    validate_sentinel_condition_check_json,
)
from ._utils import is_accepted_str, extract_json_from_string
from loguru import logger as trace_logger


class OrchestratorState(BaseGroupChatManagerState):
    """
    The OrchestratorState class is responsible for maintaining the state of the group chat conversation.
    """

    task: str = ""
    plan_str: str = ""
    plan: Plan | None = None
    n_rounds: int = 0
    current_step_idx: int = 0
    information_collected: str = ""
    in_planning_mode: bool = True
    is_paused: bool = False
    group_topic_type: str = ""
    message_history: List[BaseChatMessage | BaseAgentEvent] = []
    participant_topic_types: List[str] = []
    n_replans: int = 0

    def reset(self) -> None:
        self.task = ""
        self.plan_str = ""
        self.plan = None
        self.n_rounds = 0
        self.current_step_idx = 0
        self.information_collected = ""
        self.in_planning_mode = True
        self.message_history = []
        self.is_paused = False
        self.n_replans = 0

    # resets most of the orchestrator's state but keeps message history
    # to allow for follow up questions
    def reset_for_followup(self) -> None:
        self.task = ""
        self.plan_str = ""
        self.plan = None
        self.n_rounds = 0
        self.current_step_idx = 0
        self.in_planning_mode = True
        self.is_paused = False
        self.n_replans = 0


class Orchestrator(BaseGroupChatManager):
    """
    The Orchestrator class is responsible for managing a group chat by orchestrating the conversation
    between multiple participants. It extends the SequentialRoutedAgent class and provides functionality
    to handle the start, reset, and progression of the group chat.

    The orchestrator maintains the state of the conversation, including the task, plan, and progress. It
    interacts with a model client to generate and validate plans, and it publishes messages to the group
    chat based on the current state and responses from participants.

    """

    def __init__(
        self,
        name: str,
        group_topic_type: str,
        output_topic_type: str,
        message_factory: MessageFactory,
        participant_topic_types: List[str],
        participant_descriptions: List[str],
        participant_names: List[str],
        output_message_queue: asyncio.Queue[
            BaseAgentEvent | BaseChatMessage | GroupChatTermination
        ],
        model_client: ChatCompletionClient,
        config: OrchestratorConfig,
        termination_condition: TerminationCondition | None = None,
        max_turns: int | None = None,
        memory_provider: MemoryControllerProvider | None = None,
    ):
        super().__init__(
            name,
            group_topic_type,
            output_topic_type,
            participant_topic_types,
            participant_names,
            participant_descriptions,
            output_message_queue,
            termination_condition,
            max_turns,
            message_factory=message_factory,
        )
        self._model_client: ChatCompletionClient = model_client
        self._model_context = TokenLimitedChatCompletionContext(
            model_client, token_limit=config.model_context_token_limit
        )
        self._config: OrchestratorConfig = config
        self._user_agent_topic = "user_proxy"
        self._web_agent_topic = "web_surfer"
        if self._user_agent_topic not in self._participant_names:
            if not (
                self._config.autonomous_execution
                and not self._config.allow_follow_up_input
            ):
                raise ValueError(
                    f"User agent topic {self._user_agent_topic} not in participant names {self._participant_names}"
                )

        self._memory_controller = None
        self._memory_provider = memory_provider
        if (
            self._config.memory_controller_key
            and self._model_client
            and self._memory_provider is not None
            and self._config.retrieve_relevant_plans in ["hint", "reuse"]
        ):
            try:
                provider = self._memory_provider
                self._memory_controller = provider.get_memory_controller(
                    memory_controller_key=self._config.memory_controller_key,
                    client=self._model_client,
                )
                trace_logger.info("Memory controller initialized successfully.")
            except Exception as e:
                trace_logger.warning(f"Failed to initialize memory controller: {e}")

        # Setup internal variables
        self._setup_internals()

        # Pause monitoring for sentinel steps
        self._pause_event = asyncio.Event()

    def _setup_internals(self) -> None:
        """
        Setup internal variables used in orchestrator
        """
        self._state: OrchestratorState = OrchestratorState()

        # Create filtered lists for execution that may exclude the user agent
        self._agent_execution_names = self._participant_names.copy()
        self._agent_execution_descriptions = self._participant_descriptions.copy()

        if self._config.autonomous_execution:
            # Filter out the user agent from execution lists
            user_indices = [
                i
                for i, name in enumerate(self._agent_execution_names)
                if name == self._user_agent_topic
            ]
            if user_indices:
                user_index = user_indices[0]
                self._agent_execution_names.pop(user_index)
                self._agent_execution_descriptions.pop(user_index)
        # add a a new participant for the orchestrator to do nothing
        self._agent_execution_names.append("no_action_agent")
        self._agent_execution_descriptions.append(
            "If for this step no action is needed, you can use this agent to perform no action"
        )

        self._team_description: str = "\n".join(
            [
                f"{topic_type}: {description}".strip()
                for topic_type, description in zip(
                    self._agent_execution_names,
                    self._agent_execution_descriptions,
                    strict=True,
                )
            ]
        )
        self._last_browser_metadata_hash = ""

    def _get_system_message_planning(
        self,
    ) -> str:
        date_today = datetime.now().strftime("%Y-%m-%d")
        if self._config.autonomous_execution:
            return get_orchestrator_system_message_planning_autonomous(
                self._config.sentinel_plan.enable_sentinel_steps
            ).format(
                date_today=date_today,
                team=self._team_description,
            )
        else:
            return get_orchestrator_system_message_planning(
                self._config.sentinel_plan.enable_sentinel_steps
            ).format(
                date_today=date_today,
                team=self._team_description,
            )

    def _get_task_ledger_plan_prompt(self, team: str) -> str:
        additional_instructions = ""
        if self._config.allowed_websites is not None:
            additional_instructions = (
                "Only use the following websites if possible: "
                + ", ".join(self._config.allowed_websites)
            )

        return get_orchestrator_plan_prompt_json(
            self._config.sentinel_plan.enable_sentinel_steps
        ).format(team=team, additional_instructions=additional_instructions)

    def _get_task_ledger_replan_plan_prompt(
        self, task: str, team: str, plan: str
    ) -> str:
        additional_instructions = ""
        if self._config.allowed_websites is not None:
            additional_instructions = (
                "Only use the following websites if possible: "
                + ", ".join(self._config.allowed_websites)
            )
        return get_orchestrator_plan_replan_json(
            self._config.sentinel_plan.enable_sentinel_steps
        ).format(
            task=task,
            team=team,
            plan=plan,
            additional_instructions=additional_instructions,
        )

    def _get_task_ledger_full_prompt(self, task: str, team: str, plan: str) -> str:
        return ORCHESTRATOR_TASK_LEDGER_FULL_FORMAT.format(
            task=task, team=team, plan=plan
        )

    def _get_progress_ledger_prompt(
        self, task: str, plan: str, step_index: int, team: str, names: List[str]
    ) -> str:
        assert self._state.plan is not None
        additional_instructions = ""
        if self._config.autonomous_execution:
            additional_instructions = "VERY IMPORTANT: The next agent name cannot be the user or user_proxy, use any other agent."

        # Determine step_type based on the current step
        step_type = "PlanStep"
        if self._config.sentinel_plan.enable_sentinel_steps and isinstance(
            self._state.plan[step_index], SentinelPlanStep
        ):
            step_type = "SentinelPlanStep"

        return get_orchestrator_progress_ledger_prompt(
            self._config.sentinel_plan.enable_sentinel_steps
        ).format(
            task=task,
            plan=plan,
            step_index=step_index,
            step_title=self._state.plan[step_index].title,
            step_details=self._state.plan[step_index].details,
            step_type=step_type,
            agent_name=self._state.plan[step_index].agent_name,
            team=team,
            names=", ".join(names),
            additional_instructions=additional_instructions,
        )

    def _get_final_answer_prompt(self, task: str) -> str:
        if self._config.final_answer_prompt is not None:
            return self._config.final_answer_prompt.format(task=task)
        else:
            return ORCHESTRATOR_FINAL_ANSWER_PROMPT.format(task=task)

    def get_agent_instruction(self, instruction: str, agent_name: str) -> str:
        assert self._state.plan is not None

        return INSTRUCTION_AGENT_FORMAT.format(
            step_index=self._state.current_step_idx + 1,
            step_title=self._state.plan[self._state.current_step_idx].title,
            step_details=self._state.plan[self._state.current_step_idx].details,
            agent_name=agent_name,
            instruction=instruction,
        )

    def _validate_ledger_json(self, json_response: Dict[str, Any]) -> bool:
        return validate_ledger_json(json_response, self._agent_execution_names)

    def _validate_plan_json(self, json_response: Dict[str, Any]) -> bool:
        return validate_plan_json(
            json_response, self._config.sentinel_plan.enable_sentinel_steps
        )

    async def validate_group_state(
        self, messages: List[BaseChatMessage] | None
    ) -> None:
        pass

    async def select_speaker(
        self, thread: List[BaseAgentEvent | BaseChatMessage]
    ) -> str:
        """Not used in this class."""
        return ""

    async def reset(self) -> None:
        """Reset the group chat manager."""
        if self._termination_condition is not None:
            await self._termination_condition.reset()
        self._state.reset()

    async def _log_message(self, log_message: str) -> None:
        trace_logger.debug(log_message)

    async def _log_message_agentchat(
        self,
        content: str,
        internal: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        entire_message: Optional[BaseChatMessage] = None,
    ) -> None:
        if entire_message is not None:
            await self.publish_message(
                GroupChatMessage(message=entire_message),
                topic_id=DefaultTopicId(type=self._output_topic_type),
            )
            await self._output_message_queue.put(entire_message)
            return
        internal_str = "yes" if internal else "no"
        message = TextMessage(
            content=content,
            source=self._name,
            metadata=metadata or {"internal": internal_str},
        )

        await self.publish_message(
            GroupChatMessage(message=message),
            topic_id=DefaultTopicId(type=self._output_topic_type),
        )
        await self._output_message_queue.put(message)

    async def _publish_group_chat_message(
        self,
        content: str,
        cancellation_token: CancellationToken,
        internal: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Helper function to publish a group chat message."""
        internal_str = "yes" if internal else "no"
        message = TextMessage(
            content=content,
            source=self._name,
            metadata=metadata or {"internal": internal_str},
        )

        await self.publish_message(
            GroupChatMessage(message=message),
            topic_id=DefaultTopicId(type=self._output_topic_type),
        )

        await self._output_message_queue.put(message)

        await self.publish_message(
            GroupChatAgentResponse(agent_response=Response(chat_message=message)),
            topic_id=DefaultTopicId(type=self._group_topic_type),
            cancellation_token=cancellation_token,
        )

    async def _request_next_speaker(
        self, next_speaker: str, cancellation_token: CancellationToken
    ) -> None:
        """Helper function to request the next speaker."""
        if next_speaker == "no_action_agent":
            await self._orchestrate_step(cancellation_token)
            return

        next_speaker_topic_type = self._participant_name_to_topic_type[next_speaker]

        await self.publish_message(
            GroupChatRequestPublish(),
            topic_id=DefaultTopicId(type=next_speaker_topic_type),
            cancellation_token=cancellation_token,
        )

    async def _get_json_response(
        self,
        messages: List[LLMMessage],
        validate_json: Callable[[Dict[str, Any]], bool],
        cancellation_token: CancellationToken,
    ) -> Dict[str, Any] | None:
        """Get a JSON response from the model client.
        Args:
            messages (List[LLMMessage]): The messages to send to the model client.
            validate_json (callable): A function to validate the JSON response. The function should return True if the JSON response is valid, otherwise False.
            cancellation_token (CancellationToken): A token to cancel the request if needed.
        """
        retries = 0
        exception_message = ""
        response_content = "[NOT SET]"

        try:
            while retries < self._config.max_json_retries:
                # Check for pause before each retry
                if self._state.is_paused:
                    await self._log_message_agentchat(
                        "LLM request paused during JSON response retrieval.",
                        internal=True,
                    )
                    raise ValueError("Operation paused")

                # Re-initialize model context to meet token limit quota
                await self._model_context.clear()
                for msg in messages:
                    await self._model_context.add_message(msg)
                if exception_message != "":
                    await self._model_context.add_message(
                        UserMessage(content=exception_message, source=self._name)
                    )
                token_limited_messages = await self._model_context.get_messages()
                response = await self._model_client.create(
                    token_limited_messages,
                    json_output=True
                    if self._model_client.model_info["json_output"]
                    else False,
                    cancellation_token=cancellation_token,
                )
                assert isinstance(response.content, str)
                response_content = response.content
                try:
                    json_response = json.loads(response.content)
                    # Use the validate_json function to check the response
                    if validate_json(json_response):
                        return json_response
                    else:
                        exception_message = "Validation failed for JSON response, retrying. You must return a valid JSON object parsed from the response."
                        await self._log_message(
                            f"Validation failed for JSON response: {json_response}, retrying ({retries}/{self._config.max_json_retries})"
                        )
                except json.JSONDecodeError as e:
                    json_response = extract_json_from_string(response.content)
                    if json_response is not None:
                        if validate_json(json_response):
                            return json_response
                        else:
                            exception_message = "Validation failed for JSON response, retrying. You must return a valid JSON object parsed from the response."
                    else:
                        exception_message = f"Failed to parse JSON response, retrying. You must return a valid JSON object parsed from the response. Error: {e}"
                    await self._log_message(
                        f"Failed to parse JSON response, retrying ({retries}/{self._config.max_json_retries})"
                    )
                retries += 1
            await self._log_message_agentchat(
                f"Failed to get a valid JSON response after multiple retries {retries}, last error: {exception_message} and response: {response_content}",
                internal=False,
            )
            raise ValueError(
                f"Failed to get a valid JSON response after multiple retries {retries}, last error: {exception_message} and response: {response_content}"
            )
        except Exception as e:
            await self._log_message_agentchat(
                f"Error in Orchestrator: {e}", internal=False
            )
            raise

    @rpc
    async def handle_start(self, message: GroupChatStart, ctx: MessageContext) -> None:  # type: ignore
        """Handle the start of a group chat by selecting a speaker to start the conversation."""
        # Check if the conversation has already terminated.
        if (
            self._termination_condition is not None
            and self._termination_condition.terminated
        ):
            early_stop_message = StopMessage(
                content="The group chat has already terminated.", source=self._name
            )
            await self._signal_termination(early_stop_message)

            # Stop the group chat.
            return
        assert message is not None and message.messages is not None

        # send message to all agents with initial user message
        await self.publish_message(
            GroupChatStart(messages=message.messages),
            topic_id=DefaultTopicId(type=self._group_topic_type),
            cancellation_token=ctx.cancellation_token,
        )

        # handle agent response
        for m in message.messages:
            self._state.message_history.append(m)
        await self._orchestrate_step(ctx.cancellation_token)

    async def pause(self) -> None:
        """Pause the group chat manager."""
        self._state.is_paused = True
        self._pause_event.set()

    async def resume(self) -> None:
        """Resume the group chat manager."""
        self._state.is_paused = False
        self._pause_event.clear()

    @event
    async def handle_agent_response(  # type: ignore
        self, message: GroupChatAgentResponse, ctx: MessageContext
    ) -> None:
        delta: List[BaseChatMessage] = []
        if message.agent_response.inner_messages is not None:
            for inner_message in message.agent_response.inner_messages:
                delta.append(inner_message)  # type: ignore
        self._state.message_history.append(message.agent_response.chat_message)
        delta.append(message.agent_response.chat_message)

        if self._termination_condition is not None:
            stop_message = await self._termination_condition(delta)
            if stop_message is not None:
                await self._prepare_final_answer(
                    reason="Termination Condition Met.",
                    cancellation_token=ctx.cancellation_token,
                    force_stop=True,
                )
                await self._signal_termination(stop_message)
                # Stop the group chat and reset the termination conditions and turn count.
                await self._termination_condition.reset()
                return
        await self._orchestrate_step(ctx.cancellation_token)

    async def _orchestrate_step(self, cancellation_token: CancellationToken) -> None:
        """Orchestrate the next step of the conversation."""
        if self._state.is_paused:
            # let user speak next if paused
            await self._request_next_speaker(self._user_agent_topic, cancellation_token)
            return

        if self._state.in_planning_mode:
            await self._orchestrate_step_planning(cancellation_token)
        else:
            await self._orchestrate_step_execution(cancellation_token)

    async def do_bing_search(self, query: str) -> str | None:
        try:
            # log the bing search request
            await self._log_message_agentchat(
                "Searching online for information...",
                metadata={"internal": "no", "type": "progress_message"},
            )
            bing_search_results = await get_bing_search_results(
                query,
                max_pages=3,
                max_tokens_per_page=5000,
                timeout_seconds=35,
            )
            if bing_search_results.combined_content != "":
                bing_results_progress = f"Reading through {len(bing_search_results.page_contents)} web pages..."
                await self._log_message_agentchat(
                    bing_results_progress,
                    metadata={"internal": "no", "type": "progress_message"},
                )
                return bing_search_results.combined_content
            return None
        except Exception as e:
            trace_logger.exception(f"Error in doing bing search: {e}")
            return None

    async def _get_websurfer_page_info(self) -> None:
        """Get the page information from the web surfer agent."""
        try:
            if self._web_agent_topic in self._participant_names:
                web_surfer_container = (
                    await self._runtime.try_get_underlying_agent_instance(
                        AgentId(
                            type=self._participant_name_to_topic_type[
                                self._web_agent_topic
                            ],
                            key=self.id.key,
                        )
                    )
                )
                if (
                    web_surfer_container._agent is not None  # type: ignore
                ):
                    web_surfer = web_surfer_container._agent  # type: ignore
                    page_title: str | None = None
                    page_url: str | None = None
                    (page_title, page_url) = await web_surfer.get_page_title_url()  # type: ignore
                    assert page_title is not None
                    assert page_url is not None

                    num_tabs, tabs_information_str = await web_surfer.get_tabs_info()  # type: ignore
                    tabs_information_str = f"There are {num_tabs} tabs open. The tabs are as follows:\n{tabs_information_str}"

                    message = MultiModalMessage(
                        content=[tabs_information_str],
                        source="web_surfer",
                    )
                    if "about:blank" not in page_url:
                        page_description: str | None = None
                        screenshot: bytes | None = None
                        metadata_hash: str | None = None
                        (
                            page_description,  # type: ignore
                            screenshot,  # type: ignore
                            metadata_hash,  # type: ignore
                        ) = await web_surfer.describe_current_page()  # type: ignore
                        assert isinstance(screenshot, bytes)
                        assert isinstance(page_description, str)
                        assert isinstance(metadata_hash, str)
                        if metadata_hash != self._last_browser_metadata_hash:
                            page_description = (
                                "A description of the current page: " + page_description
                            )
                            self._last_browser_metadata_hash: str = metadata_hash

                            message.content.append(page_description)
                            message.content.append(
                                AGImage.from_pil(PIL.Image.open(io.BytesIO(screenshot)))
                            )
                    self._state.message_history.append(message)
        except Exception as e:
            trace_logger.exception(f"Error in getting web surfer screenshot: {e}")
            pass

    async def _handle_relevant_plan_from_memory(
        self,
        context: Optional[List[LLMMessage]] = None,
    ) -> Optional[Any]:
        """
        Handles retrieval of relevant plans from memory for 'reuse' or 'hint' modes.
        Returns:
            For 'reuse', returns the most relevant plan (or None).
            For 'hint', appends a relevant plan as a UserMessage to the context if found.
        """
        if not self._memory_controller:
            return None
        try:
            mode = self._config.retrieve_relevant_plans
            task = self._state.task
            source = self._name
            trace_logger.info(
                f"retrieving relevant plan from memory for mode: {mode} ..."
            )
            memos = await self._memory_controller.retrieve_relevant_memos(task=task)
            trace_logger.info(f"{len(memos)} relevant plan(s) retrieved from memory")
            if len(memos) > 0:
                most_relevant_plan = memos[0].insight
                if mode == "reuse":
                    return most_relevant_plan
                elif mode == "hint" and context is not None:
                    context.append(
                        UserMessage(
                            content="Relevant plan:\n " + most_relevant_plan,
                            source=source,
                        )
                    )
        except Exception as e:
            trace_logger.error(f"Error retrieving plans from memory: {e}")
        return None

    async def _orchestrate_step_planning(
        self, cancellation_token: CancellationToken
    ) -> None:
        # Planning stage
        plan_response: Dict[str, Any] | None = None
        last_user_message = self._state.message_history[-1]
        assert last_user_message.source in [self._user_agent_topic, "user"]
        message_content: str = ""
        assert isinstance(last_user_message, TextMessage | MultiModalMessage)

        if isinstance(last_user_message.content, list):
            # iterate over the list and get the first item that is a string
            for item in last_user_message.content:
                if isinstance(item, str):
                    message_content = item
                    break
        else:
            message_content = last_user_message.content
        last_user_message = HumanInputFormat.from_str(message_content)

        # Is this our first time planning?
        if self._state.task == "" and self._state.plan_str == "":
            self._state.task = "TASK: " + last_user_message.content

            # TCM reuse plan
            from_memory = False
            if (
                not self._config.plan
                and self._config.retrieve_relevant_plans == "reuse"
            ):
                most_relevant_plan = await self._handle_relevant_plan_from_memory()
                if most_relevant_plan is not None:
                    self._config.plan = Plan.from_list_of_dicts_or_str(
                        most_relevant_plan
                    )
                    from_memory = True
            # Do we already have a plan to follow and planning mode is disabled?
            if self._config.plan is not None:
                self._state.plan = self._config.plan
                self._state.plan_str = str(self._config.plan)
                self._state.message_history.append(
                    TextMessage(
                        content="Initial plan from user:\n " + str(self._config.plan),
                        source="user",
                    )
                )
                plan_response = {
                    "task": self._state.plan.task,
                    "steps": [step.model_dump() for step in self._state.plan.steps],
                    "needs_plan": True,
                    "response": "",
                    "plan_summary": self._state.plan.task,
                    "from_memory": from_memory,
                }

                await self._log_message_agentchat(
                    dict_to_str(plan_response),
                    metadata={"internal": "no", "type": "plan_message"},
                )

                if not self._config.cooperative_planning:
                    self._state.in_planning_mode = False
                    await self._orchestrate_step_execution(
                        cancellation_token, first_step=True
                    )
                    return
                else:
                    await self._request_next_speaker(
                        self._user_agent_topic, cancellation_token
                    )
                    return
            # Did the user provide a plan?
            user_plan = last_user_message.plan
            if user_plan is not None:
                self._state.plan = user_plan
                self._state.plan_str = str(user_plan)
                if last_user_message.accepted or is_accepted_str(
                    last_user_message.content
                ):
                    self._state.in_planning_mode = False
                    await self._orchestrate_step_execution(
                        cancellation_token, first_step=True
                    )
                    return

            # assume the task is the last user message
            context = self._thread_to_context()
            # if bing search is enabled, do a bing search to help with planning
            if self._config.do_bing_search:
                bing_search_results = await self.do_bing_search(
                    last_user_message.content
                )
                if bing_search_results is not None:
                    context.append(
                        UserMessage(
                            content=bing_search_results,
                            source="web_surfer",
                        )
                    )

            if self._config.retrieve_relevant_plans == "hint":
                await self._handle_relevant_plan_from_memory(context=context)

            # create a first plan
            context.append(
                UserMessage(
                    content=self._get_task_ledger_plan_prompt(self._team_description),
                    source=self._name,
                )
            )
            plan_response = await self._get_json_response(
                context, self._validate_plan_json, cancellation_token
            )
            if self._state.is_paused:
                # let user speak next if paused
                await self._request_next_speaker(
                    self._user_agent_topic, cancellation_token
                )
                return
            assert plan_response is not None
            self._state.plan = Plan.from_list_of_dicts_or_str(plan_response["steps"])
            self._state.plan_str = str(self._state.plan)
            # add plan_response to the message thread
            self._state.message_history.append(
                TextMessage(
                    content=json.dumps(plan_response, indent=4), source=self._name
                )
            )
        else:
            # what did the user say?
            # Check if user accepted the plan
            if last_user_message.accepted or is_accepted_str(last_user_message.content):
                user_plan = last_user_message.plan
                if user_plan is not None:
                    self._state.plan = user_plan
                    self._state.plan_str = str(user_plan)
                # switch to execution mode
                self._state.in_planning_mode = False
                await self._orchestrate_step_execution(
                    cancellation_token, first_step=True
                )
                return
            # user did not accept the plan yet
            else:
                # update the plan
                user_plan = last_user_message.plan
                if user_plan is not None:
                    self._state.plan = user_plan
                    self._state.plan_str = str(user_plan)

                context = self._thread_to_context()

                # if bing search is enabled, do a bing search to help with planning
                if self._config.do_bing_search:
                    bing_search_results = await self.do_bing_search(
                        last_user_message.content
                    )
                    if bing_search_results is not None:
                        context.append(
                            UserMessage(
                                content=bing_search_results,
                                source="web_surfer",
                            )
                        )
                if self._config.retrieve_relevant_plans == "hint":
                    await self._handle_relevant_plan_from_memory(context=context)
                context.append(
                    UserMessage(
                        content=self._get_task_ledger_plan_prompt(
                            self._team_description
                        ),
                        source=self._name,
                    )
                )
                plan_response = await self._get_json_response(
                    context, self._validate_plan_json, cancellation_token
                )
                if self._state.is_paused:
                    # let user speak next if paused
                    await self._request_next_speaker(
                        self._user_agent_topic, cancellation_token
                    )
                    return
                assert plan_response is not None
                self._state.plan = Plan.from_list_of_dicts_or_str(
                    plan_response["steps"]
                )
                self._state.plan_str = str(self._state.plan)
                if not self._config.no_overwrite_of_task:
                    self._state.task = plan_response["task"]
                # add plan_response to the message thread
                self._state.message_history.append(
                    TextMessage(
                        content=json.dumps(plan_response, indent=4), source=self._name
                    )
                )

        assert plan_response is not None
        # if we don't need to plan, just send the message
        if self._config.cooperative_planning:
            if not plan_response["needs_plan"]:
                # send the response plan_message["response"] to the group
                await self._publish_group_chat_message(
                    plan_response["response"], cancellation_token
                )
                await self._request_next_speaker(
                    self._user_agent_topic, cancellation_token
                )
                return
            else:
                await self._publish_group_chat_message(
                    dict_to_str(plan_response),
                    cancellation_token,
                    metadata={"internal": "no", "type": "plan_message"},
                )
                await self._request_next_speaker(
                    self._user_agent_topic, cancellation_token
                )
                return
        else:
            await self._publish_group_chat_message(
                dict_to_str(plan_response),
                metadata={"internal": "no", "type": "plan_message"},
                cancellation_token=cancellation_token,
            )
            self._state.in_planning_mode = False
            await self._orchestrate_step_execution(cancellation_token, first_step=True)

    async def _orchestrate_step_execution(
        self, cancellation_token: CancellationToken, first_step: bool = False
    ) -> None:
        # Execution stage
        if first_step:
            # remove all messages from the message thread that are not from the user
            self._state.message_history = [
                m
                for m in self._state.message_history
                if m.source not in ["user", self._user_agent_topic]
            ]

            ledger_message = TextMessage(
                content=self._get_task_ledger_full_prompt(
                    self._state.task, self._team_description, self._state.plan_str
                ),
                source=self._name,
            )
            # add the ledger message to the message thread internally
            self._state.message_history.append(ledger_message)
            await self._log_message_agentchat(ledger_message.content, internal=True)

        assert self._state.plan is not None
        if self._state.current_step_idx >= len(self._state.plan) or (
            self._config.max_turns is not None
            and self._state.n_rounds > self._config.max_turns
        ):
            await self._prepare_final_answer("Max rounds reached.", cancellation_token)
            return

        self._state.n_rounds += 1
        context = self._thread_to_context()
        # Update the progress ledger

        progress_ledger_prompt = self._get_progress_ledger_prompt(
            self._state.task,
            self._state.plan_str,
            self._state.current_step_idx,
            self._team_description,
            self._agent_execution_names,
        )

        context.append(UserMessage(content=progress_ledger_prompt, source=self._name))

        progress_ledger = await self._get_json_response(
            context, self._validate_ledger_json, cancellation_token
        )
        if self._state.is_paused:
            await self._request_next_speaker(self._user_agent_topic, cancellation_token)
            return
        assert progress_ledger is not None
        # log the progress ledger
        await self._log_message_agentchat(dict_to_str(progress_ledger), internal=True)
        if not first_step:
            # Check for replans
            need_to_replan = progress_ledger["need_to_replan"]["answer"]
            replan_reason = progress_ledger["need_to_replan"]["reason"]

            if need_to_replan and self._config.allow_for_replans:
                # Replan
                if self._config.max_replans is None:
                    await self._replan(replan_reason, cancellation_token)
                elif self._state.n_replans < self._config.max_replans:
                    self._state.n_replans += 1
                    await self._replan(replan_reason, cancellation_token)
                    return
                else:
                    await self._prepare_final_answer(
                        f"We need to replan but max replan attempts reached: {replan_reason}.",
                        cancellation_token,
                    )
                    return
            elif need_to_replan:
                await self._prepare_final_answer(
                    f"The current plan failed to complete the task, we need a new plan to continue. {replan_reason}",
                    cancellation_token,
                )
                return
            if progress_ledger["is_current_step_complete"]["answer"]:
                self._state.current_step_idx += 1

        if progress_ledger["progress_summary"] != "":
            self._state.information_collected += (
                "\n" + progress_ledger["progress_summary"]
            )
        # Check for plan completion
        if self._state.current_step_idx >= len(self._state.plan):
            await self._prepare_final_answer(
                "Plan completed.",
                cancellation_token,
            )
            return

        current_step = self._state.plan[self._state.current_step_idx]
        is_sentinel_step = (
            isinstance(current_step, SentinelPlanStep)
            and self._config.sentinel_plan.enable_sentinel_steps
        )

        # Broadcast the next step
        if not is_sentinel_step:
            new_instruction = self.get_agent_instruction(
                progress_ledger["instruction_or_question"]["answer"],
                progress_ledger["instruction_or_question"]["agent_name"],
            )
            message_to_send = TextMessage(
                content=new_instruction, source=self._name, metadata={"internal": "yes"}
            )
            self._state.message_history.append(message_to_send)  # My copy

            await self._publish_group_chat_message(
                message_to_send.content, cancellation_token, internal=True
            )
        json_step_execution = {
            "title": self._state.plan[self._state.current_step_idx].title,
            "index": self._state.current_step_idx,
            "details": self._state.plan[self._state.current_step_idx].details,
            "agent_name": progress_ledger["instruction_or_question"]["agent_name"],
            "instruction": progress_ledger["instruction_or_question"]["answer"],
            "progress_summary": progress_ledger["progress_summary"],
            "plan_length": len(self._state.plan),
        }
        await self._log_message_agentchat(
            json.dumps(json_step_execution),
            metadata={"internal": "no", "type": "step_execution"},
        )

        # Request that the step be completed
        if not is_sentinel_step:
            valid_next_speaker: bool = False
            next_speaker = progress_ledger["instruction_or_question"]["agent_name"]
            for participant_name in self._agent_execution_names:
                if participant_name == next_speaker:
                    await self._request_next_speaker(next_speaker, cancellation_token)
                    valid_next_speaker = True
                    break
            if not valid_next_speaker:
                raise ValueError(
                    f"Invalid next speaker: {next_speaker} from the ledger, participants are: {self._agent_execution_names}"
                )
        else:
            assert isinstance(current_step, SentinelPlanStep)
            # Generate sentinel ID once
            sentinel_step_id = (
                f"sentinel_{self._state.current_step_idx}_{datetime.now().isoformat()}"
            )

            # Send sentinel start message with step metadata
            sentinel_start_metadata = {
                "internal": "no",
                "type": "sentinel_start",
                "sentinel_id": sentinel_step_id,
                "step_title": current_step.title,
                "step_details": current_step.details,
                "condition": str(current_step.condition),
                "sleep_duration": str(current_step.sleep_duration),
            }
            await self._log_message_agentchat(
                json.dumps(
                    {
                        "title": current_step.title,
                        "details": current_step.details,
                        "condition": current_step.condition,
                        "sleep_duration": current_step.sleep_duration,
                    }
                ),
                metadata=sentinel_start_metadata,
            )
            sentinel_completed = await self._execute_sentinel_step(
                current_step, progress_ledger, cancellation_token, sentinel_step_id
            )
            if sentinel_completed:
                # sentinel step is completed, move to the next step
                self._state.current_step_idx += 1  # moves to the next step
            await self._orchestrate_step(cancellation_token)

    async def _replan(self, reason: str, cancellation_token: CancellationToken) -> None:
        # Let's create a new plan
        self._state.in_planning_mode = True
        await self._log_message_agentchat(
            f"We need to create a new plan. {reason}",
            metadata={"internal": "no", "type": "replanning"},
        )
        context = self._thread_to_context()

        # Store completed steps
        completed_steps = (
            list(self._state.plan.steps[: self._state.current_step_idx])
            if self._state.plan
            else []
        )
        completed_plan_str = "\n".join(
            [
                f"COMPLETED STEP {i + 1}: {step}"
                for i, step in enumerate(completed_steps)
            ]
        )

        # Add completed steps info to replan prompt
        replan_prompt = self._get_task_ledger_replan_plan_prompt(
            self._state.task,
            self._team_description,
            f"Completed steps so far:\n{completed_plan_str}\n\nPrevious plan:\n{self._state.plan_str}",
        )
        context.append(
            UserMessage(
                content=replan_prompt,
                source=self._name,
            )
        )
        plan_response = await self._get_json_response(
            context, self._validate_plan_json, cancellation_token
        )
        assert plan_response is not None

        # Create new plan by combining completed steps with new steps
        new_plan = Plan.from_list_of_dicts_or_str(plan_response["steps"])
        if new_plan is not None:
            combined_steps = completed_steps + list(new_plan.steps)
            self._state.plan = Plan(task=self._state.task, steps=combined_steps)
            self._state.plan_str = str(self._state.plan)
        else:
            # If new plan is None (empty steps), check if we have any completed steps
            if len(completed_steps) > 0:
                # Keep the completed steps if we have any
                self._state.plan = Plan(task=self._state.task, steps=completed_steps)
                self._state.plan_str = str(self._state.plan)
            else:
                # Both completed_steps and new steps are empty - this indicates task completion
                await self._prepare_final_answer(
                    f"Replanning resulted in no additional steps needed. Task appears to be complete. Reason: {reason}",
                    cancellation_token,
                )
                return

        # Update task if in planning mode
        if not self._config.no_overwrite_of_task:
            self._state.task = plan_response["task"]

        plan_response["plan_summary"] = "Replanning: " + plan_response["plan_summary"]
        # Log the plan response in the same format as planning mode
        await self._publish_group_chat_message(
            dict_to_str(plan_response),
            cancellation_token=cancellation_token,
            metadata={"internal": "no", "type": "plan_message"},
        )
        # next speaker is user
        if self._config.cooperative_planning:
            await self._request_next_speaker(self._user_agent_topic, cancellation_token)
        else:
            self._state.in_planning_mode = False
            await self._orchestrate_step_execution(cancellation_token, first_step=True)

    async def _prepare_final_answer(
        self,
        reason: str,
        cancellation_token: CancellationToken,
        final_answer: str | None = None,
        force_stop: bool = False,
    ) -> None:
        """Prepare the final answer for the task.

        Args:
            reason (str): The reason for preparing the final answer
            cancellation_token (CancellationToken): Token for cancellation
            final_answer (str, optional): Optional pre-computed final answer to use instead of computing one
            force_stop (bool): Whether to force stop the conversation after the final answer is computed
        """
        if final_answer is None:
            context = self._thread_to_context()
            # add replan reason
            context.append(UserMessage(content=reason, source=self._name))
            # Get the final answer
            final_answer_prompt = self._get_final_answer_prompt(self._state.task)
            progress_summary = f"Progress Summary:\n{self._state.information_collected}"
            context.append(
                UserMessage(
                    content=progress_summary + "\n\n" + final_answer_prompt,
                    source=self._name,
                )
            )

            # Re-initialize model context to meet token limit quota
            await self._model_context.clear()
            for msg in context:
                await self._model_context.add_message(msg)
            token_limited_context = await self._model_context.get_messages()

            response = await self._model_client.create(
                token_limited_context, cancellation_token=cancellation_token
            )
            assert isinstance(response.content, str)
            final_answer = response.content

        message = TextMessage(
            content=f"Final Answer: {final_answer}", source=self._name
        )

        self._state.message_history.append(message)  # My copy

        await self._publish_group_chat_message(
            message.content,
            cancellation_token,
            metadata={"internal": "no", "type": "final_answer"},
        )

        # reset internals except message history
        self._state.reset_for_followup()
        if not force_stop and self._config.allow_follow_up_input:
            await self._request_next_speaker(self._user_agent_topic, cancellation_token)
        else:
            # Signal termination
            await self._signal_termination(
                StopMessage(content=reason, source=self._name)
            )

        if self._termination_condition is not None:
            await self._termination_condition.reset()

    def _thread_to_context(
        self, messages: Optional[List[BaseChatMessage | BaseAgentEvent]] = None
    ) -> List[LLMMessage]:
        """Convert the message thread to a context for the model."""
        chat_messages: List[BaseChatMessage | BaseAgentEvent] = (
            messages if messages is not None else self._state.message_history
        )
        context_messages: List[LLMMessage] = []
        date_today = datetime.now().strftime("%d %B, %Y")

        if self._state.in_planning_mode:
            context_messages.append(
                SystemMessage(content=self._get_system_message_planning())
            )
        else:
            context_messages.append(
                SystemMessage(
                    content=ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION.format(
                        date_today=date_today
                    )
                )
            )
        if self._model_client.model_info["vision"]:
            context_messages.extend(
                thread_to_context(
                    messages=chat_messages, agent_name=self._name, is_multimodal=True
                )
            )
        else:
            context_messages.extend(
                thread_to_context(
                    messages=chat_messages, agent_name=self._name, is_multimodal=False
                )
            )

        return context_messages

    async def save_state(self) -> Mapping[str, Any]:
        """Save the current state of the orchestrator.

        Returns:
            Mapping[str, Any]: A dictionary containing all state attributes except is_paused.
        """
        # Get all state attributes except message_history and is_paused
        data = self._state.model_dump(exclude={"is_paused"})

        # Serialize message history separately to preserve type information
        data["message_history"] = [
            message.dump() for message in self._state.message_history
        ]

        # Serialize plan if it exists
        if self._state.plan is not None:
            data["plan"] = self._state.plan.model_dump()

        return data

    async def load_state(self, state: Mapping[str, Any]) -> None:
        """Load a previously saved state into the orchestrator.

        Args:
            state (Mapping[str, Any]): A dictionary containing the state attributes to load.
        """
        # Create new state with defaults
        new_state = OrchestratorState()

        # Load basic attributes
        for key, value in state.items():
            if key == "message_history":
                # Handle message history separately
                new_state.message_history = [
                    self._message_factory.create(message) for message in value
                ]
            elif key == "plan" and value is not None:
                # Reconstruct Plan object if it exists
                new_state.plan = Plan(**value)
            elif key != "is_paused" and hasattr(new_state, key):
                setattr(new_state, key, value)

        # Update the state
        self._state = new_state

    async def _execute_sentinel_step(
        self,
        step: "SentinelPlanStep",
        progress_ledger: Dict[str, Any],
        cancellation_token: CancellationToken,
        sentinel_step_id: str,
    ) -> bool:
        """Execute a sentinel step with periodic checks of the specified condition.

        Args:
            step: The sentinel step to execute
            cancellation_token: Cancellation token to stop execution
            sentinel_step_id: Unique ID for this sentinel step execution

        Returns:
            bool: True if the sentinel step completed successfully, False if paused
        """
        # Number of times to iterate over the condition
        iteration = 0

        # Time tracking variables
        start_time = datetime.now()
        last_check_time = None

        # The agent tasked with this sentinel step
        agent_name = step.agent_name

        # Validate agent exists
        valid_agent = False
        for participant_name in self._agent_execution_names:
            if participant_name == agent_name:
                valid_agent = True
                break
        if not valid_agent:
            raise ValueError(
                f"Invalid agent: {agent_name}, participants are: {self._agent_execution_names}"
            )

        # Get the agent container
        agent_container = await self._runtime.try_get_underlying_agent_instance(
            AgentId(
                type=self._participant_name_to_topic_type[agent_name],
                key=self.id.key,
            )
        )

        if agent_container._agent is not None:  # type: ignore
            agent = agent_container._agent  # type: ignore
        else:
            raise ValueError(
                f"Agent container for {agent_name} does not have a valid agent instance"
            )

        # gets the instruction that the agent will perform
        step_details = step.details

        # only save the state when iteration == 1
        initial_agent_state = None
        can_save_load = hasattr(agent, "save_state") and hasattr(agent, "load_state")  # type: ignore

        num_errors_encountered = 0
        MAX_SENTINEL_STEP_ERRORS_ALLOWED = 3
        just_encountered_error = False

        while True:
            try:
                # Check for pause at the beginning of each iteration
                if self._state.is_paused:
                    await self._log_message_agentchat(
                        f"Sentinel step '{step.title}' is paused. Waiting for resume...",
                        metadata={"internal": "no", "type": "sentinel_paused"},
                    )
                    return False

                # Check if task is cancelled
                if cancellation_token.is_cancelled():
                    return False

                # increases iteration count
                iteration += 1
                just_encountered_error = False

                # Update time tracking
                current_time = datetime.now()
                time_since_started = (current_time - start_time).total_seconds()
                if last_check_time is not None:
                    time_since_last_check = (
                        current_time - last_check_time
                    ).total_seconds()
                else:
                    time_since_last_check = 0.0
                last_check_time = current_time

                # loads the initial state of the agent
                if can_save_load and initial_agent_state is not None:
                    if agent_name == self._web_agent_topic:
                        await agent.load_state(initial_agent_state, load_browser=False)  # type: ignore
                    else:
                        await agent.load_state(initial_agent_state)  # type: ignore

                # creates a BaseChatMessage instance and turns into a sequence
                instruction_from_ledger = progress_ledger["instruction_or_question"][
                    "answer"
                ]
                content = f"Your high level goal: {step_details}, the following might be useful but rely on the high level goal more: {instruction_from_ledger}"

                sentinel_task_agent_message = [
                    TextMessage(
                        content=content,
                        source="user",
                    )
                ]

                # uses streaming to get ALL responses
                final_response: Optional[Response] = None
                async for response in agent.on_messages_stream(  # type: ignore
                    sentinel_task_agent_message, cancellation_token
                ):
                    # Check for pause during agent execution
                    if self._state.is_paused:
                        await self._log_message_agentchat(
                            f"Sentinel step '{step.title}' was paused during agent execution.",
                            metadata={"internal": "no", "type": "sentinel_paused"},
                        )
                        return False

                    if isinstance(response, Response):
                        # logs each step of the process
                        if response.chat_message:
                            chat_content = response.chat_message
                            # Create new metadata dict with sentinel tracking
                            existing_metadata = (
                                chat_content.metadata
                                if hasattr(chat_content, "metadata")
                                and chat_content.metadata
                                else {}
                            )
                            new_metadata = {
                                **existing_metadata,
                                "sentinel_id": sentinel_step_id,
                                "check_number": str(iteration),
                            }

                            # Create a new message with the metadata
                            if isinstance(chat_content, TextMessage):
                                logged_message = TextMessage(
                                    content=chat_content.content,
                                    source=chat_content.source,
                                    metadata=new_metadata,
                                )
                            elif isinstance(chat_content, MultiModalMessage):
                                logged_message = MultiModalMessage(
                                    content=chat_content.content,
                                    source=chat_content.source,
                                    metadata=new_metadata,
                                )
                            else:
                                logged_message = chat_content

                            await self._log_message_agentchat(
                                content="dummy",
                                entire_message=logged_message,
                            )

                        final_response = response
                    elif isinstance(response, TextMessage) or isinstance(
                        response, MultiModalMessage
                    ):
                        await self._log_message_agentchat(
                            content="not used",
                            entire_message=response,
                        )
                # this is a MultiModalMessage or TextMessage object
                assert (
                    final_response is not None
                    and final_response.chat_message is not None
                )
                last_agent_message = final_response.chat_message

                # Check if condition is met
                if iteration == 1 and can_save_load:
                    initial_agent_state = await agent.save_state()  # type: ignore
                condition_met = None
                reason = None
                suggested_sleep_duration = step.sleep_duration
                suggested_sleep_duration_reason = "No reason provided"
                # For integer condition, check if we've reached the required iterations
                if isinstance(step.condition, int):
                    condition_met = iteration >= step.condition

                # For string condition, check with an LLM if the condition is met
                else:
                    # initializes empty context and adds the last message in the system
                    context: List[LLMMessage] = []
                    assert isinstance(
                        last_agent_message, MultiModalMessage | TextMessage
                    )
                    context.extend(
                        [
                            UserMessage(
                                content=f"Progress untill this step: {progress_ledger['progress_summary']}",
                                source=self._name,
                            ),
                            UserMessage(
                                content=last_agent_message.content,
                                source=agent_name,
                            ),
                        ]
                    )

                    # gets the structured prompt for the condition check
                    step_description: str = f"Step Title {step.title}, Step Instruction {step.details}, Step Condition {step.condition}, Agent Name {agent_name}"
                    condition_check_message = UserMessage(
                        content=ORCHESTRATOR_SENTINEL_CONDITION_CHECK_PROMPT.format(
                            step_description=step_description,
                            condition=step.condition,
                            current_sleep_duration=step.sleep_duration,
                            current_time=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            time_since_started=time_since_started,
                            checks_done=iteration,
                            time_since_last_check=time_since_last_check,
                        ),
                        source=self._name,
                    )
                    context.append(condition_check_message)

                    # Check for pause before LLM condition check
                    if self._state.is_paused:
                        await self._log_message_agentchat(
                            f"Sentinel step '{step.title}' was paused before condition check.",
                            metadata={"internal": "no", "type": "sentinel_paused"},
                        )
                        return False

                    # sends the condition check (the 2 messages) to an LLM
                    response_json = await self._get_json_response(
                        context,
                        validate_sentinel_condition_check_json,
                        cancellation_token,
                    )
                    assert isinstance(response_json, dict)
                    error_encountered = response_json.get("error_encountered", False)
                    if error_encountered:
                        just_encountered_error = True
                        num_errors_encountered += 1
                        if num_errors_encountered >= MAX_SENTINEL_STEP_ERRORS_ALLOWED:
                            await self._log_message_agentchat(
                                f"Maximum error limit reached during sentinel condition checks. Aborting sentinel step '{step.title}'.",
                                metadata={
                                    "internal": "no",
                                    "type": "sentinel_error",
                                },
                            )
                            # inform orchestrator that the step has failed
                            self._state.message_history.append(
                                TextMessage(
                                    content=f"Sentinel step '{step.title}' aborted due to repeated errors during condition checks.",
                                    source="user",
                                )
                            )
                            return False

                    condition_met = response_json.get("condition_met", None)
                    reason = response_json.get("reason", None)
                    suggested_sleep_duration = response_json.get(
                        "sleep_duration", step.sleep_duration
                    )
                    suggested_sleep_duration_reason = response_json.get(
                        "sleep_duration_reason", "No reason provided"
                    )

                # If condition met, return to complete the step
                if condition_met:
                    log_msg = f"Condition satisfied: {reason}."
                    complete_metadata = {
                        "internal": "no",
                        "type": "sentinel_complete",
                        "sentinel_id": sentinel_step_id,
                        "total_checks": str(iteration),
                        "runtime": str(int(time_since_started)),
                        "reason": reason or "Condition met",
                    }
                    await self._log_message_agentchat(
                        log_msg,
                        metadata=complete_metadata,
                    )
                    # inform orchestrator that the step is completed
                    self._state.message_history.append(
                        TextMessage(
                            content=f"Sentinel step '{step.title}' completed successfully. Reason: {reason}",
                            source="user",
                        )
                    )
                    return True
                else:
                    # Determine sleep duration based on dynamic sleep configuration
                    if self._config.sentinel_plan.dynamic_sentinel_sleep:
                        sleep_duration = suggested_sleep_duration
                    else:
                        sleep_duration = step.sleep_duration
                    if just_encountered_error:
                        # if we just encountered an error, we force a shorter sleep duration
                        sleep_duration = min(sleep_duration, 30)  # cap at 30 secs
                    # Sleep before the next check
                    sleep_metadata = {
                        "internal": "no",
                        "type": "sentinel_check",
                        "sentinel_id": sentinel_step_id,
                        "check_number": str(iteration),
                        "total_checks": str(iteration),
                        "runtime": str(int(time_since_started)),
                        "next_check_in": str(sleep_duration),
                        "condition_met": "false",
                        "reason": reason or "Condition not yet satisfied",
                    }
                    await self._log_message_agentchat(
                        f"(Check #{iteration}) Condition not satisfied: {reason} \n Sleeping for {sleep_duration}s before next check.",
                        metadata=sleep_metadata,
                    )
                    if self._config.sentinel_plan.dynamic_sentinel_sleep:
                        await self._log_message_agentchat(
                            f"Reason for suggested sleep duration: {suggested_sleep_duration_reason}",
                            metadata={"internal": "no", "type": "sentinel_sleep"},
                        )

                    sleep_task = asyncio.create_task(asyncio.sleep(sleep_duration))
                    pause_task = asyncio.create_task(self._pause_event.wait())
                    _, pending = await asyncio.wait(
                        [sleep_task, pause_task], return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # Check if we were paused during sleep
                    if self._state.is_paused:
                        await self._log_message_agentchat(
                            f"Sentinel step '{step.title}' was paused during sleep. Will resume when unpaused.",
                            metadata={"internal": "no", "type": "sentinel_paused"},
                        )
                        return False

            except asyncio.CancelledError:
                return False
            except Exception as e:
                trace_logger.error(f"Error in sentinel step execution: {e}")
                raise
