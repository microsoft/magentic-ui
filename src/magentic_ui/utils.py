import json
import logging
import os
import psutil
from typing import List, Union, Dict

from autogen_core.models import (
    LLMMessage,
    UserMessage,
    AssistantMessage,
)

from autogen_agentchat.utils import remove_images
from autogen_agentchat.messages import (
    BaseChatMessage,
    BaseTextChatMessage,
    HandoffMessage,
    MultiModalMessage,
    StopMessage,
    TextMessage,
    ToolCallRequestEvent,
    ToolCallExecutionEvent,
    BaseAgentEvent,
)

from .types import HumanInputFormat, RunPaths


class LLMCallFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = json.loads(record.getMessage())
            return message.get("type") == "LLMCall"
        except (json.JSONDecodeError, AttributeError):
            return False


# Define recursive types for JSON structures
JsonPrimitive = Union[str, int, float, bool, None]
JsonList = List[Union[JsonPrimitive, "JsonDict", "JsonList"]]
JsonDict = Dict[str, Union[JsonPrimitive, JsonList, "JsonDict"]]
JsonData = Union[JsonDict, JsonList, str]


def json_data_to_markdown(data: JsonData) -> str:
    """
    Convert a dictionary, list, or JSON string to a nicely formatted Markdown string.
    Handles nested structures of dictionaries and lists.

    Args:
        data (JsonData): The data to convert, can be:
            - A dictionary with string keys and JSON-compatible values
            - A list of JSON-compatible values
            - A JSON string representing either of the above

    Returns:
        str: The formatted Markdown string.

    Raises:
        ValueError: If the input cannot be parsed or converted to markdown format.
        json.JSONDecodeError: If the input string is not valid JSON.
    """

    def format_dict(d: JsonDict, indent: int = 0) -> str:
        md = ""
        for key, value in d.items():
            md += "  " * indent + f"- {key}: "
            if isinstance(value, dict):
                md += "\n" + format_dict(value, indent + 1)
            elif isinstance(value, list):
                md += "\n" + format_list(value, indent + 1)
            else:
                md += f"{value}\n"
        return md

    def format_list(lst: JsonList, indent: int = 0) -> str:
        md = ""
        for item in lst:
            if isinstance(item, dict):
                md += "  " * indent + "- \n" + format_dict(item, indent + 1)
            elif isinstance(item, list):
                md += "  " * indent + "- \n" + format_list(item, indent + 1)
            else:
                md += "  " * indent + f"- {item}\n"
        return md

    try:
        if isinstance(data, str):
            data = json.loads(data)

        if isinstance(data, list):
            return format_list(data)
        elif isinstance(data, dict):
            return format_dict(data)
        else:
            raise ValueError(f"Expected dict, list or JSON string, got {type(data)}")

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON string: {str(e)}", e.doc, e.pos)
    except Exception as e:
        raise ValueError(f"Failed to convert to markdown: {str(e)}")


def dict_to_str(data: Union[JsonDict, str]) -> str:
    """
    Convert a dictionary or JSON string to a JSON string.

    Args:
        data (JsonDict | str): The dictionary or JSON string to convert.

    Returns:
        str: The input dictionary in JSON format.
    """
    if isinstance(data, dict):
        return json.dumps(data)
    elif isinstance(data, str):
        return data
    else:
        raise ValueError("Unexpected input type")


def thread_to_context(
    messages: List[BaseAgentEvent | BaseChatMessage],
    agent_name: str,
    is_multimodal: bool = False,
) -> List[LLMMessage]:
    """Convert the message thread to a context for the model."""
    context: List[LLMMessage] = []
    for m in messages:
        if isinstance(m, ToolCallRequestEvent | ToolCallExecutionEvent):
            # Ignore tool call messages.
            continue
        elif isinstance(m, StopMessage | HandoffMessage):
            context.append(UserMessage(content=m.content, source=m.source))
        elif m.source == agent_name:
            assert isinstance(m, TextMessage), f"{type(m)}"
            context.append(AssistantMessage(content=m.content, source=m.source))
        elif m.source == "user_proxy" or m.source == "user":
            assert isinstance(m, TextMessage | MultiModalMessage), f"{type(m)}"
            if isinstance(m.content, str):
                human_input = HumanInputFormat.from_str(m.content)
                content = f"{human_input.content}"
                if human_input.plan is not None:
                    content += f"\n\nI created the following plan: {human_input.plan}"
                context.append(UserMessage(content=content, source=m.source))
            else:
                # If content is a list, transform only the string part
                content_list = list(m.content)  # Create a copy of the list
                for i, item in enumerate(content_list):
                    if isinstance(item, str):
                        human_input = HumanInputFormat.from_str(item)
                        content_list[i] = f"{human_input.content}"
                        if human_input.plan is not None and isinstance(
                            content_list[i], str
                        ):
                            content_list[i] = (
                                f"{content_list[i]}\n\nI created the following plan: {human_input.plan}"
                            )
                context.append(UserMessage(content=content_list, source=m.source))  # type: ignore
        else:
            assert isinstance(m, BaseTextChatMessage) or isinstance(
                m, MultiModalMessage
            ), f"{type(m)}"
            context.append(UserMessage(content=m.content, source=m.source))
    if is_multimodal:
        return context
    else:
        return remove_images(context)


def get_internal_urls(inside_docker: bool, paths: RunPaths) -> List[str] | None:
    if not inside_docker:
        return None
    urls: List[str] = []
    for _, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == "AF_INET":
                urls.append(addr.address)

    hostname = os.getenv("HOSTNAME")
    if hostname is not None:
        urls.append(hostname)
    container_name = os.getenv("CONTAINER_NAME")
    if container_name is not None:
        urls.append(container_name)
    return urls
