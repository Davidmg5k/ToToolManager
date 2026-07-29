from uuid import UUID
from enum import Enum

from sqlmodel import Field, SQLModel


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class GetNotification(SQLModel):
    notification_id: UUID


class CreateNotification(SQLModel):
    user_id: UUID
    channel: NotificationChannel
    subject: str
    body: str
    recipient: str


class UpdateNotification(SQLModel):
    status: NotificationStatus | None = Field(default=None)
    subject: str | None = Field(default=None)
    body: str | None = Field(default=None)
