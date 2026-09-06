import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Servicio de ejemplo para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class TestServiceMiddlewareIntegration:
    """Tests de integración entre Service y Middleware."""

    def test_middleware_chain_order(self):
        """Cadena de middlewares se ejecuta en orden"""
        call_order = []

        class MW1(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                call_order.append("MW1")
                return await func(*args, **kw)

        class MW2(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                call_order.append("MW2")
                return await func(*args, **kw)

        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[MW1(), MW2()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )

        resolved = manager._resolve_middlewares(service)
        assert len(resolved) == 2
        assert resolved[0].name == "MW1"
        assert resolved[1].name == "MW2"

    def test_tool_middleware_filters_methods(self):
        """ToolMiddleware filtra métodos correctamente"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[ConcreteToolMiddleware(include=["create"])]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )

        resolved = manager._resolve_middlewares(service)
        tool_mws = [m for m in resolved if isinstance(m, ToolMiddleware)]
        assert len(tool_mws) == 1
        assert tool_mws[0].is_allowed("create") == True
        assert tool_mws[0].is_allowed("get") == False
