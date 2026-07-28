from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.types.user import CreateUser
from app.types.order import CreateOrder
from app.types.inventory import CreateProduct
from app.types.payment import CreatePayment
from app.types.notification import CreateNotification
from app.types.chat import CreateChatSession, CreateChatMessage


class User(CreateUser, table=True):
    user_id: UUID = Field(default_factory=uuid4, primary_key=True)


class Order(CreateOrder, table=True):
    order_id: UUID = Field(default_factory=uuid4, primary_key=True)


class Product(CreateProduct, table=True):
    product_id: UUID = Field(default_factory=uuid4, primary_key=True)


class PaymentRecord(CreatePayment, table=True):
    payment_id: UUID = Field(default_factory=uuid4, primary_key=True)


class NotificationRecord(CreateNotification, table=True):
    notification_id: UUID = Field(default_factory=uuid4, primary_key=True)


class ChatSession(CreateChatSession, table=True):
    chat_id: UUID = Field(default_factory=uuid4, primary_key=True)
    is_processing: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(CreateChatMessage, table=True):
    message_id: UUID = Field(default_factory=uuid4, primary_key=True)
    chat_id: UUID = Field(foreign_key="chatsession.chat_id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
