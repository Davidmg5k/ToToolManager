from enum import Enum
from uuid import UUID

from sqlmodel import SQLModel


class ChatTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateChatSession(SQLModel):
    title: str = "New Chat"


class GetChatSession(SQLModel):
    chat_id: UUID


class UpdateChatSession(SQLModel):
    chat_id: UUID
    title: str


class UpdateChatSessionStatus(SQLModel):
    chat_id: UUID
    is_processing: bool


class CreateChatMessage(SQLModel):
    chat_id: UUID
    role: str
    content: str
