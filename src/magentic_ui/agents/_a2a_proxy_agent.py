from typing import List, Optional, Sequence, AsyncGenerator, Any, Mapping
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_agentchat.base import Response
from autogen_core import CancellationToken
from pydantic import Field
import httpx
import asyncio
from loguru import logger

# Placeholder for A2A SDK - replace with actual SDK imports and usage
# from a2a_sdk import A2AClient, A2ARequest, A2AError, A2ATimeoutError

class A2AProxyAgentConfig(BaseModel):
    name: str
    a2a_consultant_uris: List[str] = Field(default_factory=list)
    # Add other relevant config fields if needed, e.g., timeouts

class A2AProxyAgent(BaseChatAgent):
    """
    An agent that acts as a proxy to consult other A2A (Agent-to-Agent) enabled agents
    for planning suggestions or other queries.
    """
    component_type = "agent"
    component_config_schema = A2AProxyAgentConfig
    DEFAULT_DESCRIPTION = "An agent that can consult other agents for planning advice."

    def __init__(
        self,
        name: str,
        a2a_consultant_uris: Optional[List[str]] = None,
        description: str = DEFAULT_DESCRIPTION,
        # Add other necessary parameters like A2A client instances or configs
    ):
        super().__init__(name, description)
        self._a2a_consultant_uris = a2a_consultant_uris or []
        # In a real scenario, an A2A client would be initialized here.
        # For now, we'll simulate network requests.
        # self._a2a_client = A2AClient(...) 
        self._http_client = httpx.AsyncClient(timeout=10.0) # General purpose HTTP client for now

    async def get_planning_suggestions(self, task_description: str) -> List[str]:
        """
        Contacts configured A2A consultant agents to get planning suggestions for a given task.
        """
        if not self._a2a_consultant_uris:
            logger.info("A2AProxyAgent: No consultant URIs configured. Skipping suggestions.")
            return []

        suggestions: List[str] = []
        suggestion_tasks = []

        for agent_uri in self._a2a_consultant_uris:
            suggestion_tasks.append(
                self._get_single_agent_suggestion(agent_uri, task_description)
            )
        
        results = await asyncio.gather(*suggestion_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            agent_uri = self._a2a_consultant_uris[i]
            if isinstance(result, Exception):
                logger.error(f"A2AProxyAgent: Error getting suggestion from {agent_uri}: {result}")
            elif result: # Ensure result is not None or empty
                suggestions.append(f"Suggestion from {agent_uri}: {result}")
        
        return suggestions

    async def _get_single_agent_suggestion(self, agent_uri: str, task_description: str) -> Optional[str]:
        """
        Helper to get a planning suggestion from a single A2A agent.
        This method would use the A2A SDK to send a request.
        For now, it simulates a request.
        """
        logger.info(f"A2AProxyAgent: Requesting planning suggestion from {agent_uri} for task: '{task_description[:50]}...'")
        
        # Simulate A2A SDK usage
        # request = A2ARequest(skill="suggest_plan_for_task", params={"task_description": task_description})
        try:
            # This is a placeholder for actual A2A communication.
            # In a real implementation, you'd use the A2A SDK here.
            # For example: response = await self._a2a_client.send_request(agent_uri, request, timeout=10)
            # We'll mock a response structure.
            
            # Let's assume the A2A endpoint is a simple HTTP endpoint for now
            # that accepts a JSON payload and returns a JSON response.
            payload = {
                "skill": "suggest_plan_for_task",
                "params": {"task_description": task_description}
            }
            
            # Simulate different agent behaviors for testing
            if "agent1" in agent_uri:
                # Simulate a successful response
                # response_data = await self._http_client.post(f"{agent_uri}/suggest_plan", json=payload)
                # response_data.raise_for_status() 
                # return response_data.json().get("suggestion")
                await asyncio.sleep(0.5) # Simulate network latency
                return f"Delegate task '{task_description[:20]}...' to a research agent."
            elif "agent2" in agent_uri:
                await asyncio.sleep(1) # Simulate network latency
                return f"Break down task '{task_description[:20]}...' into smaller sub-tasks."
            elif "agent_timeout" in agent_uri:
                await asyncio.sleep(15) # Simulate a timeout
                return None # Should be caught by timeout logic if using actual client
            elif "agent_error" in agent_uri:
                raise ValueError("Simulated agent processing error") # Simulate an error
            else:
                # Default mock response
                await asyncio.sleep(0.2)
                return f"Consider using a tool for '{task_description[:20]}...'."

        # except A2ATimeoutError as e: # Replace with actual A2A SDK exceptions
        #     logger.warning(f"A2AProxyAgent: Timeout getting suggestion from {agent_uri}: {e}")
        #     return None
        # except A2AError as e: # Replace with actual A2A SDK exceptions
        #     logger.error(f"A2AProxyAgent: A2A error getting suggestion from {agent_uri}: {e}")
        #     return None
        except httpx.TimeoutException:
            logger.warning(f"A2AProxyAgent: HTTP timeout getting suggestion from {agent_uri}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"A2AProxyAgent: HTTP error from {agent_uri}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"A2AProxyAgent: Generic error getting suggestion from {agent_uri}: {type(e).__name__} - {e}")
            return None # Gracefully handle other errors

    async def check_for_interventions(self) -> List[str]:
        """
        Checks for intervention messages from supervising A2A agents.
        This is a mock implementation. In a real scenario, this would involve
        listening to a specific endpoint or using an A2A SDK to receive messages.
        """
        # Simulate receiving an intervention message sometimes
        # For testing, we can make this deterministic or random
        await asyncio.sleep(0.1) # Simulate brief check
        # if random.random() < 0.1: # Simulate 10% chance of intervention
        #     return ["A2A_Intervention: Step 2 seems problematic, consider re-evaluating data source."]
        # For consistent testing of the pathway, always return an intervention for now if URIs are configured.
        if self._a2a_consultant_uris: # Reuse this to simulate "supervisors are configured"
             return ["A2A_Intervention: Mock Intervention - The current approach for step might be inefficient. Consider using a specialized tool or splitting the step."]
        return []

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseChatMessage | Response, None]:
        """
        Handles incoming messages. For A2AProxy, this might involve being asked to get suggestions.
        This is a simplified implementation.
        """
        if not messages:
            yield Response(chat_message=TextMessage(content="No message received.", source=self.name))
            return

        last_message = messages[-1]
        if not isinstance(last_message, TextMessage):
            yield Response(chat_message=TextMessage(content="Can only process text messages.", source=self.name))
            return

        task_description = last_message.content

        # Example: If the A2A proxy is directly asked for suggestions
        if "get planning suggestions for" in task_description.lower():
            actual_task = task_description.lower().split("get planning suggestions for", 1)[-1].strip()
            if not actual_task:
                yield Response(TextMessage(content="No task description provided for suggestions.", source=self.name))
                return
            
            logger.info(f"A2AProxyAgent: Received direct request for planning suggestions for task: '{actual_task}'")
            suggestions = await self.get_planning_suggestions(actual_task)
            if suggestions:
                response_content = "Received planning suggestions:\n" + "\n".join(suggestions)
            else:
                response_content = "No planning suggestions received from consultant agents."
            
            response_msg = TextMessage(content=response_content, source=self.name)
            self._chat_history.append(last_message) # Add incoming message to history
            self._chat_history.append(response_msg) # Add outgoing message to history
            yield Response(chat_message=response_msg)
        else:
            # Default behavior if not a specific "get suggestions" command
            # This agent might not be designed for general chat, so this part could be minimal.
            response_msg = TextMessage(
                content=f"A2AProxyAgent received: '{task_description}'. I can fetch planning suggestions if asked directly.",
                source=self.name
            )
            self._chat_history.append(last_message)
            self._chat_history.append(response_msg)
            yield Response(chat_message=response_msg)

    async def on_messages(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        """Handle incoming messages and return a single response. Calls the on_messages_stream."""
        response: Response | None = None
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                response = message
        if response is None: # Should not happen if stream always yields a Response
             return Response(chat_message=TextMessage(content="Failed to process message.", source=self.name))
        return response
        
    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """Clear the chat history or any other relevant state."""
        super().on_reset(cancellation_token) # BaseChatAgent has on_reset that clears chat_history
        logger.info(f"A2AProxyAgent {self.name} was reset.")

    def _to_config(self) -> A2AProxyAgentConfig:
        """Convert the agent's state to a configuration object."""
        return A2AProxyAgentConfig(
            name=self.name,
            a2a_consultant_uris=self._a2a_consultant_uris,
            # description=self.description, # BaseChatAgent doesn't store description in config by default
        )

    @classmethod
    def _from_config(cls, config: A2AProxyAgentConfig) -> "A2AProxyAgent":
        """Create an agent instance from a configuration object."""
        return cls(
            name=config.name,
            a2a_consultant_uris=config.a2a_consultant_uris,
            # description=config.description,
        )

    async def save_state(self) -> Mapping[str, Any]:
        """Save the state of the agent."""
        base_state = await super().save_state()
        # Add any A2AProxyAgent specific state if needed
        # For now, consultant URIs are part of config, not dynamic state.
        return base_state

    async def load_state(self, state: Mapping[str, Any]) -> None:
        """Load the state of the agent."""
        await super().load_state(state)
        # Load any A2AProxyAgent specific state if needed

    async def close(self) -> None:
        """Clean up resources, like the HTTP client."""
        await self._http_client.aclose()
        logger.info(f"A2AProxyAgent {self.name} closed HTTP client.")
        # If using a real A2A SDK client, close it here:
        # await self._a2a_client.close()

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        """Get the types of messages produced by the agent."""
        return (TextMessage,)
