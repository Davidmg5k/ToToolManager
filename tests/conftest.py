import pytest

from to_tool_manager.core.middleware.middleware import ToolMiddleware


# Example services for tests
class UserService:
    """User service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    def delete(self, id: int) -> bool:
        return True


class OrderService:
    """Order service for testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"

    def get(self, id: int) -> dict:
        return {"id": id, "product": "Test"}


class PublicService:
    """Public service for testing."""

    def list(self) -> list:
        return []


# ConcreteToolMiddleware for testing (ToolMiddleware is abstract)
class ConcreteToolMiddleware(ToolMiddleware):
    """Concrete ToolMiddleware for testing."""

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
