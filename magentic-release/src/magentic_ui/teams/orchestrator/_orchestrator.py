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

from ...types import HumanInputFormat, Plan
from ...utils import dict_to_str, thread_to_context
from ...tools.bing_search import get_bing_search_results
from ...teams.orchestrator.orchestrator_config import OrchestratorConfig
from ._prompts import (
    ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING,
    ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING_AUTONOMOUS,
    ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION,
    ORCHESTRATOR_FINAL_ANSWER_PROMPT,
    ORCHESTRATOR_PROGRESS_LEDGER_PROMPT,
    ORCHESTRATOR_TASK_LEDGER_FULL_FORMAT,
    ORCHESTRATOR_PLAN_PROMPT_JSON,
    ORCHESTRATOR_PLAN_REPLAN_JSON,
    INSTRUCTION_AGENT_FORMAT,
    validate_ledger_json,
    validate_plan_json,
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
            return ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING_AUTONOMOUS.format(
                date_today=date_today,
                team=self._team_description,
            )
        else:
            return ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING.format(
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

        return ORCHESTRATOR_PLAN_PROMPT_JSON.format(
            team=team, additional_instructions=additional_instructions
        )

    def _get_task_ledger_replan_plan_prompt(
        self, task: str, team: str, plan: str
    ) -> str:
        additional_instructions = ""
        if self._config.allowed_websites is not None:
            additional_instructions = (
                "Only use the following websites if possible: "
                + ", ".join(self._config.allowed_websites)
            )
        return ORCHESTRATOR_PLAN_REPLAN_JSON.format(
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
        return ORCHESTRATOR_PROGRESS_LEDGER_PROMPT.format(
            task=task,
            plan=plan,
            step_index=step_index,
            step_title=self._state.plan[step_index].title,
            step_details=self._state.plan[step_index].details,
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
        return validate_plan_json(json_response)

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
    ) -> None:
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
        while retries < self._config.max_json_retries:
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
            try:
                json_response = json.loads(response.content)
                # Use the validate_json function to check the response
                if validate_json(json_response):
                    return json_response
                else:
                    exception_message = "Validation failed for JSON response, retrying. You must return a valid JSON object parsed from the response."
                    await self._log_message(
                        f"Validation failed for JSON response, retrying ({retries}/{self._config.max_json_retries})"
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
        raise ValueError("Failed to get a valid JSON response after multiple retries")

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

    async def resume(self) -> None:
        """Resume the group chat manager."""
        self._state.is_paused = False

    @event
    async def handle_agent_response(
        self, message: GroupChatAgentResponse, ctx: MessageContext
    ) -> None:  # type: ignore
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
                    await self._orchestrate_first_step(cancellation_token)
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
                    await self._orchestrate_first_step(cancellation_token)
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
                await self._orchestrate_first_step(cancellation_token)
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
            await self._orchestrate_first_step(cancellation_token)

    async def _orchestrate_first_step(
        self, cancellation_token: CancellationToken
    ) -> None:
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

        # check if the plan is empty, complete, or we have reached the max turns
        if (
            (not isinstance(self._state.plan, Plan) or len(self._state.plan) == 0)
            or (self._state.current_step_idx >= len(self._state.plan))
            or (
                self._config.max_turns is not None
                and self._state.n_rounds > self._config.max_turns
            )
        ):
            await self._prepare_final_answer("Max rounds reached.", cancellation_token)
            return
        self._state.n_rounds += 1
        context = self._thread_to_context()
        # Creat the progress ledger

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
            # let user speak next if paused
            await self._request_next_speaker(self._user_agent_topic, cancellation_token)
            return
        assert progress_ledger is not None

        await self._log_message_agentchat(dict_to_str(progress_ledger), internal=True)

        # Broadcast the next step
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

    async def _orchestrate_step_execution(
        self, cancellation_token: CancellationToken
    ) -> None:
        # Execution stage
        # Check if we reached the maximum number of rounds
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

        # Broadcast the next step
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
            [f"COMPLETED STEP {i+1}: {step}" for i, step in enumerate(completed_steps)]
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
            # If new plan is None, keep the completed steps
            self._state.plan = Plan(task=self._state.task, steps=completed_steps)
            self._state.plan_str = str(self._state.plan)

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
            await self._orchestrate_first_step(cancellation_token)

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
