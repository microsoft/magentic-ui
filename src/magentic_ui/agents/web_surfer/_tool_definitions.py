from autogen_core.tools import ToolSchema

from ...tools.tool_metadata import load_tool, make_approval_prompt

EXPLANATION_TOOL_PROMPT = "Explain to the user the action to be performed and reason for doing so. Phrase as if you are directly talking to the user."

REFINED_GOAL_PROMPT = "1) Summarize all the information observed and actions performed so far and 2) refine the request to be completed"

IRREVERSIBLE_ACTION_PROMPT = make_approval_prompt(
    guarded_examples=["buying a product", "submitting a form"],
    unguarded_examples=["navigating a website", "things that can be undone"],
    category="irreversible actions",
)

# "Is this action something that would require human approval before being done as it is irreversible? Example: buying a product, submitting a form are irreversible actions. But navigating a website and things that can be undone are not irreversible actions."

TOOL_VISIT_URL: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "visit_url",
            "description": "Navigate directly to a provided URL using the browser's address bar. Prefer this tool over other navigation techniques in cases where the user provides a fully-qualified URL (e.g., choose it over clicking links, or inputing queries into search boxes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "url": {
                        "type": "string",
                        "description": "The URL to visit in the browser.",
                    },
                },
                "required": ["explanation", "url"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_WEB_SEARCH: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Performs a web search on a search engine with the given query. Make sure the query is simple and don't use compound queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "query": {
                        "type": "string",
                        "description": "The web search query to use.",
                    },
                },
                "required": ["explanation", "query"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_HISTORY_BACK: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "history_back",
            "description": "Navigates back one page in the browser's history. This is equivalent to clicking the browser back button.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_REFRESH_PAGE: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "refresh_page",
            "description": "Refreshes the current page in the browser. This is equivalent to clicking the browser refresh button or pressing F5.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_PAGE_UP: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "page_up",
            "description": "Scrolls the entire browser viewport one page UP towards the beginning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {"requires_approval": "never"},
    }
)

TOOL_PAGE_DOWN: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "page_down",
            "description": "Scrolls the entire browser viewport one page DOWN towards the end.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {"requires_approval": "never"},
    }
)

TOOL_SCROLL_DOWN: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "scroll_down",
            "description": "Scrolls down on the current page using mouse wheel for 400 pixels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    # "pixels": {
                    #     "type": "integer",
                    #     "description": "Number of pixels to scroll down. Default is 400 pixels.",
                    #     "default": 400,
                    # },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {"requires_approval": "never"},
    }
)

TOOL_SCROLL_UP: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "scroll_up",
            "description": "Scrolls up on the current page using mouse wheel for 400 pixels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    # "pixels": {
                    #     "type": "integer",
                    #     "description": "Number of pixels to scroll up. Default is 400 pixels.",
                    #     "default": 400,
                    # },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {"requires_approval": "never"},
    }
)

