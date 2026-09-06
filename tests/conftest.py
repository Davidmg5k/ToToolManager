import pytest

from to_tool_manager.core.middleware.middleware import ToolMiddleware


# Servicios de ejemplo para tests
class UserService:
    """Servicio de usuarios para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    def delete(self, id: int) -> bool:
        return True


class OrderService:
    """Servicio de órdenes para testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"

    def get(self, id: int) -> dict:
        return {"id": id, "product": "Test"}


class PublicService:
    """Servicio público para testing."""

    def list(self) -> list:
        return []


# ConcreteToolMiddleware para testing (ToolMiddleware es abstracta)
class ConcreteToolMiddleware(ToolMiddleware):
    """ToolMiddleware concreta para testing."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


# Fixtures
@pytest.fixture
def user_service_class():
    return UserService


@pytest.fixture
def order_service_class():
    return OrderService


@pytest.fixture
def public_service_class():
    return PublicService
