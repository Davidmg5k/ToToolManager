from uuid import UUID
from enum import Enum

from sqlmodel import Field, SQLModel


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class GetPayment(SQLModel):
    payment_id: UUID


class CreatePayment(SQLModel):
    order_id: UUID
    amount: float = Field(ge=0.01)
    method: PaymentMethod
    currency: str = "USD"


class UpdatePayment(SQLModel):
    status: PaymentStatus | None = Field(default=None)
    amount: float | None = Field(default=None, ge=0.01)
