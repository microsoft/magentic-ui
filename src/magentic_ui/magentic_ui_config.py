from typing import Any, ClassVar, Dict, List, Literal, Optional, Union

from autogen_core import ComponentModel
from pydantic import BaseModel, Field

from .agents.mcp import McpAgentConfig
from .types import Plan


class SentinelPlanConfig(BaseModel):
    """Configuration for sentinel plan functionality.

    Attributes:
        enable_sentinel_steps (bool): Whether sentinel plan steps are enabled. Default: False.
        dynamic_sentinel_sleep (bool): Whether to dynamically adapt sleep duration based on LLM response. Default: False.
    """

    enable_sentinel_steps: bool = False
    dynamic_sentinel_sleep: bool = False


class ModelClientConfigs(BaseModel):
    """Configurations for the model clients.
    Attributes:
        default_client_config (dict): Default configuration for the model clients.
        orchestrator (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the orchestrator component. Default: None.
        web_surfer (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the web surfer component. Default: None.
        coder (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the coder component. Default: None.
        file_surfer (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the file surfer component. Default: None.
        action_guard (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the action guard component. Default: None.
    """

    orchestrator: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    web_surfer: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    coder: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    file_surfer: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    action_guard: Optional[Union[ComponentModel, Dict[str, Any]]] = None

    default_client_config: ClassVar[Dict[str, Any]] = {
        "provider": "OpenAIChatCompletionClient",
        "config": {
            "model": "gpt-4.1-2025-04-14",
        },
        "max_retries": 10,
    }
    default_action_guard_config: ClassVar[Dict[str, Any]] = {
        "provider": "OpenAIChatCompletionClient",
        "config": {
            "model": "gpt-4.1-nano-2025-04-14",
        },
        "max_retries": 10,
    }

    @classmethod
    def get_default_client_config(cls) -> Dict[str, Any]:
        return cls.default_client_config

    @classmethod
    def get_default_action_guard_config(cls) -> Dict[str, Any]:
        return cls.default_action_guard_config


class MagenticUIConfig(BaseModel):
    """
    A simplified set of configuration options for Magentic-UI.

    Attributes:
        model_client_configs (ModelClientConfigs): Configurations for the model client.
        mcp_agent_configs (List[McpAgentConfig], optional): Configs for AssistantAgents with access to MCP Servers.
        cooperative_planning (bool): Enable co-planning mode (default: enabled), user will be involved in the planning process. Default: True.
        autonomous_execution (bool): Enable autonomous execution mode (default: disabled), user will not be involved in the execution. Default: False.
        allowed_websites (List[str], optional): List of websites that are permitted.
        max_actions_per_step (int): Maximum number of actions allowed per step. Default: 5.
        multiple_tools_per_call (bool): Allow multiple tools to be called in a single step. Default: False.
        max_turns (int): Maximum number of operational turns allowed. Default: 20.
        plan (Plan, optional): A pre-defined plan. In cooperative planning mode, the plan will be enhanced with user feedback.
        approval_policy (str, optional): Policy for action approval. Default: "auto-conservative".
        allow_for_replans (bool): Whether to allow the orchestrator to create a new plan when needed. Default: True.
        do_bing_search (bool): Flag to determine if Bing search should be used to come up with information for the plan. Default: False.
        websurfer_loop (bool): Flag to determine if the websurfer should loop through the plan. Default: False.
        retrieve_relevant_plans (Literal["never", "hint", "reuse"]): Determines if the orchestrator should retrieve relevant plans from memory. Default: `never`.
        memory_controller_key (str, optional): The key to retrieve the memory_controller for a particular user. Default: None.
        model_context_token_limit (int, optional): The maximum number of tokens the model can use. Default: 110000.
        allow_follow_up_input (bool): Flag to determine if new input should be requested after a final answer is given. Default: True.
        final_answer_prompt (str, optional): Prompt for the final answer. Should be a string that can be formatted with the {task} variable. Default: None.
        playwright_port (int, optional): Port for the Playwright browser. Default: -1 (auto-assign).
        novnc_port (int, optional): Port for the noVNC server. Default: -1 (auto-assign).
        user_proxy_type (str, optional): Type of user proxy agent to use ("dummy", "metadata", or None for default). Default: None.
        task (str, optional): Task to be performed by the agents. Default: None.
        hints (str, optional): Helpful hints for the task. Default: None.
        answer (str, optional): Answer to the task. Default: None.
        inside_docker (bool, optional): Whether to run inside a docker container. Default: True.
        browser_headless (bool, optional): Whether to run a headless browser or not. Default: False.
        browser_local (bool, optional): Whether to run a local browser (as opposed to dockerized browser). Default: False.
        sentinel_plan (SentinelPlanConfig, optional): Configuration for sentinel plan functionality. Default: SentinelPlanConfig().
        run_without_docker (bool, optional): If docker is not available, run without docker for browser, remove coder and filesurfer agents. Default: False.
        network_name (str, optional): The name of the network to use for the browser. Default: "my-network".
    """

    model_client_configs: ModelClientConfigs = Field(default_factory=ModelClientConfigs)
    mcp_agent_configs: List[McpAgentConfig] = Field(default_factory=lambda: [])
    cooperative_planning: bool = True
    autonomous_execution: bool = False
    allowed_websites: Optional[List[str]] = None
    max_actions_per_step: int = 5
    multiple_tools_per_call: bool = False
    max_turns: int = 20
    plan: Optional[Plan] = None
    approval_policy: Literal[
        "always", "never", "auto-conservative", "auto-permissive"
    ] = "auto-conservative"
    allow_for_replans: bool = True
    do_bing_search: bool = False
    websurfer_loop: bool = False
    retrieve_relevant_plans: Literal["never", "hint", "reuse"] = "never"
    memory_controller_key: Optional[str] = None
    model_context_token_limit: int = 110000
    allow_follow_up_input: bool = True
    final_answer_prompt: str | None = None
    playwright_port: int = -1
    novnc_port: int = -1
    user_proxy_type: Optional[str] = None
    task: Optional[str] = None
    hints: Optional[str] = None
    answer: Optional[str] = None
    inside_docker: bool = True
    browser_local: bool = False
    sentinel_plan: SentinelPlanConfig = Field(default_factory=SentinelPlanConfig)
    run_without_docker: bool = False
    browser_headless: bool = False
    network_name: str = "my-network"
