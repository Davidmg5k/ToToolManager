from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.types.user import CreateUser
from app.types.order import CreateOrder, OrderStatus
from app.types.inventory import CreateProduct
from app.types.payment import CreatePayment, PaymentMethod, PaymentStatus
from app.types.notification import CreateNotification, NotificationChannel, NotificationStatus
from app.types.chat import CreateChatSession, CreateChatMessage


class User(CreateUser, table=True):
    user_id: UUID = Field(default_factory=uuid4, primary_key=True)


class Order(CreateOrder, table=True):
    order_id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: OrderStatus = Field(
        default=OrderStatus.PENDING,
        sa_type=SAEnum(OrderStatus, values_by_token=False),
    )


class Product(CreateProduct, table=True):
    product_id: UUID = Field(default_factory=uuid4, primary_key=True)


class PaymentRecord(CreatePayment, table=True):
    payment_id: UUID = Field(default_factory=uuid4, primary_key=True)
    method: PaymentMethod = Field(
        sa_type=SAEnum(PaymentMethod, values_by_token=False),
    )
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING,
        sa_type=SAEnum(PaymentStatus, values_by_token=False),
    )


class NotificationRecord(CreateNotification, table=True):
    notification_id: UUID = Field(default_factory=uuid4, primary_key=True)
    channel: NotificationChannel = Field(
        sa_type=SAEnum(NotificationChannel, values_by_token=False),
    )
    status: NotificationStatus = Field(
        default=NotificationStatus.PENDING,
        sa_type=SAEnum(NotificationStatus, values_by_token=False),
    )


class ChatSession(CreateChatSession, table=True):
    chat_id: UUID = Field(default_factory=uuid4, primary_key=True)
    is_processing: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(CreateChatMessage, table=True):
    message_id: UUID = Field(default_factory=uuid4, primary_key=True)
    chat_id: UUID = Field(foreign_key="chatsession.chat_id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
