import logging
from typing import Callable, List, Dict, Any, Mapping, AsyncGenerator, Sequence
import json
import asyncio
from pydantic import BaseModel
import inspect

from autogen_core.models import ChatCompletionClient
from autogen_core import (
    AgentId,
    Component,
    ComponentModel,
    AgentRuntime,
    CancellationToken,
)
from autogen_agentchat import EVENT_LOGGER_NAME, TRACE_LOGGER_NAME
from autogen_agentchat.base import ChatAgent, TerminationCondition, TaskResult
from autogen_agentchat.state import TeamState, BaseState
from autogen_agentchat.teams import BaseGroupChat
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, MessageFactory
from autogen_agentchat.teams._group_chat._events import GroupChatTermination
from ._orchestrator import Orchestrator
from ...teams.orchestrator.orchestrator_config import OrchestratorConfig
from ...types import CheckpointEvent
from ...learning.memory_provider import MemoryControllerProvider

trace_logger = logging.getLogger(TRACE_LOGGER_NAME)
event_logger = logging.getLogger(EVENT_LOGGER_NAME)


class GroupChatConfig(BaseModel):
    participants: List[ComponentModel]
    model_client: ComponentModel
    orchestrator_config: Dict[str, Any]
    termination_condition: ComponentModel | None = None


class GroupChatState(BaseState):
    agent_states: Dict[str, Any]
    orchestrater_state: Any


