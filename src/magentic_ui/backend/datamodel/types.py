# from dataclasses import Field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import BaseChatMessage, BaseTextChatMessage
from autogen_core import ComponentModel
from pydantic import BaseModel, field_serializer


class MessageConfig(BaseModel):
    source: str
    content: str | BaseChatMessage | Sequence[BaseChatMessage] | None
    message_type: Optional[str] = "text"


class TeamResult(BaseModel):
    task_result: TaskResult
    usage: str
    duration: float
    files: Optional[List[dict[str, Any]]] = None


class LLMCallEventMessage(BaseTextChatMessage):
    source: str = "llm_call_event"
    content: str


class MessageMeta(BaseModel):
    task: Optional[str] = None
    task_result: Optional[TaskResult] = None
    summary_method: Optional[str] = "last"
    files: Optional[List[dict[str, Any]]] = None
    time: Optional[datetime] = None
    log: Optional[List[dict[str, Any]]] = None
    usage: Optional[List[dict[str, Any]]] = None


class GalleryMetadata(BaseModel):
    author: str
    # created_at: datetime = Field(default_factory=datetime.now)
    # updated_at: datetime = Field(default_factory=datetime.now)
    version: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    category: Optional[str] = None
    last_synced: Optional[datetime] = None

    @field_serializer("last_synced")
    def serialize_last_synced(cls, value: Optional[datetime]) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        else:
            return None


class GalleryComponents(BaseModel):
    agents: List[ComponentModel]
    models: List[ComponentModel]
    tools: List[ComponentModel]
    terminations: List[ComponentModel]
    teams: List[ComponentModel]


class GalleryConfig(BaseModel):
    id: str
    name: str
    url: Optional[str] = None
    metadata: GalleryMetadata
    components: GalleryComponents


class EnvironmentVariable(BaseModel):
    name: str
    value: str
    type: Literal["string", "number", "boolean", "secret"] = "string"
    description: Optional[str] = None
    required: bool = False


class UISettings(BaseModel):
    show_llm_call_events: bool = False
    expanded_messages_by_default: bool = True
    show_agent_flow_by_default: bool = True


class SettingsConfig(BaseModel):
    # empty starting point
    pass


# web request/response data models


class Response(BaseModel):
    message: str
    status: bool
    data: Optional[Any] = None


class SocketMessage(BaseModel):
    connection_id: str
    data: Dict[str, Any]
    type: str
