import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Servicio de usuarios para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class AuthMiddleware(ConcreteToolMiddleware):
    """Middleware de autenticación de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(ConcreteToolMiddleware):
    """Middleware de logging de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestDisableMiddlewaresEnToToolManager:
    """Caso de uso: Deshabilitar middlewares en ToToolManager."""

    def test_servicio_publico_sin_auth(self):
        """Dado un servicio público, cuando se deshabilita auth, no se aplica"""
        public_service = Service(
            name="Public",
            service=UserService,
            instructions="API pública",
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
        """Dado un servicio normal, auth se aplica"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
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
    """Caso de uso: Deshabilitar middlewares en Module."""

    def test_module_sin_auth(self):
        """Dado un módulo, cuando el Service deshabilita auth, no se aplica"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            disable_middlewares=("AuthMiddleware",)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[AuthMiddleware(), LogMiddleware()],
        )
        module.build_as_agent()
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_module_con_auth_normal(self):
        """Dado un módulo sin disable_middlewares, auth se aplica"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[AuthMiddleware(), LogMiddleware()]
        )
        module.build_as_agent()
        assert any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)


class TestDisableMiddlewaresEnTTMBuilder:
    """Caso de uso: Deshabilitar middlewares en TTMBuilder."""

    def test_builder_add_middleware(self):
        """TTMBuilder add_middleware registra el middleware"""
        builder = TTMBuilder(name="TestBuilder")
        mw = LogMiddleware()
        result = builder.add_middleware(mw)
        assert result is builder

    def test_builder_remove_middleware_to_service(self):
        """TTMBuilder remove_middleware_to_service funciona"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        # No debe lanzar error
        result = builder.remove_middleware_to_service("User", AuthMiddleware)
        assert result is builder
