from typing import Any, Dict

ORCHESTRATOR_SENTINEL_CONDITION_CHECK_PROMPT = """
You are evaluating whether a specific condition has been satisfied based on an agent's response in the last message.


The overall step we're trying to complete is:
{step_description}

Current sleep duration: {current_sleep_duration} seconds

Timing Information:
- Current time: {current_time}
- Time since started: {time_since_started:.1f} seconds
- Number of checks done so far: {checks_done}
- Time since last check: {time_since_last_check:.1f} seconds

Rules to follow:
- Finding information ABOUT the condition is NOT the same as the condition being met
- The condition must be CURRENTLY and DEFINITIVELY satisfied in the present moment
- If there was no effort made to check the condition, for instance because of CAPTCHAs, or there were other issues preventing the agent from completing the task, return error_encountered: true and condition_met: false
- If there is no point in checking again because the condition can never be met or the world will not change further, return condition_met: true. This will make the system move on to the next step. For example, if we are checking if a sports game score has changed, but the game is already over, return condition_met: true.


- Helpful hints:
    - If the agent provides a screenshot, use the screenshot to determine ground truth in addition to the agent's answer.

Condition to Evaluate:
'{condition}'


For the sleep_duration field, suggest an intelligent new sleep duration in seconds based on the current state and progress observed. Consider:
- If progress is rapid or near completion, suggest shorter intervals
- If little progress is observed, you may suggest longer intervals
- For countdown timers: sleep for roughly 80-90% of the remaining time (e.g., if 6 hours remain, sleep ~5 hours)
- For rapid countdowns (< 10 minutes remaining), use frequent checks (30-60 seconds)
- For gradual progress indicators (like download percentages), adjust based on completion velocity

* Explicit timing: "every 5 seconds" → 5, "check hourly" → 3600, "daily monitoring" → 86400 and so on
* the sleep duration should be based on the specific monitoring check and reasonable expectations on when a change might occur. It is best to have shorter durations which can then be adjusted later if needed.
Examples:
- checking for social media posts: based on frequency of poster, determine the right interval (e.g., every 10 minutes for active users, every few hours for less active)
A good default if there are no good contextual clues for checking is usually 1 minute (60 seconds)  or 5 minutes (300 seconds).

- If no clear pattern emerges, return the current sleep duration

Answer in this exact JSON format:

{{
    "reason": "very short explanation (short sentence) why the condition is or isn't met",
    "condition_met": boolean,
    "sleep_duration_reason": "Detailed explanation for the suggested sleep duration",
    "sleep_duration": suggested_sleep_duration_in_seconds,
    "error_encountered": boolean
}}

Only output the JSON object and nothing else.
"""

SENTINEL_STEP_TYPES = """

# Step Types

There are two types of plan steps:

1) PlanStep: Short-term, immediate tasks that complete quickly.
 
Use PlanStep for:
- Immediate actions (e.g., "send an email", "create a file")
- One-time information gathering (e.g., "find restaurant menus")
- Tasks that can be completed in a single execution cycle

2) SentinelPlanStep: Long-running, periodic, or recurring tasks. These steps involve:
- Monitoring conditions over extended time periods
- Waiting for external events or thresholds to be met
- Tasks that require periodic execution (e.g., "check every day", "monitor constantly")


Use **SentinelPlanStep** when the step involves:
- Waiting for a condition to be met (e.g., "wait until I have 2000 followers")
- Continuous monitoring (e.g., "constantly check for new mentions")
- Periodic tasks (e.g., "check daily", "monitor weekly")
- An action that repeats a specific number of times (e.g., "check 5 times with 30s between each check")

In most cases do not create multiple separate steps for the same repeated action.
    
If a task needs to be repeated multiple times (e.g., "check 5 times with 30s between each", "verify twice with 10s intervals"), you MUST create EXACTLY ONE SentinelPlanStep with the appropriate condition value, NOT multiple separate steps. 

GOOD: Creating ONE SentinelPlanStep with condition: 2 and sleep_duration: 10
BAD: Creating "Step 1: Check first time", "Step 2: Check second time"  

The condition parameter handles ALL repetition automatically - the system will execute the same step multiple times based on the condition value.

However, if you need to two different sleep durations or two different conditions, you can create multiple SentinelPlanSteps.
For instance, if we want to check the score of a game that starts in 6 hours, we can create two SentinelPlanSteps:
- SentinelPlanStep 1: sleep_duration: 300, condition: "the game has started"
- SentinelPlanStep 2: sleep_duration: 30, condition: "the score has changed"
Or something similar.

# Step Format

Each step should have a title, details, and agent_name field.

- title (string): The title should be a short one sentence description of the step.

For **PlanStep** ONLY:
- details (string):  The details should start with a brief recap of the title. We then follow it with a new line. We then add any additional details without repeating information from the title. We should be concise but mention all crucial details to allow the human to verify the step.

For **SentinelPlanStep*:
- details (string): The details field should be the SINGLE instruction the agent will do. 
    * For instance, if the sentinel step is "check the magentic-ui repo until it has 7k stars", the details field should be "check the number of stars of magentic-ui repo"
    * If the task requires checking a specific URL, website, or repository, INCLUDE THE FULL URL in the details field. For example: "check the number of stars of https://github.com/magentic-ai/magentic-ui repo" or "check if https://example.com/api/status returns a 200 status code"
    * (IMPORTANT) DO NOT INCLUDE ANY MENTION OF MONITORING OR WAITING IN THE DETAILS FIELD. The system will handle the monitoring and waiting based on the sleep_duration and condition fields.
    
- agent_name (string): the agent_name should be the name of the agent that will execute the step. 

For **SentinelPlanStep** ONLY, you should also include step_type, sleep_duration and condition fields:
- **step_type** (string): Should be "SentinelPlanStep".

- **sleep_duration** (integer): Number of seconds to wait between checks. Intelligently extract timing from the user's request:
    * Explicit timing: "every 5 seconds" → 5, "check hourly" → 3600, "daily monitoring" → 86400 and so on
    * the sleep duration should be based on the specific monitoring check and reasonable expectations on when a change might occur. It is best to have shorter durations which can then be adjusted later if needed.
    Examples:
    - checking for social media posts: based on frequency of poster, determine the right interval (e.g., every 10 minutes for active users, every few hours for less active)
    A good defaul if there are no good contextual clues for checking is usually 1 minute (60 seconds)  or 5 minutes (300 seconds).

- **condition** (integer or string): Either:
    * Integer: Specific number of times to execute (e.g., "check 5 times" → 5)
    * String: Natural language description of the completion condition (e.g., "until star count reaches 2000")
    * For String conditions, this should be a verifiable statement that can be programmatically checked against the output of an agent's action. The condition will be evaluated by another LLM based on the agent's response.
    - GOOD: "condition:" "The response contains the text 'Download complete.'"
    - GOOD: "condition:" "The webpage title is 'Stock Price Update'."
    - BAD: "condition:" "Wait until the user says to stop." (The system cannot check this)
    - BAD: "condition:" "Monitor for 5 minutes." (The system handles time, but the condition should be about the *result* of an action)
    * If not specified, use a descriptive condition from the task

For **PlanStep** you should NOT include step_type, sleep_duration or condition fields, only title, details, and agent_name.

"""


