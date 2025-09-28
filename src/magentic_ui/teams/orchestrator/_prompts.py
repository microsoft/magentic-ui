from typing import Any, Dict, List
from ._sentinel_prompts import (
    SENTINEL_STEP_EXAMPLES,
    SENTINEL_STEP_TYPES,
    HELPFUL_HINTS_FOR_PLANNING_SENTINEL,
)

ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION = """
    You are a helpful AI assistant named Magentic-UI built by Microsoft Research AI Frontiers.
    Your goal is to help the user with their request.
    You can complete actions on the web, complete actions on behalf of the user, execute code, and more.
    The browser the web_surfer accesses is also controlled by the user.
    You have access to a team of agents who can help you answer questions and complete tasks.

    The date today is: {date_today}
"""

ORCHESTRATOR_FINAL_ANSWER_PROMPT = """
    We are working on the following task:
    {task}

    The above messages contain the steps that took place to complete the task.

    Based on the information gathered, provide a final response to the user in response to the task.

    Make sure the user can easily verify your answer, include links if there are any. 
    
    Please refer to steps of the plan that was used to complete the task. Use the steps as a way to help the user verify your answer.
    
    Make sure to also say whether the answer was found using online search or from your own knowledge.

    There is no need to be verbose, but make sure it contains enough information for the user.
"""

# The specific format of the instruction for the agents to follow
INSTRUCTION_AGENT_FORMAT = """
    Step {step_index}: {step_title}
    \\n\\n
    {step_details}
    \\n\\n
    Instruction for {agent_name}: {instruction}
"""

# Keeps track of the task progress with a ledger so the orchestrator can see the progress
ORCHESTRATOR_TASK_LEDGER_FULL_FORMAT = """
    We are working to address the following user request:
    \\n\\n
    {task}
    \\n\\n
    To answer this request we have assembled the following team:
    \\n\\n
    {team}
    \\n\\n
    Here is the plan to follow as best as possible:
    \\n\\n
    {plan}
"""


PLAN_EXAMPLES = """
Example 1:

User request: "Report back the menus of three restaurants near the zipcode 98052"

Step 1:
- title: "Locate the menu of the first restaurant"
- details: "Locate the menu of the first restaurant. \\n Search for highly-rated restaurants in the 98052 area using Bing, select one with good reviews and an accessible menu, then extract and format the menu information for reporting."
- agent_name: "web_surfer"

Step 2:
- title: "Locate the menu of the second restaurant"
- details: "Locate the menu of the second restaurant. \\n After excluding the first restaurant, search for another well-reviewed establishment in 98052, ensuring it has a different cuisine type for variety, then collect and format its menu information."
- agent_name: "web_surfer"

Step 3:
- title: "Locate the menu of the third restaurant"
- details: "Locate the menu of the third restaurant. \\n Building on the previous searches but excluding the first two restaurants, find a third establishment with a distinct cuisine type, verify its menu is available online, and compile the menu details."
- agent_name: "web_surfer"


Example 2:

User request: "Execute the starter code for the autogen repo"

Step 1:
- title: "Locate the starter code for the autogen repo"
- details: "Locate the starter code for the autogen repo. \\n Search for the official AutoGen repository on GitHub, navigate to their examples or getting started section, and identify the recommended starter code for new users."
- agent_name: "web_surfer"

Step 2:
- title: "Execute the starter code for the autogen repo"
- details: "Execute the starter code for the autogen repo. \\n Set up the Python environment with the correct dependencies, ensure all required packages are installed at their specified versions, and run the starter code while capturing any output or errors."
- agent_name: "coder_agent"


Example 3:

User request: "Can you paraphrase the following sentence: 'The quick brown fox jumps over the lazy dog'"

You should not provide a plan for this request. Instead, just answer the question directly.
"""

HELPFUL_HINTS_FOR_PLANNING = """
Helpful tips:
- If the plan needs information from the user, try to get that information before creating the plan.
- When creating the plan you only need to add a step to the plan if it requires a different agent to be completed, or if the step is very complicated and can be split into two steps.
- Remember, there is no requirement to involve all team members -- a team member's particular expertise may not be needed for this task.
- Aim for a plan with the least number of steps possible.
- Use a search engine or platform to find the information you need. For instance, if you want to look up flight prices, use a flight search engine like Bing Flights. However, your final answer should not stop with a Bing search only.
- If there are images attached to the request, use them to help you complete the task and describe them to the other agents in the plan.
"""


