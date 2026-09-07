import inspect
import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.middleware.middleware import ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Example service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    def delete(self, id: int) -> bool:
        return True


class AsyncUserService:
    """Example async service for testing."""

    async def create(self, name: str) -> str:
        return f"Created {name}"

    async def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class AuthMiddleware(ConcreteToolMiddleware):
    """Example authentication middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(ConcreteToolMiddleware):
    """Example logging middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestService:
    """Tests for the Service class."""

    def test_build_as_capability(self):
        """Service returns Capability"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()
        assert capability.id == "User"

    def test_add_middleware(self):
        """Service allows adding middlewares"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        mw = ConcreteToolMiddleware()
        service.add_middleware(mw)
        assert mw in service.middleware

    def test_disable_middlewares_default_empty(self):
        """disable_middlewares is empty tuple by default"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        assert service.disable_middlewares == ()

    def test_disable_middlewares_custom(self):
        """disable_middlewares accepts tuple of strings"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            disable_middlewares=("AuthMiddleware", "LogMiddleware")
        )
        assert "AuthMiddleware" in service.disable_middlewares
        assert "LogMiddleware" in service.disable_middlewares

    def test_service_is_not_frozen(self):
        """Service is NOT frozen (add_middleware() needs to mutate)"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        # Service allows mutation because add_middleware() adds to self.middleware
        service.name = "Other"
        assert service.name == "Other"

    def test_service_has_slots(self):
        """Service has slots for efficiency"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        assert not hasattr(service, '__dict__')

    def test_middleware_default_empty_list(self):
        """middleware is empty list by default"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        assert service.middleware == []

    def test_include_default_none(self):
        """include is None by default"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        assert service.include is None

    def test_exclude_default_none(self):
        """exclude is None by default"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        assert service.exclude is None


class TestBuildAsCapability:
    """Tests for build_as_capability() with auto-discovery."""

    def test_creates_capability_with_tools(self):
        """build_as_capability() creates Capability with tools from all methods."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()

        # Should have 3 tools: create, get, delete
        assert len(capability.tools) == 3

    def test_tools_are_tool_instances(self):
        """Created tools are instances of pydantic_ai Tool."""
        from pydantic_ai.tools import Tool as PydanticTool
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()

        for tool in capability.tools:
            assert isinstance(tool, PydanticTool)

    def test_tool_names_match_methods(self):
        """Tool names match the service methods."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()

        tool_names = [tool.name for tool in capability.tools]
        assert "create" in tool_names
        assert "get" in tool_names
        assert "delete" in tool_names

    def test_tool_has_run_context_param(self):
        """Each tool has RunContext as the first parameter in its function."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()

        for tool in capability.tools:
            sig = inspect.signature(tool.function)
            params = list(sig.parameters.keys())
            assert params[0] == "ctx"

    def test_middleware_applied_before_tool_creation(self):
        """Middleware is applied BEFORE creating the tool."""
        auth_mw = AuthMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=[auth_mw]
        )
        capability = service.build_as_capability()

        # All tools should exist
        assert len(capability.tools) == 3

    def test_middleware_filters_methods(self):
        """ToolMiddleware with include only applies to included methods."""
        auth_mw = AuthMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=[auth_mw]
        )
        capability = service.build_as_capability()

        # All tools should exist (create with middleware, get/delete without)
        tool_names = [tool.name for tool in capability.tools]
        assert "create" in tool_names
        assert "get" in tool_names
        assert "delete" in tool_names

    def test_async_service_creates_async_tools(self):
        """Async service creates async tools."""
        service = Service(
            name="AsyncUser",
            service=AsyncUserService,
            instructions="Async user management"
        )
        capability = service.build_as_capability()

        for tool in capability.tools:
            assert inspect.iscoroutinefunction(tool.function)

    def test_multiple_middlewares_applied(self):
        """Multiple middlewares applied to the same method."""
        auth_mw = AuthMiddleware(include=["create"])
        log_mw = LogMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=[auth_mw, log_mw]
        )
        capability = service.build_as_capability()

        # All tools should exist
        assert len(capability.tools) == 3

    def test_capability_has_instructions(self):
        """Capability preserves the service instructions."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()

        instructions = capability.get_instructions()
        assert "User management" in instructions

    def test_capability_defer_loading(self):
        """Capability has defer_loading=True."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        capability = service.build_as_capability()

        assert capability.defer_loading is True

