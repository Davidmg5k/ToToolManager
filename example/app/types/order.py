from uuid import UUID
from enum import Enum

from sqlmodel import Field, SQLModel


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class GetOrder(SQLModel):
    order_id: UUID


class CreateOrder(SQLModel):
    user_id: UUID
    product_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.0)
    status: OrderStatus = OrderStatus.PENDING


class UpdateOrder(GetOrder):
    product_name: str | None = Field(default=None)
    quantity: int | None = Field(default=None, ge=1)
    unit_price: float | None = Field(default=None, ge=0.0)
    status: OrderStatus | None = Field(default=None)
