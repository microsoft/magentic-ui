"""Approval enums and constants shared across the harness.

Used by OmniAgent (tool approval decisions), TeamManager (pending state),
and ConnectionManager (WebSocket approval handling).
"""

from enum import Enum


class ApprovalDecision(str, Enum):
    """Decision values for approval responses (persisted in message metadata)."""

    APPROVE = "approve"
    DENY = "deny"
    ALTERNATIVE = "alternative"


class ApprovalSource(str, Enum):
    """Source of an approval decision."""

    USER = "user"
    AUTO_SESSION = "auto_session"


class ApprovalStatus(str, Enum):
    """Status recorded on tool_call messages.

    Indicates how a tool call was approved before execution.
    """

    USER = "user"
    """Manually approved via Approve button or typing yes."""

    AUTO_SESSION = "auto_session"
    """Auto-approved by session-level user preference."""

    AUTO_POLICY = "auto_policy"
    """Auto-approved by global approval_policy config."""

    AUTO_SAFE = "auto_safe"
    """Classifier determined this is a safe action."""


# Internal agent input value for session-level auto-approve.
# Sent via provide_input() so OmniAgent can distinguish from manual "approve".
AGENT_INPUT_SESSION_AUTO_APPROVE = "session_auto_approve"
