"""Type-safe message schemas for agent additional_properties.

This module defines TypedDict schemas for all WebSocket message types,
ensuring consistency between agents and the connection layer.

Usage:
    from magentic_ui.agents.message_schemas import (
        browser_address_props,
        screenshot_props,
        system_props,
    )

    yield StreamUpdate(
        text="...",
        additional_properties=screenshot_props(source, image),
    )
"""

import json
from enum import Enum
from typing import Any, Literal, TypedDict, NotRequired


# =============================================================================
# Literal types for discriminators
# =============================================================================

MessageType = Literal[
    "agent_state",
    "browser_address",
    "browser_screenshot",
    "code_to_execute",
    "compaction_end",
    "compaction_start",
    "error",
    "file",
    "final_answer",
    "input_request",
    "reasoning",
    "system",
    "text",
    "tool_call",
    "tool_result",
]

SystemStatus = Literal["complete", "error", "paused", "stopped", "awaiting_input"]

InputType = Literal["text_input", "approval", "continuation"]

# Transient signal around LLM calls so the UI can distinguish "waiting for
# the model" from "generating". Forwarded to the WebSocket only, not persisted.
AgentState = Literal["calling_model", "generating"]


# =============================================================================
# TypedDict schemas for additional_properties
# =============================================================================


class BrowserAddressProps(TypedDict):
    """Browser initialization message with noVNC/Playwright ports."""

    source: str
    type: Literal["browser_address"]
    novnc_port: str
    playwright_port: str
    # Per-slot RFB password the frontend passes to react-vnc so the noVNC
    # handshake authenticates silently. Omitted from the dict when the
    # browser backend doesn't set a password (e.g., local-only tests) and
    # scrubbed from persisted messages — only the live WS frame carries it.
    password: NotRequired[str]


class ScreenshotProps(TypedDict):
    """Browser screenshot message."""

    source: str
    type: Literal["browser_screenshot"]
    image: str  # data:image/png;base64,...


class ToolCallProps(TypedDict):
    """Tool call message (before execution).

    ``approval_status`` records how this tool call was approved:

    - ``"user"`` — manually approved via Approve button or typing yes
    - ``"auto_session"`` — auto-approved by session-level preference
    - ``"auto_policy"`` — auto-approved by global approval_policy config
    - ``"auto_safe"`` — classifier determined this is a safe action
    - absent — no explicit approval status was recorded for this tool call

    This is informational only — by the time this message is emitted
    the approval has already been granted (or was not needed).
    """

    source: str
    type: Literal["tool_call"]
    tool: str
    tool_args: dict[str, Any]
    tool_call_id: NotRequired[str]
    approval_status: NotRequired[
        Literal["user", "auto_session", "auto_policy", "auto_safe"]
    ]


class SystemProps(TypedDict):
    """System status message (complete, error, paused, stopped)."""

    source: str
    type: Literal["system"]
    status: SystemStatus
    content: NotRequired[str]


class InputRequestProps(TypedDict):
    """Request for user input (pause state)."""

    source: str
    type: Literal["input_request"]
    input_type: InputType
    content: NotRequired[str]
    # Approval-specific fields (present when input_type == "approval")
    tool: NotRequired[str]
    tool_args: NotRequired[dict[str, Any]]
    category: NotRequired[str]
    reason: NotRequired[str]


class ErrorProps(TypedDict):
    """Error message (non-fatal, agent continues)."""

    source: str
    type: Literal["error"]


class ReasoningProps(TypedDict):
    """Agent reasoning/thought message."""

    source: str
    type: Literal["reasoning"]
    # Model generation time (first token -> completion). Omitted when
    # unknown (legacy rows, or no token stream) rather than null.
    thinking_seconds: NotRequired[int]


class TextProps(TypedDict):
    """Plain text message."""

    source: str
    type: Literal["text"]


class ToolResultProps(TypedDict):
    """Tool result message."""

    source: str
    type: Literal["tool_result"]
    tool: NotRequired[str]
    tool_call_id: NotRequired[str]


class CodeToExecuteProps(TypedDict):
    """Code to execute message (before execution)."""

    source: str
    type: Literal["code_to_execute"]
    code: str