SENTINEL_STEP_EXAMPLES = """
Example 4:

User request: "Browse to the magentic-ui GitHub repository a total of 5 times and report the number of stars at each check. Sleep 30 seconds between each check."

Step 1:
- title: "Monitor GitHub repository stars with 5 repeated checks"
- details: "Visit the magentic-ui GitHub repository and record the star count"
- agent_name: "web_surfer"
- step_type: "SentinelPlanStep"
- sleep_duration: 30
- condition: 5

Example 5:

User request: "Tell me when there is a new issue in the microsoft/magentic-ui repo that is not spam and genuine. Then try to write a summary of the issue."
Step 1:
- title: "Record current issues in microsoft/magentic-ui repo"
- details: "List all current open issues in the microsoft/magentic-ui GitHub repository
- agent_name: "web_surfer"
Step 2:
- title: "Monitor for new genuine issues in microsoft/magentic-ui repo"
- details: "Check for new open issues in the microsoft/magentic-ui GitHub repository
- agent_name: "web_surfer"
- step_type: "SentinelPlanStep"
- sleep_duration: 1200
- condition: "a new genuine (non-spam) issue is found"
Step 3:
- title: "Summarize the new issue"
- details: "Write a summary of the newly found issue"
- agent_name: "coder_agent"

Example 6: 

User request: "Keep monitoring the news for events about new earthquakes in california"
Step 1:
- title: "Monitor news for new earthquake events in California"
- details: "Check news websites and sources for reports of new earthquake events in California"
- agent_name: "web_surfer"
- step_type: "SentinelPlanStep"
- sleep_duration: 300
- condition: "a new earthquake event in California is reported"
"""

HELPFUL_HINTS_FOR_PLANNING_SENTINEL = """
- Carefully classify each step as either SentinelPlanStep or PlanStep based on whether it requires long-term monitoring, waiting, or periodic execution.
- For SentinelPlanStep timing: Always analyze the user's request for timing clues ("daily", "every hour", "constantly", "until X happens") and choose appropriate sleep_duration and condition values. Consider the nature of the task to avoid being too aggressive with checking frequency.
- If the condition field for a SentinelPlanStep is a string, it should be verifiable by the system based on the agent's response. It should describe a specific outcome that can be checked programmatically.
"""


def validate_sentinel_condition_check_json(json_response: Dict[str, Any]) -> bool:
    """Validate the JSON response for the sentinel condition check."""
    if not isinstance(json_response, dict):
        return False
    if "condition_met" not in json_response:
        return False
    if "reason" not in json_response:
        return False
    if "sleep_duration" not in json_response:
        return False
    if "sleep_duration_reason" not in json_response:
        return False
    if "error_encountered" not in json_response:
        return False
    return True