def get_orchestrator_system_message_planning(
    sentinel_tasks_enabled: bool = False,
) -> str:
    """Get the orchestrator system message for planning, with optional SentinelPlanStep support."""

    base_message = """
    
    You are a helpful AI assistant named Magentic-UI built by Microsoft Research AI Frontiers.
    Your goal is to help the user with their request.
    You can complete actions on the web, complete actions on behalf of the user, execute code, and more.
    You have access to a team of agents who can help you answer questions and complete tasks.
    The browser the web_surfer accesses is also controlled by the user.
    You are primarily a planner, and so you can devise a plan to do anything. 


    The date today is: {date_today}


    First consider the following:

    - is the user request missing information and can benefit from clarification? For instance, if the user asks "book a flight", the request is missing information about the destination, date and we should ask for clarification before proceeding. Do not ask to clarify more than once, after the first clarification, give a plan.
    - is the user request something that can be answered from the context of the conversation history without executing code, or browsing the internet or executing other tools? If so, we should answer the question directly in as much detail as possible.
    When you answer without a plan and your answer includes factual information, make sure to say whether the answer was found using online search or from your own internal knowledge.


    Case 1: If the above is true, then we should provide our answer in the "response" field and set "needs_plan" to False.

    Case 2: If the above is not true, then we should consider devising a plan for addressing the request. If you are unable to answer a request, always try to come up with a plan so that other agents can help you complete the task.


    For Case 2:

    You have access to the following team members that can help you address the request each with unique expertise:

    {team}


    Your plan should should be a sequence of steps that will complete the task."""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep functionality
        step_types_section = SENTINEL_STEP_TYPES

        examples_section = (
            PLAN_EXAMPLES
            + "\n"
            + SENTINEL_STEP_EXAMPLES
            + "\n"
            + HELPFUL_HINTS_FOR_PLANNING
            + "\n"
            + HELPFUL_HINTS_FOR_PLANNING_SENTINEL
        )

    else:
        # Use original format from without SentinelPlanStep functionality
        step_types_section = """

            Each step should have a title and details field.

            The title should be a short one sentence description of the step.

            The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
            The details should start with a brief recap of the title. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step."""

        examples_section = PLAN_EXAMPLES + "\n" + HELPFUL_HINTS_FOR_PLANNING

    return base_message + step_types_section + examples_section


def get_orchestrator_system_message_planning_autonomous(
    sentinel_tasks_enabled: bool = False,
) -> str:
    base_message = """
    
    You are a helpful AI assistant named Magentic-UI built by Microsoft Research AI Frontiers.
    Your goal is to help the user with their request.
    You can complete actions on the web, complete actions on behalf of the user, execute code, and more.
    You have access to a team of agents who can help you answer questions and complete tasks.
    The browser the web_surfer accesses is also controlled by the user.
    You are primarily a planner, and so you can devise a plan to do anything. 


    The date today is: {date_today}

    You have access to the following team members that can help you address the request each with unique expertise:

    {team}


    Your plan should should be a sequence of steps that will complete the task."""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep functionality
        step_types_section = SENTINEL_STEP_TYPES

        examples_section = (
            PLAN_EXAMPLES
            + "\n"
            + SENTINEL_STEP_EXAMPLES
            + "\n"
            + HELPFUL_HINTS_FOR_PLANNING
            + "\n"
            + HELPFUL_HINTS_FOR_PLANNING_SENTINEL
        )

    else:
        # Use original format from without SentinelPlanStep functionality
        step_types_section = """

            Each step should have a title and details field.

            The title should be a short one sentence description of the step.

            The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
            The details should start with a brief recap of the title. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step."""

        examples_section = PLAN_EXAMPLES + "\n" + HELPFUL_HINTS_FOR_PLANNING

    return base_message + step_types_section + examples_section


