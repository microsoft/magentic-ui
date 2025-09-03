# defines how core data types are serialized and stored in the database

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union

from autogen_core import ComponentModel
from pydantic import field_serializer
from sqlalchemy import ForeignKey, Integer
from sqlmodel import JSON, Column, DateTime, Field, SQLModel, func

from .types import (
    GalleryConfig,
    MessageConfig,
    MessageMeta,
    SettingsConfig,
    TeamResult,
    GalleryComponents,
    GalleryMetadata,
)


class Team(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = None
    version: Optional[str] = "0.0.1"
    component: Union[ComponentModel, dict[str, Any]] = Field(sa_column=Column(JSON))


class Message(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=datetime.now,
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


class Session(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = None
    version: Optional[str] = "0.0.1"
    team_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("team.id", ondelete="CASCADE")),
    )
    name: Optional[str] = None
    selected_mcp_configs: Optional[List[dict[str, Any]]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )


class RunStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"
    AWAITING_INPUT = "awaiting_input"
    PAUSED = "paused"


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
        default_factory=datetime.now,
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

    # Store TeamResult which contains TaskResult
    team_result: Union[TeamResult, dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON)
    )

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

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(cls, value: datetime) -> str:
        if isinstance(value, datetime):
            return value.isoformat()


class Gallery(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = None
    version: Optional[str] = "0.0.1"
    config: Union[GalleryConfig, dict[str, Any]] = Field(
        default_factory=lambda: GalleryConfig(
            id="",
            name="",
            metadata=GalleryMetadata(author="", version=""),
            components=GalleryComponents(
                agents=[], models=[], tools=[], terminations=[], teams=[]
            ),
        ),
        sa_column=Column(JSON),
    )

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(cls, value: datetime) -> str:
        if isinstance(value, datetime):
            return value.isoformat()


class Settings(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = Field(default=None, unique=True)
    version: Optional[str] = "0.0.1"
    config: Union[SettingsConfig, dict[str, Any]] = Field(
        default_factory=lambda: SettingsConfig().model_dump(), sa_column=Column(JSON)
    )

    @field_serializer("config")
    def serialize_config(
        self, value: Union[SettingsConfig, dict[str, Any]]
    ) -> dict[str, Any]:
        if isinstance(value, SettingsConfig):
            return value.model_dump()
        return value


class Plan(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )  # pylint: disable=not-callable
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )  # pylint: disable=not-callable
    user_id: Optional[str] = None
    version: Optional[str] = "0.0.1"
    task: Optional[str] = None
    steps: Optional[List[dict[str, Any]]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    session_id: Optional[int] = None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(cls, value: datetime) -> str:
        if isinstance(value, datetime):
            return value.isoformat()


DatabaseModel = Team | Message | Session | Run | Gallery | Settings | Plan
