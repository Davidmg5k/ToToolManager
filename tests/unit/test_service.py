import inspect
import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.middleware.middleware import ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Servicio de ejemplo para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    def delete(self, id: int) -> bool:
        return True


class AsyncUserService:
    """Servicio async de ejemplo para testing."""

    async def create(self, name: str) -> str:
        return f"Created {name}"

    async def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class AuthMiddleware(ConcreteToolMiddleware):
    """Middleware de autenticación de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(ConcreteToolMiddleware):
    """Middleware de logging de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestService:
    """Tests para la clase Service."""

    def test_build_as_capability(self):
        """Service retorna Capability"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        capability = service.build_as_capability()
        assert capability.id == "User"

    def test_add_middleware(self):
        """Service permite añadir middlewares"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        mw = ConcreteToolMiddleware()
        service.add_middleware(mw)
        assert mw in service.middleware

    def test_disable_middlewares_default_empty(self):
        """disable_middlewares es tuple vacío por defecto"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        assert service.disable_middlewares == ()

    def test_disable_middlewares_custom(self):
        """disable_middlewares acepta tupla de strings"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            disable_middlewares=("AuthMiddleware", "LogMiddleware")
        )
        assert "AuthMiddleware" in service.disable_middlewares
        assert "LogMiddleware" in service.disable_middlewares

    def test_service_is_not_frozen(self):
        """Service NO es frozen (add_middleware() necesita mutar)"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        # Service permite mutación porque add_middleware() añade a self.middleware
        service.name = "Other"
        assert service.name == "Other"

    def test_service_has_slots(self):
        """Service tiene slots para eficiencia"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        assert not hasattr(service, '__dict__')

    def test_middleware_default_empty_list(self):
        """middleware es lista vacía por defecto"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        assert service.middleware == []

    def test_include_default_none(self):
        """include es None por defecto"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        assert service.include is None

    def test_exclude_default_none(self):
        """exclude es None por defecto"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        assert service.exclude is None


class TestBuildAsCapability:
    """Tests para build_as_capability() con descubrimiento automático."""

    def test_creates_capability_with_tools(self):
        """build_as_capability() crea Capability con tools de todos los métodos."""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        capability = service.build_as_capability()

        # Debe tener 3 tools: create, get, delete
        assert len(capability.tools) == 3

    def test_tools_are_tool_instances(self):
        """Las tools creadas son instancias de Tool de pydantic_ai."""
        from pydantic_ai.tools import Tool as PydanticTool
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        capability = service.build_as_capability()

        for tool in capability.tools:
            assert isinstance(tool, PydanticTool)

    def test_tool_names_match_methods(self):
        """Los nombres de las tools coinciden con los métodos del servicio."""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        capability = service.build_as_capability()

        tool_names = [tool.name for tool in capability.tools]
        assert "create" in tool_names
        assert "get" in tool_names
        assert "delete" in tool_names

    def test_tool_has_run_context_param(self):
        """Cada tool tiene RunContext como primer parámetro en su función."""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        capability = service.build_as_capability()

        for tool in capability.tools:
            sig = inspect.signature(tool.function)
            params = list(sig.parameters.keys())
            assert params[0] == "ctx"

    def test_middleware_applied_before_tool_creation(self):
        """El middleware se aplica ANTES de crear la tool."""
        auth_mw = AuthMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[auth_mw]
        )
        capability = service.build_as_capability()

        # Todas las tools deben existir
        assert len(capability.tools) == 3

    def test_middleware_filters_methods(self):
        """ToolMiddleware con include solo aplica a métodos incluidos."""
        auth_mw = AuthMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[auth_mw]
        )
        capability = service.build_as_capability()

        # Todas las tools deben existir (create con middleware, get/delete sin)
        tool_names = [tool.name for tool in capability.tools]
        assert "create" in tool_names
        assert "get" in tool_names
        assert "delete" in tool_names

    def test_async_service_creates_async_tools(self):
        """Servicio async crea tools async."""
        service = Service(
            name="AsyncUser",
            service=AsyncUserService,
            instructions="Gestión async de usuarios"
        )
        capability = service.build_as_capability()

        for tool in capability.tools:
            assert inspect.iscoroutinefunction(tool.function)

    def test_multiple_middlewares_applied(self):
        """Múltiples middlewares se aplican al mismo método."""
        auth_mw = AuthMiddleware(include=["create"])
        log_mw = LogMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[auth_mw, log_mw]
        )
        capability = service.build_as_capability()

        # Todas las tools deben existir
        assert len(capability.tools) == 3

    def test_capability_has_instructions(self):
        """Capability conserva las instructions del servicio."""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestion de usuarios"
        )
        capability = service.build_as_capability()

        instructions = capability.get_instructions()
        assert "Gestion de usuarios" in instructions

    def test_capability_defer_loading(self):
        """Capability tiene defer_loading=True."""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        capability = service.build_as_capability()

        assert capability.defer_loading is True