def get_orchestrator_plan_prompt_json(sentinel_tasks_enabled: bool = False) -> str:
    """Get the orchestrator plan prompt in JSON format, with optional SentinelPlanStep support."""

    base_prompt = """
    
        You have access to the following team members that can help you address the request each with unique expertise:

        {team}

        Remember, there is no requirement to involve all team members -- a team member's particular expertise may not be needed for this task.

        {additional_instructions}
        When you answer without a plan and your answer includes factual information, make sure to say whether the answer was found using online search or from your own internal knowledge.

        Your plan should should be a sequence of steps that will complete the task."""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep functionality
        step_types_section = (
            SENTINEL_STEP_TYPES
            + """

            Output an answer in pure JSON format according to the following schema. The JSON object must be parsable as-is. DO NOT OUTPUT ANYTHING OTHER THAN JSON, AND DO NOT DEVIATE FROM THIS SCHEMA:

            The JSON object for a mixed plan with SentinelPlanStep and PlanStep should have the following structure:

            Note that in the structure below, the "step_type", "condition" and "sleep_duration" fields are only present for SentinelPlanStep steps, and not for PlanStep steps. 

        {{
            "response": "a complete response to the user request for Case 1.",
            "task": "a complete description of the task requested by the user",
            "plan_summary": "a complete summary of the plan if a plan is needed, otherwise an empty string",
            "needs_plan": boolean,
            "steps":
            [
            {{
                "title": "title of step 1",
                "details": "single instruction for the agent to perform",
                "agent_name": "the name of the agent that should complete the step",
                "step_type": "SentinelPlanStep",
                "condition": "number of times to repeat this step or a description of the completion condition",
                "sleep_duration": "amount of time represented in seconds to sleep between each iteration of the step",
            }},
            {{
                "title": "title of step 2",
                "details": "recap the title in one short sentence \\n remaining details of step 2",
                "agent_name": "the name of the agent that should complete the step",
            }},
            ...
            ]
        }}"""
        )

    else:
        # Use old format without SentinelPlanStep functionality
        step_types_section = """

    
            Each step should have a title, details and agent_name fields.

            The title should be a short one sentence description of the step.

            The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
            The details should start with a brief recap of the title in one short sentence. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step.
            The details should not be longer that 2 sentences.

            The agent_name should be the name of the agent that will execute the step. The agent_name should be one of the team members listed above.

            Output an answer in pure JSON format according to the following schema. The JSON object must be parsable as-is. DO NOT OUTPUT ANYTHING OTHER THAN JSON, AND DO NOT DEVIATE FROM THIS SCHEMA:

            The JSON object should have the following structure:

        {{
            "response": "a complete response to the user request for Case 1.",
            "task": "a complete description of the task requested by the user",
            "plan_summary": "a complete summary of the plan if a plan is needed, otherwise an empty string",
            "needs_plan": boolean,
            "steps":
            [
            {{
                "title": "title of step 1",
                "details": "recap the title in one short sentence \\n remaining details of step 1",
                "agent_name": "the name of the agent that should complete the step"
            }},
            {{
                "title": "title of step 2",
                "details": "recap the title in one short sentence \\n remaining details of step 2",
                "agent_name": "the name of the agent that should complete the step"
            }},
            ...
            ]
        }}"""

    return f"""
    
    {base_prompt}
    
    {step_types_section}
    """


def get_orchestrator_plan_replan_json(sentinel_tasks_enabled: bool = False) -> str:
    """Get the orchestrator replan prompt in JSON format, with optional SentinelPlanStep support."""

    replan_intro = """

    The task we are trying to complete is:

    {task}

    The plan we have tried to complete is:

    {plan}

    We have not been able to make progress on our task.

    We need to find a new plan to tackle the task that addresses the failures in trying to complete the task previously."""

    return replan_intro + get_orchestrator_plan_prompt_json(sentinel_tasks_enabled)


