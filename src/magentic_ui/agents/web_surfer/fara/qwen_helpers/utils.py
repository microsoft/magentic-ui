# Source: https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/utils/utils.py

import json
import re

from typing import Any


CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def has_chinese_chars(data: Any) -> bool:
    text = f"{data}"
    return bool(CHINESE_CHAR_RE.search(text))


def json_loads(text: str) -> dict:
    text = text.strip("\n")
    if text.startswith("```") and text.endswith("\n```"):
        text = "\n".join(text.split("\n")[1:-1])
    try:
        return json.loads(text)
    except json.decoder.JSONDecodeError as json_err:
        raise json_err
