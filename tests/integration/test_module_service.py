import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
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


class AuthMiddleware(ConcreteToolMiddleware):
    """Example authentication middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(ConcreteToolMiddleware):
    """Example logging middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestModuleServiceIntegration:
    """Integration tests between Module and Service."""

    def test_module_with_service_builds_agent(self):
        """Module with service builds agent correctly"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        agent = manager.build_agent()
        assert agent is not None
        assert "Commerce" in manager.modules

    def test_module_middlewares_applied_to_services(self):
        """Module middlewares are applied to services"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[LogMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        manager.build_agent()
        # LogMiddleware must be in the service
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_module_disable_middlewares_filters_correctly(self):
        """disable_middlewares filters middlewares correctly"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            disable_middlewares=("AuthMiddleware",)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[AuthMiddleware(), LogMiddleware()],
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        manager.build_agent()
        # AuthMiddleware filtered, LogMiddleware present
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_multiple_modules_with_different_middlewares(self):
        """Multiple modules with different middlewares"""
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
        user_module = Module(
            name="Users",
            services=[user_service],
            description="User module",
            middleware=[AuthMiddleware()]
        )
        order_module = Module(
            name="Orders",
            services=[order_service],
            description="Order module",
            middleware=[LogMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[user_module, order_module]
        )
        agent = manager.build_agent()
        assert agent is not None
        assert "Users" in manager.modules
        assert "Orders" in manager.modules

    def test_global_middlewares_with_module(self):
        """Global middlewares are applied alongside module middlewares"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[LogMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module],
            middlewares=[AuthMiddleware()]
        )
        manager.build_agent()
        # After build_agent():
        # - LogMiddleware (module) is applied via Module._apply_module_middlewares
        # - AuthMiddleware (global) is resolved via _resolve_middlewares
        # Verify that the service has the module middleware
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)
        # Verify that _resolve_middlewares includes the global
        resolved = manager._resolve_middlewares(service)
        assert any(isinstance(mw, AuthMiddleware) for mw in resolved)
