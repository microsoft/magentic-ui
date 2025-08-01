from typing import Any, Dict

ORCHESTRATOR_SENTINEL_CONDITION_CHECK_PROMPT = """
You are evaluating whether a specific condition has been ACTUALLY FULFILLED based on an agent's response in the last message.


The overall step we're trying to complete is:
{step_description}


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

Answer in this exact JSON format:

{{
    "reason": "Detailed explanation referencing specific evidence from the agent response and why it does/doesn't meet the condition criteria",
    "condition_met": true or false,
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
    return True