TOOL_CLICK: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Clicks the mouse on the target with the given id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "The numeric id of the target to click.",
                    },
                },
                "required": ["explanation", "target_id"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_CLICK_FULL: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "click_full",
            "description": "Clicks the mouse on the target with the given id, with optional hold duration and button type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "The numeric id of the target to click.",
                    },
                    "hold": {
                        "type": "number",
                        "description": "Seconds to hold the mouse button down before releasing. Default: 0.0.",
                        "default": 0.0,
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "right"],
                        "description": "Mouse button to use. Default: 'left'.",
                        "default": "left",
                    },
                },
                "required": ["explanation", "target_id", "hold", "button"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_TYPE: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "input_text",
            "description": "Types the given text value into the specified field. Presses enter only if you want to submit the form or search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "input_field_id": {
                        "type": "integer",
                        "description": "The numeric id of the input field to receive the text.",
                    },
                    "text_value": {
                        "type": "string",
                        "description": "The text to type into the input field.",
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "Whether to press enter after typing into the field or not.",
                    },
                    "delete_existing_text": {
                        "type": "boolean",
                        "description": "Whether to delete existing text in the field before inputing the text value.",
                    },
                },
                "required": [
                    "explanation",
                    "input_field_id",
                    "text_value",
                    "delete_existing_text",
                ],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_SCROLL_ELEMENT_DOWN: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "scroll_element_down",
            "description": "Scrolls a given html element (e.g., a div or a menu) DOWN.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "The numeric id of the target to scroll down.",
                    },
                },
                "required": ["explanation", "target_id"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_SCROLL_ELEMENT_UP: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "scroll_element_up",
            "description": "Scrolls a given html element (e.g., a div or a menu) UP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "The numeric id of the target to scroll UP.",
                    },
                },
                "required": ["explanation", "target_id"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_HOVER: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "hover",
            "description": "Hovers the mouse over the target with the given id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "The numeric id of the target to hover over.",
                    },
                },
                "required": ["explanation", "target_id"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_KEYPRESS: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "keypress",
            "description": "Press one or multiple keyboard keys in sequence, this is not used for typing text. Supports special keys like 'Enter', 'Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Backspace', 'Delete', 'Escape', 'Control', 'Alt', 'Shift'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of keys to press in sequence. For special keys, use their full name (e.g. 'Enter', 'Tab', etc.).",
                    },
                },
                "required": ["explanation", "keys"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_READ_PAGE_AND_ANSWER: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "answer_question",
            "description": "Used to answer questions about the current webpage's content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "question": {
                        "type": "string",
                        "description": "The question to answer. Do not ask any follow up questions or say that you can help with more things.",
                    },
                },
                "required": ["explanation", "question"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_SUMMARIZE_PAGE: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "summarize_page",
            "description": "Uses AI to summarize the entire page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_SLEEP: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "sleep",
            "description": "Wait a specified period of time in seconds (default 3 seconds). Call this function if the page has not yet fully loaded, or if it is determined that a small delay would increase the task's chances of success.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "duration": {
                        "type": "number",
                        "description": "The number of seconds to wait. Default is 3 seconds.",
                    },
                },
                "required": ["explanation"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)


TOOL_STOP_ACTION: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "stop_action",
            "description": "Perform no action on the browser. Answer the request directly and summarize all past actions and observations you did previously in relation to the request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "answer": {
                        "type": "string",
                        "description": "The answer to the request and a complete summary of past actions and observations. Phrase using first person and as if you are directly talking to the user. Do not ask any questions or say that you can help with more things.",
                    },
                },
                "required": ["explanation", "answer"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_SELECT_OPTION: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "select_option",
            "description": "Selects an option from a dropdown/select menu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "The numeric id of the option to select.",
                    },
                },
                "required": ["explanation", "target_id"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_CREATE_TAB: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "create_tab",
            "description": "Creates a new browser tab and navigates to the specified URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "url": {
                        "type": "string",
                        "description": "The URL to open in the new tab.",
                    },
                },
                "required": ["explanation", "url"],
            },
        },
        "metadata": {
            "requires_approval": "maybe",
        },
    }
)

TOOL_SWITCH_TAB: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "switch_tab",
            "description": "Switches focus to a different browser tab by its index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "tab_index": {
                        "type": "integer",
                        "description": "The index of the tab to switch to (0-based).",
                    },
                },
                "required": ["explanation", "tab_index"],
            },
        },
        "metadata": {
            "requires_approval": "never",
        },
    }
)

TOOL_CLOSE_TAB: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "close_tab",
            "description": "Closes the specified browser tab by its index and switches to an adjacent tab. Cannot close the last remaining tab.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": EXPLANATION_TOOL_PROMPT,
                    },
                    "tab_index": {
                        "type": "integer",
                        "description": "The index of the tab to close (0-based).",
                    },
                },
                "required": ["explanation", "tab_index"],
            },
        },
        "metadata": {
            "requires_approval": "always",
        },
    }
)

TOOL_UPLOAD_FILE: ToolSchema = load_tool(
    {
        "type": "function",
        "function": {
            "name": "upload_file",
            "description": "Upload a file to a specified input element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": "The explanation of the action to be performed.",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "The ID of the target input element.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to be uploaded.",
                    },
                },
                "required": ["explanation", "target_id", "file_path"],
            },
            "metadata": {
                "requires_approval": "always",
            },
        },
    }
)
