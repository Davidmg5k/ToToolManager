import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
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


class AuthMiddleware(ConcreteToolMiddleware):
    """Middleware de autenticación de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(ConcreteToolMiddleware):
    """Middleware de logging de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestModuleServiceIntegration:
    """Tests de integración entre Module y Service."""

    def test_module_with_service_builds_agent(self):
        """Module con servicio construye agente correctamente"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        agent = manager.build_agent()
        assert agent is not None
        assert "Commerce" in manager.modules

    def test_module_middlewares_applied_to_services(self):
        """Middlewares del módulo se aplican a servicios"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[LogMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        manager.build_agent()
        # LogMiddleware debe estar en el servicio
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_module_disable_middlewares_filters_correctly(self):
        """disable_middlewares filtra middlewares correctamente"""
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
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        manager.build_agent()
        # AuthMiddleware filtrado, LogMiddleware presente
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_multiple_modules_with_different_middlewares(self):
        """Múltiples módulos con middlewares diferentes"""
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
        user_module = Module(
            name="Users",
            services=[user_service],
            description="Módulo de usuarios",
            middleware=[AuthMiddleware()]
        )
        order_module = Module(
            name="Orders",
            services=[order_service],
            description="Módulo de órdenes",
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
        """Middlewares globales se aplican junto con middlewares de módulo"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[LogMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module],
            middlewares=[AuthMiddleware()]
        )
        manager.build_agent()
        # Después de build_agent():
        # - LogMiddleware (módulo) se aplica vía Module._apply_module_middlewares
        # - AuthMiddleware (global) se resuelve vía _resolve_middlewares
        # Verificamos que el servicio tiene el middleware del módulo
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)
        # Verificamos que _resolve_middlewares incluye el global
        resolved = manager._resolve_middlewares(service)
        assert any(isinstance(mw, AuthMiddleware) for mw in resolved)
