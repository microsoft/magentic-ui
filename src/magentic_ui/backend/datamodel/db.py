# defines how core data types are serialized and stored in the database

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Union

from pydantic import field_serializer
from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlmodel import JSON, Column, DateTime, Field, SQLModel, func

from .types import (
    MessageConfig,
    MessageMeta,
)


def _utc_now() -> datetime:
    """Timezone-aware UTC `datetime.now()` for use as a SQLModel default_factory.

    Pairing this with `func.now()` (UTC at the SQL level) keeps every write in
    UTC, so the read-side serializer can safely treat naive datetimes (SQLite
    drops tzinfo on read) as UTC without shifting them.
    """
    return datetime.now(timezone.utc)


def _serialize_utc(value: Any) -> Optional[str]:
    """Serialize a datetime as an ISO-8601 UTC string.

    SQLite drops tzinfo on `DateTime(timezone=True)` columns, so values written
    via `func.now()` or `_utc_now()` come back as naive on read. We treat
    naive datetimes as UTC and stamp the tzinfo so the frontend can parse them
    correctly. Without this, browsers interpret naive ISO strings as local
    time, producing nonsensical relative labels.

    All write paths in this module use `func.now()` or `_utc_now()`, so this
    "naive == UTC" assumption is safe.
    """
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


class Message(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = None
    version: Optional[str] = "0.0.1"
    config: Union[MessageConfig, dict[str, Any]] = Field(
        default_factory=lambda: MessageConfig(source="", content=""),
        sa_column=Column(JSON),
    )
    session_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("session.id", ondelete="CASCADE")),
    )
    run_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("run.id", ondelete="CASCADE")),
    )
    message_meta: Optional[Union[MessageMeta, dict[str, Any]]] = Field(
        default={}, sa_column=Column(JSON)
    )

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime) -> Optional[str]:
        return _serialize_utc(value)


class Session(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = None
    version: Optional[str] = "0.0.1"
    name: Optional[str] = None
    selected_mcp_configs: Optional[List[dict[str, Any]]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime) -> Optional[str]:
        return _serialize_utc(value)


class RunStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"
    PAUSED = "paused"
    AWAITING_INPUT = "awaiting_input"


class InputType(str, Enum):
    TEXT_INPUT = "text_input"
    APPROVAL = "approval"


class Run(SQLModel, table=True):
    """Represents a single execution run within a session"""

    __table_args__ = {"sqlite_autoincrement": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )
    session_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("session.id", ondelete="CASCADE"), nullable=False
        ),
    )
    status: RunStatus = Field(default=RunStatus.CREATED)

    # Store the original user task
    task: Union[MessageConfig, dict[str, Any]] = Field(
        default_factory=lambda: MessageConfig(source="", content=""),
        sa_column=Column(JSON),
    )

    team_result: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    error_message: Optional[str] = None
    version: Optional[str] = "0.0.1"
    messages: Union[List[Message], List[dict[str, Any]]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )

    user_id: Optional[str] = None
    state: Optional[str] = None

    input_request: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON)
    )

    # The agent_mode that was active when this run was started.
    # Stored as the string value of `magentic_ui.magentic_ui_config.AgentMode`
    # (e.g. "all", "omniagent_only", "websurfer_only"). Null on legacy runs
    # created before this column existed; consumers should treat null as
    # "unknown" and avoid hiding any messages.
    agent_mode: Optional[str] = None

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime) -> Optional[str]:
        return _serialize_utc(value)


class Settings(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = Field(default=None, unique=True)
    version: Optional[str] = "0.0.1"
    onboarding_completed: bool = Field(
        default=False, sa_column=Column(Boolean, server_default="0", nullable=False)
    )
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class TrustedFolder(SQLModel, table=True):
    """A folder the user has granted persistent 'Always Allow' access to."""

    __table_args__ = (
        UniqueConstraint("user_id", "path", name="uq_trusted_folder_user_path"),
        {"sqlite_autoincrement": True},
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    user_id: str = Field(nullable=False)
    name: str
    path: str


DatabaseModel = Message | Session | Run | Settings | TrustedFolder
