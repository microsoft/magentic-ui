from typing import Any, Dict, List

class PromptHolder:
    """A container to hold a prompt string that can be updated at runtime."""

    def __init__(self, value: str = ""):
        self.value = value

    def format(self, *args: Any, **kwargs: Any) -> str:
        """Allows the holder to be used like a string with .format()."""
        return self.value.format(*args, **kwargs)


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
    You are primarly a planner, and so you can devise a plan to do anything. 


    The date today is: {date_today}


    First consider the following:

    - is the user request missing information and can benefit from clarification? For instance, if the user asks "book a flight", the request is missing information about the destination, date and we should ask for clarification before proceeding. Do not ask to clarify more than once, after the first clarification, give a plan.
    - is the user request something that can be answered from the context of the conversation history without executing code, or browsing the internet or executing other tools? If so, we should answer the question directly in as much detail as possible.


    Case 1: If the above is true, then we should provide our answer in the "response" field and set "needs_plan" to False.

    Case 2: If the above is not true, then we should consider devising a plan for addressing the request. If you are unable to answer a request, always try to come up with a plan so that other agents can help you complete the task.


    For Case 2:

    You have access to the following team members that can help you address the request each with unique expertise:

    {team}


    Your plan should should be a sequence of steps that will complete the task."""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep functionality
        step_types_section = """

            ## Step Types

            There are two types of plan steps:

            **[PlanStep]**: Short-term, immediate tasks that complete quickly (within seconds to minutes). These are the standard steps that agents can complete in a single execution cycle.

            **[SentinelPlanStep]**: Long-running, periodic, or recurring tasks that may take days, weeks, or months to complete. These steps involve:
            - Monitoring conditions over extended time periods
            - Waiting for external events or thresholds to be met
            - Repeatedly checking the same condition until satisfied
            - Tasks that require periodic execution (e.g., "check every day", "monitor constantly")

            ## How to Classify Steps

            Use **SentinelPlanStep** when the step involves:
            - Waiting for a condition to be met (e.g., "wait until I have 2000 followers")
            - Continuous monitoring (e.g., "constantly check for new mentions")
            - Periodic tasks (e.g., "check daily", "monitor weekly")
            - Tasks that span extended time periods
            - Tasks with timing dependencies that can't be completed immediately

            Use **PlanStep** for:
            - Immediate actions (e.g., "send an email", "create a file")
            - One-time information gathering (e.g., "find restaurant menus")
            - Tasks that can be completed in a single execution cycle

            Each step should have a title, details, step_type, and agent_name field.

            For **SentinelPlanStep** only, you should also include:
            - **sleep_duration** (integer): Number of seconds to wait between checks. Extract this from the user's request if they specify timing (e.g., "2 seconds", "5s", "wait 3 seconds"). If not specified, omit this field and a default will be used.
            - **counter** (integer or string): Number of iterations or descriptive text like "until goal is met".

            The title should be a short one sentence description of the step.

            The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
            The details should start with a brief recap of the title. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step.

            The step_type should be either "SentinelPlanStep" or "PlanStep" based on the classification above."""

        examples_section = """

            Example 1:

            User request: "Report back the menus of three restaurants near the zipcode 98052"

            Step 1:
            - title: "Locate the menu of the first restaurant"
            - details: "Locate the menu of the first restaurant. \\n Search for highly-rated restaurants in the 98052 area using Bing, select one with good reviews and an accessible menu, then extract and format the menu information for reporting."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"

            Step 2:
            - title: "Locate the menu of the second restaurant"
            - details: "Locate the menu of the second restaurant. \\n After excluding the first restaurant, search for another well-reviewed establishment in 98052, ensuring it has a different cuisine type for variety, then collect and format its menu information."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"

            Step 3:
            - title: "Locate the menu of the third restaurant"
            - details: "Locate the menu of the third restaurant. \\n Building on the previous searches but excluding the first two restaurants, find a third establishment with a distinct cuisine type, verify its menu is available online, and compile the menu details."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"


            Example 2:

            User request: "Execute the starter code for the autogen repo"

            Step 1:
            - title: "Locate the starter code for the autogen repo"
            - details: "Locate the starter code for the autogen repo. \\n Search for the official AutoGen repository on GitHub, navigate to their examples or getting started section, and identify the recommended starter code for new users."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"

            Step 2:
            - title: "Execute the starter code for the autogen repo"
            - details: "Execute the starter code for the autogen repo. \\n Set up the Python environment with the correct dependencies, ensure all required packages are installed at their specified versions, and run the starter code while capturing any output or errors."
            - step_type: "PlanStep"
            - agent_name: "coder_agent"


            Example 3:

            User request: "Wait until I have 2000 Instagram followers to send a message to Nike asking for a partnership"

            Step 1:
            - title: "Monitor Instagram follower count until reaching 2000 followers"
            - details: "Monitor Instagram follower count until reaching 2000 followers. \\n Periodically check the user's Instagram account follower count, sleeping between checks to avoid excessive API calls, and continue monitoring until the 2000 follower threshold is reached."
            - step_type: "SentinelPlanStep"
            - agent_name: "web_surfer"

            Step 2:
            - title: "Send partnership message to Nike"
            - details: "Send partnership message to Nike. \\n Once the follower threshold is met, compose and send a professional partnership inquiry message to Nike through their official channels."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"


            Example 4:

            User request: "Constantly check the internet for resources describing Ayrton Senna and add these to a local txt file"

            Step 1:
            - title: "Periodically search the internet for new resources about Ayrton Senna"
            - details: "Periodically search the internet for new resources about Ayrton Senna. \\n Repeatedly search the web for new articles, posts, or mentions, monitoring for new information over time and identifying resources that haven't been previously collected."
            - step_type: "SentinelPlanStep"
            - agent_name: "web_surfer"

            Step 2:
            - title: "Append new resources to a local txt file"
            - details: "Append new resources to a local txt file. \\n Each time a new resource is found, add its details to a local txt file, ensuring a cumulative and organized record of relevant resources."
            - step_type: "PlanStep"  
            - agent_name: "coder_agent"


            Example 5:

            User request: "Browse to the magentic-ui GitHub repository a total of 5 times and report the number of stars at each check"

            Step 1:
            - title: "Monitor GitHub repository stars with 5 repeated checks"
            - details: "Monitor GitHub repository stars with 5 repeated checks. \\n Visit the magentic-ui GitHub repository 5 times, recording the star count at each visit and compiling a report of all star counts collected during the monitoring period."
            - step_type: "SentinelPlanStep"
            - counter: 5
            - agent_name: "web_surfer"

            Step 2:
            - title: "Say hi to the user using code"
            - details: "Say hi to the user using the coder agent. \\n Execute code to generate a greeting message."
            - step_type: "PlanStep"
            - agent_name: "coder_agent"


            Example 6:

            User request: "Can you paraphrase the following sentence: 'The quick brown fox jumps over the lazy dog'"

            You should not provide a plan for this request. Instead, just answer the question directly.


            Example 7:

            User request: "Create a plan where the sentinel agent sleeps for 3 times for 2 seconds each"

            Step 1:
            - title: "Execute sleep cycle with 3 iterations of 2 seconds each"
            - details: "Execute sleep cycle with 3 iterations of 2 seconds each. \\n Perform a monitoring task that sleeps for 2 seconds per iteration, repeating this process exactly 3 times before completing."
            - step_type: "SentinelPlanStep"
            - counter: 3
            - sleep_duration: 2
            - agent_name: "sentinel_agent"


            Helpful tips:
            - If the plan needs information from the user, try to get that information before creating the plan.
            - When creating the plan you only need to add a step to the plan if it requires a different agent to be completed, or if the step is very complicated and can be split into two steps.
            - Remember, there is no requirement to involve all team members -- a team member's particular expertise may not be needed for this task.
            - Aim for a plan with the least number of steps possible.
            - Use a search engine or platform to find the information you need. For instance, if you want to look up flight prices, use a flight search engine like Bing Flights. However, your final answer should not stop with a Bing search only.
            - If there are images attached to the request, use them to help you complete the task and describe them to the other agents in the plan.
            - Carefully classify each step as either SentinelPlanStep or PlanStep based on whether it requires long-term monitoring, waiting, or periodic execution.
        """

    else:
        # Use original format from without SentinelPlanStep functionality
        step_types_section = """

            Each step should have a title and details field.

            The title should be a short one sentence description of the step.

            The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
            The details should start with a brief recap of the title. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step."""

        examples_section = """

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

            User request: "On which social media platform does Autogen have the most followers?"

            Step 1:
            - title: "Find all social media platforms that Autogen is on"
            - details: "Find all social media platforms that Autogen is on. \\n Search for AutoGen's official presence across major platforms like GitHub, Twitter, LinkedIn, and others, then compile a comprehensive list of their verified accounts."
            - agent_name: "web_surfer"

            Step 2:
            - title: "Find the number of followers for each social media platform"
            - details: "Find the number of followers for each social media platform. \\n For each platform identified, visit AutoGen's official profile and record their current follower count, ensuring to note the date of collection for accuracy."
            - agent_name: "web_surfer"

            Step 3:
            - title: "Find the number of followers for the remaining social media platform that Autogen is on"
            - details: "Find the number of followers for the remaining social media platforms. \\n Visit the remaining platforms and record their follower counts."
            - agent_name: "web_surfer"


            Example 4:

            User request: "Can you paraphrase the following sentence: 'The quick brown fox jumps over the lazy dog'"

            You should not provide a plan for this request. Instead, just answer the question directly.


            Helpful tips:
            - If the plan needs information from the user, try to get that information before creating the plan.
            - When creating the plan you only need to add a step to the plan if it requires a different agent to be completed, or if the step is very complicated and can be split into two steps.
            - Remember, there is no requirement to involve all team members -- a team member's particular expertise may not be needed for this task.
            - Aim for a plan with the least number of steps possible.
            - Use a search engine or platform to find the information you need. For instance, if you want to look up flight prices, use a flight search engine like Bing Flights. However, your final answer should not stop with a Bing search only.
            - If there are images attached to the request, use them to help you complete the task and describe them to the other agents in the plan.
        """

    return base_message + step_types_section + examples_section


def get_orchestrator_system_message_planning_autonomous(
    sentinel_tasks_enabled: bool = False,
) -> str:
    """Get the autonomous orchestrator system message for planning, with optional SentinelPlanStep support."""

    base_message = """
    
    You are a helpful AI assistant named Magentic-UI built by Microsoft Research AI Frontiers.
    Your goal is to help the user with their request.
    You can complete actions on the web, complete actions on behalf of the user, execute code, and more.
    You have access to a team of agents who can help you answer questions and complete tasks.
    You are primarly a planner, and so you can devise a plan to do anything. 

    The date today is: {date_today}

    You have access to the following team members that can help you address the request each with unique expertise:

    {team}

    Your plan should should be a sequence of steps that will complete the task."""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep functionality
        step_types_section = """

            ## Step Types

            There are two types of plan steps:

            **[PlanStep]**: Short-term, immediate tasks that complete quickly (within minutes to hours). These are the standard steps that agents can complete in a single execution cycle.

            **[SentinelPlanStep]**: Long-running, periodic, or recurring tasks that may take days, weeks, or months to complete. These steps involve:
            - Monitoring conditions over extended time periods
            - Waiting for external events or thresholds to be met
            - Repeatedly checking the same condition until satisfied
            - Tasks that require periodic execution (e.g., "check every day", "monitor constantly")

            ## How to Classify Steps

            Use **[SentinelPlanStep]** when the step involves:
            - Waiting for a condition to be met (e.g., "wait until I have 2000 followers")
            - Continuous monitoring (e.g., "constantly check for new mentions")
            - Periodic tasks (e.g., "check daily", "monitor weekly")
            - Tasks that span extended time periods
            - Tasks with timing dependencies that can't be completed immediately

            Use **[PlanStep]** for:
            - Immediate actions (e.g., "send an email", "create a file")
            - One-time information gathering (e.g., "find restaurant menus")
            - Tasks that can be completed in a single execution cycle"""

        step_fields_section = """
            Each step should have a title, details, step_type, and agent_name field."""

        step_format_section = """
            The step_type should be either "SentinelPlanStep" or "PlanStep" based on the classification above."""

        examples_section = """
            Example 1:

            User request: "Report back the menus of three restaurants near the zipcode 98052"

            Step 1:
            - title: "Locate the menu of the first restaurant"
            - details: "Locate the menu of the first restaurant. \\n Search for top-rated restaurants in the 98052 area, select one with good reviews and an accessible menu, then extract and format the menu information."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"

            Step 2:
            - title: "Locate the menu of the second restaurant"
            - details: "Locate the menu of the second restaurant. \\n After excluding the first restaurant, search for another well-reviewed establishment in 98052, ensuring it has a different cuisine type for variety, then collect and format its menu information."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"

            Step 3:
            - title: "Locate the menu of the third restaurant"
            - details: "Locate the menu of the third restaurant. \\n Building on the previous searches but excluding the first two restaurants, find a third establishment with a distinct cuisine type, verify its menu is available online, and compile the menu details."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"


            Example 2:

            User request: "Execute the starter code for the autogen repo"

            Step 1:
            - title: "Locate the starter code for the autogen repo"
            - details: "Locate the starter code for the autogen repo. \\n Search for the official AutoGen repository on GitHub, navigate to their examples or getting started section, and identify the recommended starter code for new users."
            - step_type: "PlanStep"
            - agent_name: "web_surfer"

            Step 2:
            - title: "Execute the starter code for the autogen repo"
            - details: "Execute the starter code for the autogen repo. \\n Set up the Python environment with the correct dependencies, ensure all required packages are installed at their specified versions, and run the starter code while capturing any output or errors."
            - step_type: "PlanStep"
            - agent_name: "coder_agent"


            Example 3:

            User request: "Constantly check the internet for resources describing Ayrton Senna and add these to a local txt file"

            Step 1:
            - title: "Periodically search the internet for new resources about Ayrton Senna"
            - details: "Periodically search the internet for new resources about Ayrton Senna. \\n Repeatedly search the web for new articles, posts, or mentions, monitoring for new information over time and identifying resources that haven't been previously collected."
            - step_type: "SentinelPlanStep"
            - agent_name: "web_surfer"
            - sleep_duration: 300 # 5 minutes
            - counter: 10

            Step 2:
            - title: "Append new resources to a local txt file"
            - details: "Append new resources to a local txt file. \\n Each time a new resource is found, add its details to a local txt file, ensuring a cumulative and organized record of relevant resources."
            - step_type: "PlanStep"
            - agent_name: "coder_agent"
            """

        helpful_tips = """
        
            Helpful tips:
            - When creating the plan you only need to add a step to the plan if it requires a different agent to be completed, or if the step is very complicated and can be split into two steps.
            - Aim for a plan with the least number of steps possible.
            - Use a search engine or platform to find the information you need. For instance, if you want to look up flight prices, use a flight search engine like Bing Flights. However, your final answer should not stop with a Bing search only.
            - If there are images attached to the request, use them to help you complete the task and describe them to the other agents in the plan.
            - Carefully classify each step as either SentinelPlanStep or PlanStep based on whether it requires long-term monitoring, waiting, or periodic execution."""

    else:
        # Use original format without SentinelPlanStep functionality
        step_types_section = ""
        step_fields_section = "Each step should have a title and details field."
        step_format_section = ""

        examples_section = """
            Example 1:

            User request: "Report back the menus of three restaurants near the zipcode 98052"

            Step 1:
            - title: "Locate the menu of the first restaurant"
            - details: "Locate the menu of the first restaurant. \\n Search for top-rated restaurants in the 98052 area, select one with good reviews and an accessible menu, then extract and format the menu information."
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

            User request: "Constantly check the internet for resources describing Ayrton Senna and add these to a local txt file"

            Step 1:
            - title: "Periodically search the internet for new resources about Ayrton Senna"
            - details: "Periodically search the internet for new resources about Ayrton Senna. \\n Repeatedly search the web for new articles, posts, or mentions, monitoring for new information over time and identifying resources that haven't been previously collected."
            - agent_name: "web_surfer"

            Step 2:
            - title: "Append new resources to a local txt file"
            - details: "Append new resources to a local txt file. \\n Each time a new resource is found, add its details to a local txt file, ensuring a cumulative and organized record of relevant resources."
            - agent_name: "coder_agent\""""

        helpful_tips = """
        
            Helpful tips:
            
            - When creating the plan you only need to add a step to the plan if it requires a different agent to be completed, or if the step is very complicated and can be split into two steps.
            - Aim for a plan with the least number of steps possible.
            - Use a search engine or platform to find the information you need. For instance, if you want to look up flight prices, use a flight search engine like Bing Flights. However, your final answer should not stop with a Bing search only.
            - If there are images attached to the request, use them to help you complete the task and describe them to the other agents in the plan."""

    # Common sections
    description_section = """
        The title should be a short one sentence description of the step.

        The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
        The details should start with a brief recap of the title. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step."""

    return f"""
        {base_message}        
        {step_types_section}
        {step_fields_section}
        {description_section}
        {step_format_section}
        {examples_section}
        {helpful_tips}
        """


