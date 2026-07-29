import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.model import User, Order, Product, PaymentRecord, NotificationRecord
from app.types.user import CreateUser
from app.types.order import CreateOrder
from app.types.inventory import CreateProduct
from app.types.payment import CreatePayment
from app.types.notification import CreateNotification

TEST_DB_DIR = Path(__file__).parent.parent / "data" / "test"
TEST_DB_PATH = TEST_DB_DIR / "test.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"


@pytest.fixture(name="engine", autouse=True)
def engine_fixture():
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    eng = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine):
    from app import get_session

    def _override_get_session():
        with Session(engine) as session:
            yield session

    from main import app
    app.dependency_overrides[get_session] = _override_get_session

    with patch("app.engine", engine), \
         patch("app.router.api.user.engine", engine), \
         patch("app.router.api.order.engine", engine), \
         patch("app.router.api.payment.engine", engine), \
         patch("app.router.api.inventory.engine", engine), \
         patch("app.router.api.notification.engine", engine), \
         patch("app.router.api.chat.engine", engine), \
         patch("app.router.api.dashboard.engine", engine), \
         patch("main.seed"):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture
def user_factory(session):
    def _create(**kwargs):
        uid = kwargs.pop("user_id", uuid4())
        data = CreateUser(
            user_name=kwargs.get("user_name", f"user_{uid.hex[:8]}"),
            email=kwargs.get("email", f"{uid.hex[:8]}@test.com"),
            password=kwargs.get("password", "secret123"),
        )
        user = User(user_id=uid, **data.model_dump())
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    return _create


@pytest.fixture
def order_factory(session, user_factory):
    def _create(**kwargs):
        user = kwargs.pop("user", None) or user_factory()
        uid = kwargs.pop("order_id", uuid4())
        data = CreateOrder(
            user_id=user.user_id,
            product_name=kwargs.get("product_name", "Test Product"),
            quantity=kwargs.get("quantity", 2),
            unit_price=kwargs.get("unit_price", 29.99),
        )
        order = Order(order_id=uid, **data.model_dump())
        session.add(order)
        session.commit()
        session.refresh(order)
        return order
    return _create


@pytest.fixture
def product_factory(session):
    def _create(**kwargs):
        uid = kwargs.pop("product_id", uuid4())
        data = CreateProduct(
            name=kwargs.get("name", "Test Product"),
            sku=kwargs.get("sku", f"SKU-{uid.hex[:8]}"),
            price=kwargs.get("price", 19.99),
            stock=kwargs.get("stock", 50),
            description=kwargs.get("description", "A test product"),
        )
        product = Product(product_id=uid, **data.model_dump())
        session.add(product)
        session.commit()
        session.refresh(product)
        return product
    return _create


@pytest.fixture
def payment_factory(session, order_factory):
    def _create(**kwargs):
        order = kwargs.pop("order", None) or order_factory()
        uid = kwargs.pop("payment_id", uuid4())
        data = CreatePayment(
            order_id=order.order_id,
            amount=kwargs.get("amount", 59.98),
            method=kwargs.get("method", "credit_card"),
        )
        payment = PaymentRecord(payment_id=uid, **data.model_dump())
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return payment
    return _create


@pytest.fixture
def notification_factory(session, user_factory):
    def _create(**kwargs):
        user = kwargs.pop("user", None) or user_factory()
        uid = kwargs.pop("notification_id", uuid4())
        data = CreateNotification(
            user_id=user.user_id,
            channel=kwargs.get("channel", "email"),
            subject=kwargs.get("subject", "Test Subject"),
            body=kwargs.get("body", "Test body content"),
            recipient=kwargs.get("recipient", "test@test.com"),
        )
        notif = NotificationRecord(notification_id=uid, **data.model_dump())
        session.add(notif)
        session.commit()
        session.refresh(notif)
        return notif
    return _create
