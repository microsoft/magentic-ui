from autogen_core.tools import ParametersSchema
from ...tools.tool_metadata import load_tool

EXPLANATION_TOOL_PROMPT = "Explain to the user the action to be performed and reason for doing so. Phrase as if you are directly talking to the user."

TOOL_OPEN_PATH = load_tool(
    {
        "type": "function",
        "function": {
            "name": "open_path",
            "description": "Open a local file or directory at a path in the text-based file browser and return current viewport content.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "path": {
                        "type": "string",
                        "description": "The relative or absolute path of a local file to visit.",
                    },
                },
                required=["explanation", "path"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_LIST_CURRENT_DIRECTORY = load_tool(
    {
        "type": "function",
        "function": {
            "name": "list_current_directory",
            "description": "List the contents of the current working directory using the text-based file browser.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                required=["explanation"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_PAGE_UP = load_tool(
    {
        "type": "function",
        "function": {
            "name": "page_up",
            "description": "Scroll the viewport UP one page-length in the current file and return the new viewport content.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                required=["explanation"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_PAGE_DOWN = load_tool(
    {
        "type": "function",
        "function": {
            "name": "page_down",
            "description": "Scroll the viewport DOWN one page-length in the current file and return the new viewport content.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                required=["explanation"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_FIND_ON_PAGE_CTRL_F = load_tool(
    {
        "type": "function",
        "function": {
            "name": "find_on_page_ctrl_f",
            "description": "Scroll the viewport to the first occurrence of the search string. This is equivalent to Ctrl+F.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "search_string": {
                        "type": "string",
                        "description": "The string to search for on the page. This search string supports wildcards like '*'",
                    },
                },
                required=["explanation", "search_string"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_FIND_NEXT = load_tool(
    {
        "type": "function",
        "function": {
            "name": "find_next",
            "description": "Scroll the viewport to next occurrence of the search string.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                required=["explanation"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_FIND_FILE = load_tool(
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": "Search for files matching a query string in the current directory and subdirectories. Returns up to 20 closest matches.",
            "parameters": ParametersSchema(
                type="object",
                properties={
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "query": {
                        "type": "string",
                        "description": "The file name or pattern to search for. Supports wildcards like '*'.",
                    },
                },
                required=["explanation", "query"],
            ),
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)
