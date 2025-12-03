from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class MessageConfig(BaseModel):
    source: str
    content: str | None
    message_type: Optional[str] = "text"


class MessageMeta(BaseModel):
    task: Optional[str] = None
    summary_method: Optional[str] = "last"
    files: Optional[List[dict[str, Any]]] = None
    time: Optional[datetime] = None
    log: Optional[List[dict[str, Any]]] = None
    usage: Optional[List[dict[str, Any]]] = None


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


# web request/response data models


class Response(BaseModel):
    message: str
    status: bool
    data: Optional[Any] = None


class SocketMessage(BaseModel):
    connection_id: str
    data: Dict[str, Any]
    type: str
