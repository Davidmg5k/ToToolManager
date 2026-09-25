import pytest
from pydantic_ai_skills import Skill
from to_tool_manager.core.builder.manager import Manager
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.exception import (
    ModuleAlreadyRegisteredError,
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
    ToToolManagerAlreadyRegisteredError,
    ToToolManagerNotFoundError,
)


class UserService:
    """Example service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"


class OrderService:
    """Order service for testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"


class ConcreteMiddleware(Middleware):
    """Concrete middleware for testing."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestManagerToolsets:
    """Tests for Manager.toolsets()."""

    def test_toolsets_includes_skills(self):
        """toolsets() includes registered skills (manager.py:45)."""
        manager = Manager()
        skill = Skill(name="math", description="Math skill", content="content")
        manager.add_skill(skill)
        result = manager.toolsets(None)
        assert result == [skill]

    def test_toolsets_combines_skills_and_custom(self):
        """toolsets() appends provided toolsets after skills (manager.py:49)."""
        manager = Manager()
        skill = Skill(name="math", description="Math skill", content="content")
        manager.add_skill(skill)
        result = manager.toolsets(["custom-toolset"])
        assert result == [skill, "custom-toolset"]


class TestManagerRegistration:
    """Tests for duplicate registration errors."""

    def test_add_service_duplicate_raises(self):
        """Adding the same service twice raises ServiceAlreadyRegisteredError (manager.py:84)."""
        manager = Manager()
        dep = DinamicDepend()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager.add_service(service, dep)
        with pytest.raises(ServiceAlreadyRegisteredError, match="User"):
            manager.add_service(service, dep)

    def test_add_module_duplicate_raises(self):
        """Adding the same module twice raises ModuleAlreadyRegisteredError (manager.py:97)."""
        manager = Manager()
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
        manager.add_module(module)
        with pytest.raises(ModuleAlreadyRegisteredError, match="Commerce"):
            manager.add_module(module)

    def test_remove_middleware_from_services_not_found_raises(self):
        """Removing middleware from an unknown service raises (manager.py:142)."""
        manager = Manager()
        with pytest.raises(ServiceNotFoundError, match="Ghost"):
            manager.remove_middleware_from_services("Ghost", ConcreteMiddleware)

    def test_apply_middlewares_to_services_initializes_none(self):
        """apply_middlewares_to_services initializes None middleware lists (manager.py:158)."""
        manager = Manager()
        dep = DinamicDepend()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=None
        )
        manager.add_service(service, dep)
        mw = ConcreteMiddleware()
        manager.apply_middlewares_to_services([mw])
        assert service.middleware == [mw]


class TestManagerTTMDelegation:
    """Tests for ToToolManager delegation methods."""

    def _ttm_with_service(self) -> tuple[Manager, ToToolManager, Service]:
        manager = Manager()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        ttm = ToToolManager(name="Orchestrator", resources=[service])
        manager.add_ttm(ttm)
        return manager, ttm, service

    def test_add_middleware_to_service_via_ttm(self):
        """add_middleware_to_service delegates to ToToolManager (manager.py:114-115)."""
        manager, ttm, service = self._ttm_with_service()
        mw = ConcreteMiddleware()
        manager.add_middleware_to_service("Orchestrator", "User", mw)
        assert mw in service.middleware

    def test_add_middleware_to_module_via_ttm(self):
        """add_middleware_to_module delegates to ToToolManager (manager.py:123-124)."""
        manager = Manager()
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
        ttm = ToToolManager(name="Orchestrator", resources=[module])
        manager.add_ttm(ttm)
        mw = ConcreteMiddleware()
        manager.add_middleware_to_module("Orchestrator", "Commerce", mw)
        assert mw in module.middleware

    def test_remove_middleware_to_service_via_ttm(self):
        """remove_middleware_to_service delegates to ToToolManager (manager.py:132-133)."""
        mw = ConcreteMiddleware()
        manager = Manager()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=[mw]
        )
        ttm = ToToolManager(name="Orchestrator", resources=[service])
        manager.add_ttm(ttm)
        manager.remove_middleware_to_service("Orchestrator", "User", ConcreteMiddleware)
        assert service.middleware == []

    def test_remove_middleware_to_module_via_ttm(self):
        """remove_middleware_to_module delegates to ToToolManager (manager.py:176-177)."""
        mw = ConcreteMiddleware()
        manager = Manager()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[mw]
        )
        ttm = ToToolManager(name="Orchestrator", resources=[module])
        manager.add_ttm(ttm)
        manager.remove_middleware_to_module("Orchestrator", "Commerce", ConcreteMiddleware)
        assert module.middleware == []


class TestManagerTTMErrors:
    """Tests for ToToolManager registration errors."""

    def test_add_ttm_duplicate_raises(self):
        """Adding the same ToToolManager twice raises (manager.py:187)."""
        manager = Manager()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        ttm = ToToolManager(name="Orchestrator", resources=[service])
        manager.add_ttm(ttm)
        with pytest.raises(ToToolManagerAlreadyRegisteredError, match="Orchestrator"):
            manager.add_ttm(ttm)

    def test_get_ttm_not_found_raises(self):
        """Delegation to an unknown ToToolManager raises (manager.py:196-198)."""
        manager = Manager()
        with pytest.raises(ToToolManagerNotFoundError, match="Missing"):
            manager.add_middleware_to_service("Missing", "User", ConcreteMiddleware())