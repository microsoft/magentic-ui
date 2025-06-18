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
