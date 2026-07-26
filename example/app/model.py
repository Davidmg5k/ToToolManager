from uuid import UUID, uuid4

from sqlmodel import Field

from app.types.user import CreateUser
from app.types.order import CreateOrder
from app.types.inventory import CreateProduct
from app.types.payment import CreatePayment
from app.types.notification import CreateNotification


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
