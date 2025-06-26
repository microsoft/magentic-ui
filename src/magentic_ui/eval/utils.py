import hashlib
import json
import requests
from typing import List, Dict, Any


def download_file(url: str, filepath: str) -> None:
    response = requests.get(url)
    response.raise_for_status()
    with open(filepath, "wb") as file:
        file.write(response.content)


def load_jsonl(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def load_json(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_response(response: str) -> str:
    """
    Normalize the response by removing markdown and LaTeX formatting that may prevent a match.

    Source: https://github.com/openai/simple-evals/blob/3ec4e9b5ae3931a1858580e2fd3ce80c7fcbe1d9/common.py#L355C1-L374C6
    """

    return (
        response.replace("**", "")
        .replace("$\\boxed{", "")
        .replace("}$", "")
        .replace("\\$", "")
        .replace("$\\text{", "")
        .replace("$", "")
        .replace("\\mathrm{", "")
        .replace("\\{", "")
        .replace("\\text", "")
        .replace("\\(", "")
        .replace("\\mathbf{", "")
        .replace("{", "")
        .replace("\\boxed", "")
    )


def get_id_for_str(input_string: str) -> str:
    """Generate a unique ID for a given string

    Arguments:
        input_string (str): The input string to hash.
    """
    # Create a SHA-256 hash of the input string, convert to hexadecimal, and take the first 16 characters
    hash_object = hashlib.sha256(input_string.encode())
    hex_dig = hash_object.hexdigest()
    return hex_dig[:16]