class HandoffStatus(str, Enum):
    """Coarse outcome of a sub-agent run."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    ERROR = "error"


class HandoffReason(str, Enum):
    """What ended the sub-agent run."""

    TERMINATE = "terminate"
    MAX_ROUNDS = "max_rounds"
    ORPHAN_RECOVERY = "orphan_recovery"
    CONSECUTIVE_ERRORS = "consecutive_errors"


class HandoffInfo(TypedDict):
    """Structured sub-agent handoff metadata."""

    status: str
    reason: str
    last_url: str | None
    facts: list[str]


class FinalAnswerProps(TypedDict):
    """Final answer message (task complete)."""

    source: str
    type: Literal["final_answer"]
    max_rounds_reached: NotRequired[bool]
    handoff: NotRequired[HandoffInfo]


class FileGeneratedProps(TypedDict):
    """File generated/modified message."""

    source: str
    type: Literal["file"]
    files: str  # JSON string of file list
    # When True, this message is the end-of-run aggregated summary listing
    # every file the agent created or modified during the task. The frontend
    # renders it under a "Files created or modified" header so users can
    # find all artifacts at a glance after the final answer.
    summary: NotRequired[bool]
    # Only set on summary messages. JSON string of files the user uploaded
    # for this task. Each entry has the same display fields as `files`
    # (`name`, `url`, `timestamp`, `extension`, `file_type`) but no
    # `action` field — uploads aren't created/modified by the agent.
    # Rendered as a separate "Files you uploaded" section above the
    # "Files the agent created or modified" section so users get a
    # complete overview of inputs and outputs.
    uploaded_files: NotRequired[str]


class CompactionStartProps(TypedDict):
    """Context compaction started — history is about to be summarized."""

    source: str
    type: Literal["compaction_start"]
    tokens_before: int  # total_tokens on the call that triggered compaction


class CompactionEndProps(TypedDict):
    """Context compaction finished — history has been replaced with a handoff."""

    source: str
    type: Literal["compaction_end"]


class AgentStateProps(TypedDict):
    """Transient agent activity signal around an LLM call.

    ``calling_model`` before the request is dispatched; ``generating`` once
    the first token streams back. Cleared by the next persistent message,
    so there is no explicit ``idle`` state.
    """

    source: str
    type: Literal["agent_state"]
    state: AgentState


# =============================================================================
# Factory functions for type-safe construction
# =============================================================================


def browser_address_props(
    source: str,
    novnc_port: str,
    playwright_port: str,
    password: str = "",
) -> BrowserAddressProps:
    """Create browser address properties."""
    props: BrowserAddressProps = {
        "source": source,
        "type": "browser_address",
        "novnc_port": novnc_port,
        "playwright_port": playwright_port,
    }
    if password:
        props["password"] = password
    return props


def screenshot_props(source: str, image: str) -> ScreenshotProps:
    """Create screenshot properties.

    Args:
        source: Agent name
        image: Base64 data URI (data:image/png;base64,...)
    """
    return {
        "source": source,
        "type": "browser_screenshot",
        "image": image,
    }


def tool_call_props(
    source: str,
    tool: str,
    tool_args: dict[str, Any],
    tool_call_id: str | None = None,
    *,
    approval_status: Literal["user", "auto_session", "auto_policy", "auto_safe"]
    | None = None,
) -> ToolCallProps:
    """Create tool call properties."""
    props: ToolCallProps = {
        "source": source,
        "type": "tool_call",
        "tool": tool,
        "tool_args": tool_args,
    }
    if tool_call_id is not None:
        props["tool_call_id"] = tool_call_id
    if approval_status is not None:
        props["approval_status"] = approval_status
    return props


def system_props(
    source: str, status: SystemStatus, content: str | None = None
) -> SystemProps:
    """Create system status properties.

    Args:
        source: Agent name
        status: One of "complete", "error", "paused", "stopped"
        content: Optional message content (e.g., error details)
    """
    props: SystemProps = {
        "source": source,
        "type": "system",
        "status": status,
    }
    if content is not None:
        props["content"] = content
    return props


def input_request_props(
    source: str,
    content: str | None = None,
    input_type: InputType = "text_input",
    *,
    tool: str | None = None,
    tool_args: dict[str, Any] | None = None,
    category: str | None = None,
    reason: str | None = None,
) -> InputRequestProps:
    """Create input request properties.

    For approval requests (``input_type="approval"``), include
    ``tool``, ``tool_args``, ``category``, and ``reason``.
    """
    props: InputRequestProps = {
        "source": source,
        "type": "input_request",
        "input_type": input_type,
    }
    if content is not None:
        props["content"] = content
    if tool is not None:
        props["tool"] = tool
    if tool_args is not None:
        props["tool_args"] = tool_args
    if category is not None:
        props["category"] = category
    if reason is not None:
        props["reason"] = reason
    return props


def error_props(source: str) -> ErrorProps:
    """Create error properties."""
    return {
        "source": source,
        "type": "error",
    }


def reasoning_props(source: str, thinking_seconds: int | None = None) -> ReasoningProps:
    """Create reasoning/thought properties.

    ``thinking_seconds`` is the model's generation time; omitted when None
    so the frontend's timestamp-diff fallback is unchanged.
    """
    props: ReasoningProps = {
        "source": source,
        "type": "reasoning",
    }
    if thinking_seconds is not None:
        props["thinking_seconds"] = thinking_seconds
    return props


def agent_state_props(source: str, state: AgentState) -> AgentStateProps:
    """Create transient agent_state properties (not persisted)."""
    return {
        "source": source,
        "type": "agent_state",
        "state": state,
    }


def text_props(source: str) -> TextProps:
    """Create text properties."""
    return {
        "source": source,
        "type": "text",
    }


def tool_result_props(
    source: str,
    tool_call_id: str | None = None,
    tool: str | None = None,
) -> ToolResultProps:
    """Create tool result properties."""
    props: ToolResultProps = {
        "source": source,
        "type": "tool_result",
    }
    if tool is not None:
        props["tool"] = tool
    if tool_call_id is not None:
        props["tool_call_id"] = tool_call_id
    return props


def code_to_execute_props(source: str, code: str) -> CodeToExecuteProps:
    """Create code to execute properties.

    Args:
        source: Agent name
        code: The Python code to execute
    """
    return {
        "source": source,
        "type": "code_to_execute",
        "code": code,
    }


def final_answer_props(
    source: str,
    max_rounds_reached: bool = False,
    handoff: HandoffInfo | None = None,
) -> FinalAnswerProps:
    """Create final answer properties.

    Args:
        source: Agent name
        max_rounds_reached: Whether max rounds was reached (vs natural completion)
        handoff: Structured sub-agent handoff metadata, when available
    """
    props: FinalAnswerProps = {
        "source": source,
        "type": "final_answer",
    }
    if max_rounds_reached:
        props["max_rounds_reached"] = True
    if handoff is not None:
        props["handoff"] = handoff
    return props


def file_generated_props(
    source: str,
    files: list[dict[str, Any]],
    summary: bool = False,
    uploaded_files: list[dict[str, Any]] | None = None,
) -> FileGeneratedProps:
    """Create file generated/modified properties.

    Args:
        source: Agent name (typically "system")
        files: List of file dicts with name, url, timestamp, extension, file_type, action
        summary: If True, marks this as the end-of-run aggregated file list
            (rendered with a "Files the agent created or modified" header).
        uploaded_files: Files the user uploaded for this task. Only meaningful
            on summary messages — the frontend renders them as a separate
            "Files you uploaded" section above the generated files.
    """
    props: FileGeneratedProps = {
        "source": source,
        "type": "file",
        "files": json.dumps(files),
    }
    if summary:
        props["summary"] = True
    if uploaded_files:
        props["uploaded_files"] = json.dumps(uploaded_files)
    return props


def compaction_start_props(source: str, tokens_before: int) -> CompactionStartProps:
    """Create compaction-start properties.

    Args:
        source: Agent name.
        tokens_before: Total token count of the response that
            triggered compaction. Lets the UI show how much context
            is about to be summarized.
    """
    return {
        "source": source,
        "type": "compaction_start",
        "tokens_before": tokens_before,
    }


def compaction_end_props(source: str) -> CompactionEndProps:
    """Create compaction-end properties.

    Args:
        source: Agent name.
    """
    return {
        "source": source,
        "type": "compaction_end",
    }
