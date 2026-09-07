import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.middleware.middleware import Middleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """User service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class OrderService:
    """Order service for testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"


class LogMiddleware(ConcreteToolMiddleware):
    """Example logging middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestTTMBuilderWithModule:
    """Integration tests for TTMBuilder + Module."""

    def test_builder_add_module(self):
        """TTMBuilder add_module works correctly"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_module(
            name="Commerce",
            services=[user_service],
            description="Commerce module"
        )
        assert result is builder

    def test_builder_build_with_module(self):
        """TTMBuilder build() works with modules"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Commerce",
            services=[user_service],
            description="Commerce module"
        )
        builder.build()
        assert builder.agent is not None
        assert builder.agent.name == "TestBuilder"

    def test_builder_with_module_and_service(self):
        """TTMBuilder works with modules and services"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        order_service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Commerce",
            services=[user_service],
            description="Commerce module"
        )
        builder.add_service(
            name="Orders",
            service=OrderService,
            instructions="Order management"
        )
        builder.build()
        assert builder.agent is not None

    def test_builder_with_multiple_modules(self):
        """TTMBuilder works with multiple modules"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        order_service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Users",
            services=[user_service],
            description="User module"
        )
        builder.add_module(
            name="Orders",
            services=[order_service],
            description="Order module"
        )
        builder.build()
        assert builder.agent is not None

    def test_builder_context_manager_with_module(self):
        """Context manager works with modules"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        with TTMBuilder(name="TestBuilder") as builder:
            builder.add_module(
                name="Commerce",
                services=[user_service],
                description="Commerce module"
            )
        assert builder.agent is not None