def get_orchestrator_plan_prompt_json(sentinel_tasks_enabled: bool = False) -> str:
    """Get the orchestrator plan prompt in JSON format, with optional SentinelPlanStep support."""

    base_prompt = """
    
        You have access to the following team members that can help you address the request each with unique expertise:

        {team}

        Remember, there is no requirement to involve all team members -- a team member's particular expertise may not be needed for this task.

        {additional_instructions}

        Your plan should should be a sequence of steps that will complete the task."""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep functionality
        step_types_section = """

            ## Step Types

            There are two types of plan steps:

            **[PlanStep]**: Short-term, immediate tasks that complete quickly (within seconds to minutes). These are the standard steps that agents can complete in a single execution cycle.

            **[SentinelPlanStep]**: Long-running, periodic, or recurring tasks that may take days, weeks, or months to complete. These steps involve:
            - Monitoring conditions over extended time periods
            - Waiting for external events or thresholds to be met
            - Repeatedly checking the same condition until satisfied
            - Tasks that require periodic execution (e.g., "check every day", "monitor constantly")

            ## How to Classify Steps

            Use **[SentinelPlanStep]** when the step involves:
            - Waiting for a condition to be met (e.g., "wait until I have 2000 followers")
            - Continuous monitoring (e.g., "constantly check for new mentions")
            - Periodic tasks (e.g., "check daily", "monitor weekly")
            - Tasks that span extended time periods
            - Tasks with timing dependencies that can't be completed immediately

            Use **[PlanStep]** for:
            - Immediate actions (e.g., "send an email", "create a file")
            - One-time information gathering (e.g., "find restaurant menus")
            - Tasks that can be completed in a single execution cycle"""

        json_schema = """
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
                "step_type": "PlanStep or SentinelPlanStep based on the classification above",
                "counter": "number of times to repeat this step",
                "sleep_duration": "amount of time represented in seconds to sleep between each iteration of the step",
                "agent_name": "the name of the agent that should complete the step"
            }},
            {{
                "title": "title of step 2",
                "details": "recap the title in one short sentence \\n remaining details of step 2",
                "step_type": "PlanStep or SentinelPlanStep based on the classification above",
                "counter": "number of times to repeat this step",
                "sleep_duration": "amount of time represented in seconds to sleep between each iteration of the step",
                "agent_name": "the name of the agent that should complete the step"
            }},
            ...
            ]
        }}"""

    else:
        # Use old format without SentinelPlanStep functionality
        step_types_section = ""

        json_schema = """{{
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

    description_section = """
    
        Each step should have a title and details field.

        The title should be a short one sentence description of the step.

        The details should be a detailed description of the step. The details should be concise and directly describe the action to be taken.
        The details should start with a brief recap of the title in one short sentence. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step.
        The details should not be longer that 2 sentences.

        Output an answer in pure JSON format according to the following schema. The JSON object must be parsable as-is. DO NOT OUTPUT ANYTHING OTHER THAN JSON, AND DO NOT DEVIATE FROM THIS SCHEMA:

        The JSON object should have the following structure

        """

    return f"""
    
    {base_prompt}
    
    {step_types_section}

    {description_section}

    {json_schema}
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

    if sentinel_tasks_enabled:
        replan_intro += """

    When creating the new plan, make sure to properly classify each step as either PlanStep or SentinelPlanStep based on whether it requires long-term monitoring, waiting, or periodic execution."""

    return replan_intro + get_orchestrator_plan_prompt_json(sentinel_tasks_enabled)


