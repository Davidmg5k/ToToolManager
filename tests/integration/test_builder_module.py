import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.middleware.middleware import Middleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Servicio de usuarios para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class OrderService:
    """Servicio de órdenes para testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"


class LogMiddleware(ConcreteToolMiddleware):
    """Middleware de logging de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestTTMBuilderWithModule:
    """Tests de integración TTMBuilder + Module."""

    def test_builder_add_module(self):
        """TTMBuilder add_module funciona correctamente"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_module(
            name="Commerce",
            services=[user_service],
            description="Módulo de comercio"
        )
        assert result is builder

    def test_builder_build_with_module(self):
        """TTMBuilder build() funciona con módulos"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Commerce",
            services=[user_service],
            description="Módulo de comercio"
        )
        builder.build()
        assert builder.agent is not None
        assert builder.agent.name == "TestBuilder"

    def test_builder_with_module_and_service(self):
        """TTMBuilder funciona con módulos y servicios"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        order_service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Commerce",
            services=[user_service],
            description="Módulo de comercio"
        )
        builder.add_service(
            name="Orders",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        builder.build()
        assert builder.agent is not None

    def test_builder_with_multiple_modules(self):
        """TTMBuilder funciona con múltiples módulos"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        order_service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Users",
            services=[user_service],
            description="Módulo de usuarios"
        )
        builder.add_module(
            name="Orders",
            services=[order_service],
            description="Módulo de órdenes"
        )
        builder.build()
        assert builder.agent is not None

    def test_builder_context_manager_with_module(self):
        """Context manager funciona con módulos"""
        user_service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        with TTMBuilder(name="TestBuilder") as builder:
            builder.add_module(
                name="Commerce",
                services=[user_service],
                description="Módulo de comercio"
            )
        assert builder.agent is not None
