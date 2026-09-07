import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """User service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class AuthMiddleware(ConcreteToolMiddleware):
    """Example authentication middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(ConcreteToolMiddleware):
    """Example logging middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestDisableMiddlewaresEnToToolManager:
    """Use case: Disable middlewares in ToToolManager."""

    def test_servicio_publico_sin_auth(self):
        """Given a public service, when auth is disabled, it is not applied"""
        public_service = Service(
            name="Public",
            service=UserService,
            instructions="Public API",
            disable_middlewares=("AuthMiddleware",)
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[public_service],
            middlewares=[AuthMiddleware(), LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(public_service)
        assert not any(m.name == "AuthMiddleware" for m in resolved)
        assert any(m.name == "LogMiddleware" for m in resolved)

    def test_servicio_con_auth_normal(self):
        """Given a normal service, auth is applied"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[AuthMiddleware(), LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(service)
        assert any(m.name == "AuthMiddleware" for m in resolved)
        assert any(m.name == "LogMiddleware" for m in resolved)


class TestDisableMiddlewaresEnModule:
    """Use case: Disable middlewares in Module."""

    def test_module_sin_auth(self):
        """Given a module, when Service disables auth, it is not applied"""
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
        module.build_as_agent()
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_module_con_auth_normal(self):
        """Given a module without disable_middlewares, auth is applied"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[AuthMiddleware(), LogMiddleware()]
        )
        module.build_as_agent()
        assert any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)


class TestDisableMiddlewaresEnTTMBuilder:
    """Use case: Disable middlewares in TTMBuilder."""

    def test_builder_add_middleware(self):
        """TTMBuilder add_middleware registers the middleware"""
        builder = TTMBuilder(name="TestBuilder")
        mw = LogMiddleware()
        result = builder.add_middleware(mw)
        assert result is builder

    def test_builder_remove_middleware_to_service(self):
        """TTMBuilder remove_middleware_to_service works"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        # Should not raise error
        result = builder.remove_middleware_to_service("User", AuthMiddleware)
        assert result is builder