class GroupChat(BaseGroupChat, Component[GroupChatConfig]):
    """
    args:
        participants (List[ChatAgent]): The agents participating in the group chat. Agents must implement Component Config.
        model_client (ChatCompletionClient): The model client to use for generating responses.
        orchestrator_config (OrchestratorConfig): The configuration for the orchestrator.
        termination_condition (TerminationCondition, optional): The termination condition for the group chat.
        memory_provider (MemoryControllerProvider, optional): The memory provider for the group chat.

    """

    component_config_schema = GroupChatConfig
    component_provider_override = "magentic_ui.teams.GroupChat"

    def __init__(
        self,
        participants: List[ChatAgent],
        model_client: ChatCompletionClient,
        orchestrator_config: OrchestratorConfig,
        runtime: AgentRuntime | None = None,
        *,
        termination_condition: TerminationCondition | None = None,
        memory_provider: MemoryControllerProvider | None = None,
    ):
        super().__init__(
            participants,
            group_chat_manager_name="Orchestrator",
            group_chat_manager_class=Orchestrator,
            termination_condition=termination_condition,
            max_turns=orchestrator_config.max_turns,
            runtime=runtime,
        )
        self._orchestrator_config = orchestrator_config
        # Validate the participants.
        if len(participants) == 0:
            raise ValueError("At least one participant is required for GroupChat.")
        self._model_client = model_client
        self.is_paused = False
        self._message_factory = MessageFactory()
        self._memory_provider = memory_provider

    def _create_group_chat_manager_factory(
        self,
        name: str,
        group_topic_type: str,
        output_topic_type: str,
        participant_topic_types: List[str],
        participant_names: List[str],
        participant_descriptions: List[str],
        output_message_queue: asyncio.Queue[
            BaseAgentEvent | BaseChatMessage | GroupChatTermination
        ],
        termination_condition: TerminationCondition | None,
        max_turns: int | None,
        message_factory: MessageFactory,
    ) -> Callable[[], Orchestrator]:
        return lambda: Orchestrator(
            name=name,
            group_topic_type=group_topic_type,
            output_topic_type=output_topic_type,
            participant_topic_types=participant_topic_types,
            participant_descriptions=participant_descriptions,
            participant_names=participant_names,
            output_message_queue=output_message_queue,
            model_client=self._model_client,
            config=self._orchestrator_config,
            termination_condition=termination_condition,
            max_turns=max_turns,
            message_factory=self._message_factory,
            memory_provider=self._memory_provider,
        )

    async def run_stream(
        self,
        *,
        task: str | BaseChatMessage | Sequence[BaseChatMessage] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | TaskResult, None]:
        async for message in super().run_stream(
            task=task, cancellation_token=cancellation_token
        ):
            yield message
            partial_state = await self._get_partial_state()
            yield CheckpointEvent(
                source="orchestrator", state=json.dumps(partial_state)
            )  # type: ignore

    async def pause(self) -> None:  # TODO: can this be implemented using events?
        orchestrator = await self._runtime.try_get_underlying_agent_instance(
            AgentId(type=self._group_chat_manager_topic_type, key=self._team_id),
            type=Orchestrator,
        )
        await orchestrator.pause()
        for agent in self._participants:
            if hasattr(agent, "pause"):
                await agent.pause()  # type: ignore

    async def resume(self) -> None:
        orchestrator = await self._runtime.try_get_underlying_agent_instance(
            AgentId(type=self._group_chat_manager_topic_type, key=self._team_id),
            type=Orchestrator,
        )
        await orchestrator.resume()
        for agent in self._participants:
            if hasattr(agent, "resume"):
                await agent.resume()  # type: ignore

    async def lazy_init(self) -> None:
        await asyncio.gather(
            *(
                getattr(agent, "lazy_init")()
                for agent in self._participants
                if hasattr(agent, "lazy_init")
                and inspect.iscoroutinefunction(getattr(agent, "lazy_init"))
            )
        )

    def _to_config(self) -> GroupChatConfig:
        return GroupChatConfig(
            participants=[agent.dump_component() for agent in self._participants],
            model_client=self._model_client.dump_component(),
            orchestrator_config=self._orchestrator_config.model_dump(),
            termination_condition=self._termination_condition.dump_component()
            if self._termination_condition
            else None,
        )

    @classmethod
    def _from_config(cls, config: GroupChatConfig) -> "GroupChat":
        return cls(
            participants=[
                ChatAgent.load_component(agent) for agent in config.participants
            ],
            model_client=ChatCompletionClient.load_component(config.model_client),
            orchestrator_config=OrchestratorConfig(**config.orchestrator_config),
            termination_condition=TerminationCondition.load_component(
                config.termination_condition
            )
            if config.termination_condition
            else None,
        )

    async def _get_partial_state(self) -> Mapping[str, Any]:
        """Save the state of the group chat team."""
        try:
            # Save the state of the runtime. This will save the state of the participants and the group chat manager.
            agent_states: Dict[str, Mapping[str, Any]] = {}
            # Save the state of all participants.
            for name, agent_type in zip(
                self._participant_names, self._participant_topic_types, strict=True
            ):
                agent_id = AgentId(type=agent_type, key=self._team_id)
                # NOTE: We are using the runtime's save state method rather than the agent instance's
                # save_state method because we want to support saving state of remote agents.
                agent_states[name] = await self._runtime.agent_save_state(agent_id)
            # Save the state of the group chat manager.
            agent_id = AgentId(
                type=self._group_chat_manager_topic_type, key=self._team_id
            )
            agent_states[
                self._group_chat_manager_name
            ] = await self._runtime.agent_save_state(agent_id)
            return TeamState(agent_states=agent_states).model_dump()
        finally:
            # Indicate that the team is no longer running.
            self._is_running = False

    async def close(self) -> None:
        if hasattr(self._model_client, "close"):
            await self._model_client.close()

        # Prepare a list of closable agents
        closable_agents: List[Orchestrator | ChatAgent] = [
            agent for agent in self._participants if hasattr(agent, "close")
        ]
        # can we close the orchestrator?
        orchestrator = await self._runtime.try_get_underlying_agent_instance(
            AgentId(type=self._group_chat_manager_topic_type, key=self._team_id),
            type=Orchestrator,
        )
        if hasattr(orchestrator, "close"):
            closable_agents.append(orchestrator)

        # Close all closable agents concurrently
        await asyncio.gather(
            *(agent.close() for agent in closable_agents), return_exceptions=True
        )

    @property
    def participants(self) -> List[ChatAgent]:
        """
        Get the list of participants in the group chat.

        Returns:
            List[ChatAgent]: The list of participants.
        """
        return self._participants
