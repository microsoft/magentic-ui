import json
import re
from typing import Any, Optional


def is_accepted_str(user_input: str) -> bool:
    LIST_OF_ACCEPTED_STRS = [
        "accept",
        "accepted",
        "acept",
        "run",
        "execute plan",
        "execute",
        "looks good",
        "do it",
        "accept plan",
        "accpt",
        "run plan",
        "sounds good",
        "i don't know. use your best judgment.",
        "i don't know, you figure it out, don't ask me again.",
    ]
    user_input = user_input.lower()
    user_input = user_input.strip()
    if user_input in LIST_OF_ACCEPTED_STRS:
        return True
    return False


def extract_json_from_string(s: str) -> Optional[Any]:
    """
    Searches for a JSON object within the string and returns the loaded JSON if found, otherwise returns None.
    """
    # Regex to find JSON objects (greedy, matches first { to last })
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None