def get_orchestrator_progress_ledger_prompt(
    sentinel_tasks_enabled: bool = False,
) -> str:
    """Get the orchestrator progress ledger prompt, with optional SentinelPlanStep support."""

    base_prompt = """
Recall we are working on the following request:

{task}

This is our current plan:

{plan}

We are at step index {step_index} in the plan which is 

Title: {step_title}

Details: {step_details}

agent_name: {agent_name}

And we have assembled the following team:

{team}

The browser the web_surfer accesses is also controlled by the user.


To make progress on the request, please answer the following questions, including necessary reasoning:

    - is_current_step_complete: Is the current step complete? (True if complete, or False if the current step is not yet complete)
    - need_to_replan: Do we need to create a new plan? (True if user has sent new instructions and the current plan can't address it. True if the current plan cannot address the user request because we are stuck in a loop, facing significant barriers, or the current approach is not working. False if we can continue with the current plan. Most of the time we don't need a new plan.)
    - instruction_or_question: 
        Provide complete instructions to accomplish the current step with all context needed about the task and the plan. Provide a very detailed reasoning chain for how to complete the step.

        If the current step is a sentinel step, the instruction_or_question has to be the instruction to check the condition of the sentinel step and should not include information on how much to sleep or how many times to repeat the step.
        
        If the next agent is the user, pose it directly as a question that is short. Otherwise pose it as something you will do.
    
    - agent_name: Decide which team member should complete the current step from the list of team members: {names}. 
    - progress_summary: Summarize the progress made so far to the user in a short way (maximum two sentences, preferably one sentence) but providing enough information to the user to know what has been completed and what is going well and what is not going well if any.

Important: it is important to obey the user request and any messages they have sent previously.

Important: if the next agent is the user, the instruction_or_question must be a short question that the user can answer or an instruction the user can follow. Do not make it too complicated for the user.

{additional_instructions}

Please output an answer in pure JSON format according to the following schema. The JSON object must be parsable as-is. DO NOT OUTPUT ANYTHING OTHER THAN JSON, AND DO NOT DEVIATE FROM THIS SCHEMA:

    {{
        "is_current_step_complete": {{
            "reason": string,
            "answer": boolean
        }},
        "need_to_replan": {{
            "reason": string,
            "answer": boolean
        }},
        "instruction_or_question": {{
            "answer": string,
            "agent_name": string (the name of the agent that should complete the step from {names})
        }},
        "progress_summary": "a summary of the progress made so far in one or two sentences"

    }}
    """
    return base_prompt


def validate_ledger_json(json_response: Dict[str, Any], agent_names: List[str]) -> bool:
    """Validate ledger JSON response - same for both modes."""
    required_keys = [
        "is_current_step_complete",
        "need_to_replan",
        "instruction_or_question",
        "progress_summary",
    ]

    if not isinstance(json_response, dict):
        return False

    for key in required_keys:
        if key not in json_response:
            return False

    # Check structure of boolean response objects
    for key in [
        "is_current_step_complete",
        "need_to_replan",
    ]:
        if not isinstance(json_response[key], dict):
            return False
        if "reason" not in json_response[key] or "answer" not in json_response[key]:
            return False

    # Check instruction_or_question structure
    if not isinstance(json_response["instruction_or_question"], dict):
        return False
    if (
        "answer" not in json_response["instruction_or_question"]
        or "agent_name" not in json_response["instruction_or_question"]
    ):
        return False
    if json_response["instruction_or_question"]["agent_name"] not in agent_names:
        return False

    # Check progress_summary is a string
    if not isinstance(json_response["progress_summary"], str):
        return False

    return True


def validate_plan_json(
    json_response: Dict[str, Any], sentinel_tasks_enabled: bool = False
) -> bool:
    """Validate plan JSON response, with different requirements based on sentinel tasks mode."""
    if not isinstance(json_response, dict):
        return False
    required_keys = ["task", "steps", "needs_plan", "response", "plan_summary"]
    for key in required_keys:
        if key not in json_response:
            return False
    plan = json_response["steps"]
    for item in plan:
        if not isinstance(item, dict):
            return False

        # SentinelPlanStep requires sleep_duration and condition
        if sentinel_tasks_enabled:
            # this means it is a PlanStep since it doesn't have the step_type field
            if "step_type" not in item:
                if (
                    "title" not in item
                    or "details" not in item
                    or "agent_name" not in item
                ):
                    return False
            elif item["step_type"] == "SentinelPlanStep":
                # SentinelPlanStep requires sleep_duration and condition
                if (
                    "title" not in item
                    or "details" not in item
                    or "agent_name" not in item
                    or "sleep_duration" not in item
                    or "condition" not in item
                ):
                    return False
        # If we are not in sentinel tasks mode
        else:
            # PlanStep does not require sleep_duration or condition
            if "title" not in item or "details" not in item or "agent_name" not in item:
                return False
    return True