def get_orchestrator_progress_ledger_prompt(
    sentinel_tasks_enabled: bool = False,
) -> str:
    """Get the orchestrator progress ledger prompt, with optional SentinelPlanStep support."""

    base_prompt = """Recall we are working on the following request:

    {task}

    This is our current plan:

    {plan}

    We are at step index {step_index} in the plan which is 

    Title: {step_title}

    Details: {step_details}"""

    if sentinel_tasks_enabled:
        # Add SentinelPlanStep-aware section
        step_type_section = """

        Step Type: {step_type}

        agent_name: {agent_name}

        And we have assembled the following team:

        {team}

        The browser the web_surfer accesses is also controlled by the user.

        IMPORTANT: The current step is a {step_type}. This affects how you should handle completion:

        ## For PlanStep:
        - These are immediate, short-term tasks that should complete quickly
        - Mark as complete when the task has been accomplished
        - Provide standard instructions to the agent
        - Progress to the next step once the task is done

        ## For SentinelPlanStep:
        - These are long-running monitoring or waiting tasks
        - ONLY mark as complete when the monitoring condition is definitively met
        - If the condition is not yet met, the step should remain incomplete
        - Provide instructions to check the specific condition being monitored
        - The step will automatically wait and retry checking the condition periodically
        - Examples of SentinelPlanStep conditions:
        * "Wait until follower count reaches 2000" - only complete when count >= 2000
        * "Monitor for new mentions" - only complete when new mentions are found
        * "Check daily for updates" - only complete when update condition is satisfied"""

        instruction_guidance = """    - instruction_or_question: Provide complete instructions to accomplish the current step with all context needed about the task and the plan. 
            * For PlanStep: Provide detailed instructions for the immediate task
            * For SentinelPlanStep: Provide instructions to check the specific monitoring condition
            Provide a very detailed reasoning chain for how to complete the step. If the next agent is the user, pose it directly as a question. Otherwise pose it as something you will do."""

        completion_guidance = """    - is_current_step_complete: Is the current step complete? 
            * For PlanStep: True if the immediate task is done
            * For SentinelPlanStep: True ONLY if the monitoring condition is definitively met"""

    else:
        # Use old format without SentinelPlanStep functionality
        step_type_section = """

            agent_name: {agent_name}

            And we have assembled the following team:

            {team}

            The browser the web_surfer accesses is also controlled by the user.
        """
        instruction_guidance = """    - instruction_or_question: Provide complete instructions to accomplish the current step with all context needed about the task and the plan. Provide a very detailed reasoning chain for how to complete the step. If the next agent is the user, pose it directly as a question. Otherwise pose it as something you will do."""

        completion_guidance = """    - is_current_step_complete: Is the current step complete? (True if complete, or False if the current step is not yet complete)"""

    # Create the questions section based on whether sentinel tasks are enabled
    questions_section = f"""

    To make progress on the request, please answer the following questions, including necessary reasoning:

    {completion_guidance}
        - need_to_replan: Do we need to create a new plan? (True if user has sent new instructions and the current plan can't address it. True if the current plan cannot address the user request because we are stuck in a loop, facing significant barriers, or the current approach is not working. False if we can continue with the current plan. Most of the time we don't need a new plan.)
    {instruction_guidance}
        - agent_name: Decide which team member should complete the current step from the list of team members: {{names}}. 
        - progress_summary: Summarize all the information that has been gathered so far that would help in the completion of the plan including ones not present in the collected information. This should include any facts, educated guesses, or other information that has been gathered so far. Maintain any information gathered in the previous steps.

    Important: it is important to obey the user request and any messages they have sent previously.

    {{additional_instructions}}

    Please output an answer in pure JSON format according to the following schema. The JSON object must be parsable as-is. DO NOT OUTPUT ANYTHING OTHER THAN JSON, AND DO NOT DEVIATE FROM THIS SCHEMA:

    {{{{
        "is_current_step_complete": {{{{
            "reason": string,
            "answer": boolean
        }}}},
        "need_to_replan": {{{{
            "reason": string,
            "answer": boolean
        }}}},
        "instruction_or_question": {{{{
            "answer": string,
            "agent_name": string (the name of the agent that should complete the step from {{names}})
        }}}},
        "progress_summary": "a summary of the progress made so far"

    }}}}"""

    return base_prompt + step_type_section + questions_section


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


