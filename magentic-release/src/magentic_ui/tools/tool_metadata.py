from typing import Any, Dict, List, cast
from typing_extensions import TypedDict
from ..approval_guard import MaybeRequiresApproval
from autogen_core.tools import ToolSchema, ParametersSchema


# We define the ToolMetadata type here to avoid modifying
# the autogen_core module.
class ToolMetadata(TypedDict):
    irreversible: MaybeRequiresApproval


_tool_metadata: dict[str, ToolMetadata] = {}


def load_tool(tooldef: Dict[str, Any]) -> ToolSchema:
    tool_metadata: ToolMetadata = cast(ToolMetadata, tooldef.get("metadata", {}))
    _tool_metadata[tooldef["function"]["name"]] = tool_metadata

    return ToolSchema(
        name=tooldef["function"]["name"],
        description=tooldef["function"]["description"],
        parameters=ParametersSchema(
            type="object",
            properties=tooldef["function"]["parameters"]["properties"],
            required=tooldef["function"]["parameters"]["required"],
        ),
    )


def get_tool_metadata(tool_name_or_schema: str | ToolSchema) -> ToolMetadata:
    """Get the metadata for a tool by its name."""
    tool_name: str | None = (
        tool_name_or_schema
        if isinstance(tool_name_or_schema, str)
        else tool_name_or_schema.get("name")
    )

    metadata = _tool_metadata.get(tool_name)

    if metadata is None:
        raise ValueError(f"Tool {tool_name} not found in metadata.")

    return metadata


REQUIRE_APPROVAL_KEY = "require_approval"
REQUIRE_APPROVAL_PROMPT_FORMAT = "Is this action something that would require human approval before being done? Example: {guarded_examples}; but {unguarded_examples} are not {category}."
IRREVERSIBLE_ACTION_PROMPT_FORMAT = REQUIRE_APPROVAL_PROMPT_FORMAT


def make_approval_prompt(
    guarded_examples: List[str],
    unguarded_examples: List[str],
    category: str = "actions that require approval",
) -> str:
    """
    Create a prompt for the llm to guess as to whether the approval check is needed.
    Args:
        guarded_examples (List[str]): A list of examples of irreversible actions.
        unguarded_examples (List[str]): A list of examples of reversible actions.
        category (str, optional): The category of actions to check for approval. Default: `actions that require approval`.
    Returns:
        str: A string prompt for the actions that require approval check.
    """
    return REQUIRE_APPROVAL_PROMPT_FORMAT.format(
        guarded_examples=", ".join(guarded_examples),
        unguarded_examples=", ".join(unguarded_examples),
        category=category,
    )
