# Source: https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/tools/base.py

import json
from abc import ABC, abstractmethod
from typing import List, Optional, Union

from .schema import ContentItem
from .utils import has_chinese_chars, json_loads


def is_tool_schema(obj: dict) -> bool:
    """
    Check if obj is a valid JSON schema describing a tool compatible with OpenAI's tool calling.
    Example valid schema:
    {
      "name": "get_current_weather",
      "description": "Get the current weather in a given location",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "The city and state, e.g. San Francisco, CA"
          },
          "unit": {
            "type": "string",
            "enum": ["celsius", "fahrenheit"]
          }
        },
        "required": ["location"]
      }
    }
    """
    import jsonschema

    try:
        assert set(obj.keys()) == {"name", "description", "parameters"}
        assert isinstance(obj["name"], str)
        assert obj["name"].strip()
        assert isinstance(obj["description"], str)
        assert isinstance(obj["parameters"], dict)

        assert set(obj["parameters"].keys()) == {"type", "properties", "required"}
        assert obj["parameters"]["type"] == "object"
        assert isinstance(obj["parameters"]["properties"], dict)
        assert isinstance(obj["parameters"]["required"], list)
        assert set(obj["parameters"]["required"]).issubset(
            set(obj["parameters"]["properties"].keys())
        )
    except AssertionError:
        return False
    try:
        jsonschema.validate(instance={}, schema=obj["parameters"])
    except jsonschema.exceptions.SchemaError:
        return False
    except jsonschema.exceptions.ValidationError:
        pass
    return True


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: Union[List[dict], dict] = []

    def __init__(self, cfg: Optional[dict] = None):
        self.cfg = cfg or {}
        if not self.name:
            raise ValueError(
                f"You must set {self.__class__.__name__}.name, either by @register_tool(name=...) or explicitly setting {self.__class__.__name__}.name"
            )
        if isinstance(self.parameters, dict):
            if not is_tool_schema(
                {
                    "name": self.name,
                    "description": self.description,
                    "parameters": self.parameters,
                }
            ):
                raise ValueError(
                    "The parameters, when provided as a dict, must confirm to a valid openai-compatible JSON schema."
                )

    @abstractmethod
    def call(
        self, params: Union[str, dict], **kwargs
    ) -> Union[str, list, dict, List[ContentItem]]:
        """The interface for calling tools.

        Each tool needs to implement this function, which is the workflow of the tool.

        Args:
            params: The parameters of func_call.
            kwargs: Additional parameters for calling tools.

        Returns:
            The result returned by the tool, implemented in the subclass.
        """
        raise NotImplementedError

    def _verify_json_format_args(
        self, params: Union[str, dict], strict_json: bool = False
    ) -> dict:
        """Verify the parameters of the function call"""
        if isinstance(params, str):
            try:
                if strict_json:
                    params_json: dict = json.loads(params)
                else:
                    params_json: dict = json_loads(params)
            except json.decoder.JSONDecodeError:
                raise ValueError("Parameters must be formatted as a valid JSON!")
        else:
            params_json: dict = params
        if isinstance(self.parameters, list):
            for param in self.parameters:
                if "required" in param and param["required"]:
                    if param["name"] not in params_json:
                        raise ValueError("Parameters %s is required!" % param["name"])
        elif isinstance(self.parameters, dict):
            import jsonschema

            jsonschema.validate(instance=params_json, schema=self.parameters)
        else:
            raise ValueError
        return params_json

    @property
    def function(self) -> dict:  # Bad naming. It should be `function_info`.
        return {
            # 'name_for_human': self.name_for_human,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            # 'args_format': self.args_format
        }

    @property
    def name_for_human(self) -> str:
        return self.cfg.get("name_for_human", self.name)

    @property
    def args_format(self) -> str:
        fmt = self.cfg.get("args_format")
        if fmt is None:
            if has_chinese_chars(
                [self.name_for_human, self.name, self.description, self.parameters]
            ):
                fmt = "此工具的输入应为JSON对象。"
            else:
                fmt = "Format the arguments as a JSON object."
        return fmt

    @property
    def file_access(self) -> bool:
        return False
