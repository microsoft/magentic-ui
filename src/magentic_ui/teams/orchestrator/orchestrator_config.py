from pydantic import BaseModel, Field
from ...types import Plan
from typing import List, Literal, Optional, Union
from ...magentic_ui_config import SentinelPlanConfig


class OrchestratorConfig(BaseModel):
    """
    Configuration class for Orchestrator.

    Attributes:
        cooperative_planning (bool): Enable co-planning mode, requiring user-proxy feedback on plans. Default: True.
        autonomous_execution (bool): Enable autonomous execution mode; no human input is requested during execution. Default: False.
        allow_follow_up_input (bool): Flag to determine if new input should be requested after a final answer is given. Default: True.
        plan (Optional[Plan]): A pre-defined plan. In cooperative planning mode, the plan will be enhanced with user feedback.
        max_turns (Optional[int]): Maximum number of operational turns allowed. Default: 20.
        allow_for_replans (bool): Whether to allow the orchestrator to create a new plan when needed. Default: True.
        max_json_retries (int): Maximum number of retries for JSON operations. Default: 3.
        saved_facts (str, optional): Previously persisted facts.
        allowed_websites (List[str], optional): List of websites that are permitted.
        do_bing_search (bool): Flag to determine if Bing search should be used to come up with information for the plan. Default: False.
        final_answer_prompt (str, optional): Prompt for the final answer. Should be a string that can be formatted with the {task} variable.
        model_context_token_limit (int, optional): The maximum number of tokens that that can be sent to the model in a single request.
        retrieve_relevant_plans (Literal["never", "hint", "reuse"], optional): Determines if the orchestrator should retrieve relevant plans from memory. Default: `never`.
        memory_controller_key (str, optional): the key to retrieve the memory_controller for a particular user.
        max_replans (int, optional): Maximum number of replans allowed. Default: 3.
        no_overwrite_of_task (bool, optional): Whether to prevent the orchestrator from overwriting the task. Default: False.
        sentinel_plan (SentinelPlanConfig, optional): Configuration for sentinel plan functionality. Default: SentinelPlanConfig().
    """

    cooperative_planning: bool = True
    autonomous_execution: bool = False
    allow_follow_up_input: bool = True
    plan: Optional[Plan] = None
    max_turns: Optional[int] = 20
    allow_for_replans: bool = True
    max_json_retries: int = 3
    saved_facts: Optional[str] = None
    allowed_websites: Optional[List[str]] = None
    do_bing_search: bool = False
    final_answer_prompt: Optional[str] = None
    model_context_token_limit: Optional[int] = None
    retrieve_relevant_plans: Literal["never", "hint", "reuse"] = "never"
    memory_controller_key: Optional[str] = None
    max_replans: Union[int, None] = 3
    no_overwrite_of_task: bool = False
    sentinel_plan: SentinelPlanConfig = Field(default_factory=SentinelPlanConfig)
