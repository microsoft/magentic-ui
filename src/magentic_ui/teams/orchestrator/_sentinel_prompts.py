from typing import Any, Dict

ORCHESTRATOR_SENTINEL_CONDITION_CHECK_PROMPT = """
You are evaluating whether a specific condition has been ACTUALLY FULFILLED based on an agent's response in the last message.


The overall step we're trying to complete is:
{step_description}

Current sleep duration: {current_sleep_duration} seconds

Rules to follow:
- Finding information ABOUT the condition is NOT the same as the condition being met
- Future events, timers, or pending actions do NOT count as condition fulfillment
- The condition must be CURRENTLY and DEFINITIVELY satisfied in the present moment
- If there is ANY doubt or ambiguity, answer FALSE


- Helpful hints:
    - If the agent provides a screenshot, use the screenshot to determine ground truth rather than the agent's answer.

Condition to Evaluate:
'{condition}'


When in doubt between "condition met" and "condition not met", always choose "condition not met". It's better to wait longer than to incorrectly complete a monitoring task.

For the sleep_duration field, suggest an intelligent new sleep duration in seconds based on the current state and progress observed. Consider:
- If progress is rapid or near completion, suggest shorter intervals
- If little progress is observed, you may suggest longer intervals
- For countdown timers: sleep for roughly 80-90% of the remaining time (e.g., if 6 hours remain, sleep ~5 hours)
- For rapid countdowns (< 10 minutes remaining), use frequent checks (30-60 seconds)
- For gradual progress indicators (like download percentages), adjust based on completion velocity
- If no clear pattern emerges, return the current sleep duration

Answer in this exact JSON format:

{{
    "reason": "Detailed explanation referencing specific evidence from the agent response and why it does/doesn't meet the condition criteria",
    "condition_met": true or false,
    "sleep_duration_reason": "Detailed explanation for the suggested sleep duration",
    "sleep_duration": suggested_sleep_duration_in_seconds,
}}

Only output the JSON object and nothing else.
"""


def validate_sentinel_condition_check_json(json_response: Dict[str, Any]) -> bool:
    """Validate the JSON response for the sentinel condition check."""
    if not isinstance(json_response, dict):
        return False
    if "condition_met" not in json_response or not isinstance(
        json_response["condition_met"], bool
    ):
        return False
    if "reason" not in json_response or not isinstance(json_response["reason"], str):
        return False
    if "sleep_duration" not in json_response or not isinstance(
        json_response["sleep_duration"], int
    ):
        return False
    if json_response["sleep_duration"] <= 0:
        return False
    if "sleep_duration_reason" not in json_response or not isinstance(
        json_response["sleep_duration_reason"], str
    ):
        return False
    return True