# Validate the plan JSON response, with different requirements based on the step type
def validate_plan_json_with_mode(
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

        if sentinel_tasks_enabled:
            # New format requires step_type
            if (
                "title" not in item
                or "details" not in item
                or "agent_name" not in item
                or "step_type" not in item
                or "sleep_duration" not in item
                or "counter" not in item
            ):
                return False
            # Validate step_type is one of the allowed values
            if item["step_type"] not in ["PlanStep", "SentinelPlanStep"]:
                return False
        else:
            # Old format doesn't require step_type
            if "title" not in item or "details" not in item or "agent_name" not in item:
                return False
    return True


def initialize_prompts(sentinel_tasks_enabled: bool) -> None:
    """
    Initializes or updates the global prompt constants based on runtime configuration.
    """
    global ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING, ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING_AUTONOMOUS
    global ORCHESTRATOR_PLAN_PROMPT_JSON, ORCHESTRATOR_PLAN_REPLAN_JSON
    global ORCHESTRATOR_PROGRESS_LEDGER_PROMPT, _SENTINEL_TASKS_ENABLED

    _SENTINEL_TASKS_ENABLED = sentinel_tasks_enabled
    ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING.value = get_orchestrator_system_message_planning(
        sentinel_tasks_enabled
    )
    ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING_AUTONOMOUS.value = (
        get_orchestrator_system_message_planning_autonomous(sentinel_tasks_enabled)
    )
    ORCHESTRATOR_PLAN_PROMPT_JSON.value = get_orchestrator_plan_prompt_json(
        sentinel_tasks_enabled
    )
    ORCHESTRATOR_PLAN_REPLAN_JSON.value = get_orchestrator_plan_replan_json(
        sentinel_tasks_enabled
    )
    ORCHESTRATOR_PROGRESS_LEDGER_PROMPT.value = get_orchestrator_progress_ledger_prompt(
        sentinel_tasks_enabled
    )


# =============================================================================
# Constants that don't change between modes
# =============================================================================

# The specific format of the system message for the agents to follow
ORCHESTRATOR_SYSTEM_MESSAGE_EXECUTION = """
    You are a helpful AI assistant named Magentic-UI built by Microsoft Research AI Frontiers.
    Your goal is to help the user with their request.
    You can complete actions on the web, complete actions on behalf of the user, execute code, and more.
    The browser the web_surfer accesses is also controlled by the user.
    You have access to a team of agents who can help you answer questions and complete tasks.

    The date today is: {date_today}
"""

# The specific format of the final answer to the user once the task is complete
ORCHESTRATOR_FINAL_ANSWER_PROMPT = """
    We are working on the following task:

    {task}

    The above messages contain the steps that took place to complete the task.

    Based on the information gathered, provide a final response to the user in response to the task.

    Make sure the user can easily verify your answer, include links if there are any.

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


# =============================================================================
# Keeps the same variable names as _prompts.py for backward compatibility
# By default, sentinel tasks are disabled to keep original Magentic UI behavior
# =============================================================================

# This global flag will be updated by the initializer
_SENTINEL_TASKS_ENABLED = False

# The capitalized variables are now instances of PromptHolder
ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING = PromptHolder()
ORCHESTRATOR_SYSTEM_MESSAGE_PLANNING_AUTONOMOUS = PromptHolder()
ORCHESTRATOR_PLAN_PROMPT_JSON = PromptHolder()
ORCHESTRATOR_PLAN_REPLAN_JSON = PromptHolder()
ORCHESTRATOR_PROGRESS_LEDGER_PROMPT = PromptHolder()

# Initialize prompts with the default value (False)
initialize_prompts(False)


# Validation function with compatibility layer
def validate_plan_json(json_response: Dict[str, Any]) -> bool:
    """Compatibility wrapper for validate_plan_json with default sentinel tasks setting."""
    return validate_plan_json_with_mode(json_response, _SENTINEL_TASKS_ENABLED)
