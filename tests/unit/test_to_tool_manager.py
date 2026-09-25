import pytest
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.exception import (
    AgentNotBuiltError,
    InvalidResourceTypeError,
    MiddlewareNotInitializedError,
    MiddlewareTargetMismatchError,
    ServiceNotFoundError,
)
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Example service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class PublicService:
    """Example public service."""

    def list(self) -> list:
        return []


class AuthMiddleware(Middleware):
    """Example authentication middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(Middleware):
    """Example logging middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestToToolManager:
    """Tests for the ToToolManager class."""

    def test_create_with_services(self):
        """ToToolManager creates with services"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        assert manager.name == "TestManager"
        assert "User" in manager.services

    def test_create_with_modules(self):
        """ToToolManager creates with modules"""
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
        assert "Commerce" in manager.modules

    def test_get_service(self):
        """get_service returns service by name"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        retrieved = manager.get_service("User")
        assert retrieved.name == "User"

    def test_get_service_not_found(self):
        """get_service raises error if not found"""
        manager = ToToolManager(
            name="TestManager",
            resources=[]
        )
        with pytest.raises(ServiceNotFoundError):
            manager.get_service("NonExistent")

    def test_resolve_middlewares_filters_disabled(self):
        """_resolve_middlewares() excludes disabled middlewares"""
        service = Service(
            name="Public",
            service=PublicService,
            instructions="Public API",
            disable_middlewares=("AuthMiddleware",)
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[AuthMiddleware(), LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(service)
        assert not any(m.name == "AuthMiddleware" for m in resolved)
        assert any(m.name == "LogMiddleware" for m in resolved)

    def test_resolve_middlewares_includes_service_level(self):
        """_resolve_middlewares() includes service-level middlewares"""
        mw = ConcreteToolMiddleware(include=["create"])
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=[mw]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(service)
        assert mw in resolved
        assert any(m.name == "LogMiddleware" for m in resolved)

    def test_build_agent(self):
        """build_agent() creates a valid agent"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        agent = manager.build_agent()
        assert agent is not None
        assert agent.name == "TestManager"

    def test_agent_property_after_build(self):
        """agent property returns agent after build"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        manager.build_agent()
        assert manager.agent is not None

    def test_agent_property_before_build_raises(self):
        """agent property raises error before build"""
        manager = ToToolManager(
            name="TestManager",
            resources=[]
        )
        with pytest.raises(AgentNotBuiltError):
            _ = manager.agent


class TestToToolManagerAgentParams:
    """Tests for Agent parameters in ToToolManager."""

    def test_stores_model(self):
        """ToToolManager stores model"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            model="gpt-4o"
        )
        assert manager._ToToolManager__agent_params['model'] == "gpt-4o"

    def test_stores_instructions(self):
        """ToToolManager stores instructions"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            instructions="Custom instructions"
        )
        assert manager._ToToolManager__agent_params['instructions'] == "Custom instructions"

    def test_stores_system_prompt(self):
        """ToToolManager stores system_prompt"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            system_prompt=["prompt1"]
        )
        assert manager._ToToolManager__agent_params['system_prompt'] == ["prompt1"]

    def test_stores_tool_timeout(self):
        """ToToolManager stores tool_timeout"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            tool_timeout=30.0
        )
        assert manager._ToToolManager__agent_params['tool_timeout'] == 30.0

    def test_stores_retries(self):
        """ToToolManager stores retries"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            retries=3
        )
        assert manager._ToToolManager__agent_params['retries'] == 3

    def test_stores_output_type(self):
        """ToToolManager stores output_type"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            output_type=dict
        )
        assert manager._ToToolManager__agent_params['output_type'] == dict

    def test_stores_description(self):
        """ToToolManager stores description"""
        manager = ToToolManager(
            name="TestManager",
            resources=[],
            description="Test description"
        )
        assert manager._ToToolManager__agent_params['description'] == "Test description"

    def test_defaults_agent_params(self):
        """ToToolManager has correct defaults"""
        manager = ToToolManager(
            name="TestManager",
            resources=[]
        )
        params = manager._ToToolManager__agent_params
        assert params['model'] is None
        assert params['instructions'] is None
        assert params['system_prompt'] == ()
        assert params['tool_timeout'] is None
        assert params['retries'] is None
        assert params['output_type'] is str
        assert params['defer_model_check'] is False
        assert params['end_strategy'] == 'graceful'

    def test_build_agent_with_params(self):
        """build_agent() uses Agent parameters"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            instructions="Custom instructions",
            tool_timeout=30.0,
            retries=3,
        )
        agent = manager.build_agent()
        assert agent is not None
        assert agent.name == "TestManager"


class TestToToolManagerEdgePaths:
    """Tests for less-common ToToolManager paths (F4 coverage)."""

    def test_invalid_resource_type_raises(self):
        """ToToolManager raises for invalid resource type (to_tool_manager.py:95)."""
        with pytest.raises(InvalidResourceTypeError, match="str"):
            ToToolManager(name="TestManager", resources=["not-a-resource"])

    def test_middlewares_property_raises_when_none(self):
        """middlewares property raises MiddlewareNotInitializedError (to_tool_manager.py:120-122)."""
        manager = ToToolManager(name="TestManager", resources=[])
        with pytest.raises(MiddlewareNotInitializedError):
            _ = manager.middlewares

    def test_get_service_returns_module(self):
        """get_service returns module when name matches a module (to_tool_manager.py:135)."""
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
        manager = ToToolManager(name="TestManager", resources=[module])
        retrieved = manager.get_service("Commerce")
        assert isinstance(retrieved, Module)
        assert retrieved.name == "Commerce"

    def test_add_middleware_to_service(self):
        """add_middleware_to_service appends middleware to a service (to_tool_manager.py:184-189)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(name="TestManager", resources=[service])
        mw = ConcreteToolMiddleware()
        manager.add_middleware_to_service("User", mw)
        assert mw in service.middleware

    def test_add_middleware_to_service_init_none(self):
        """add_middleware_to_service initializes None middleware list (to_tool_manager.py:186-187)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=None
        )
        manager = ToToolManager(name="TestManager", resources=[service])
        mw = ConcreteToolMiddleware()
        manager.add_middleware_to_service("User", mw)
        assert mw in service.middleware

    def test_add_middleware_to_service_target_mismatch(self):
        """add_middleware_to_service raises on module target (to_tool_manager.py:190)."""
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
        manager = ToToolManager(name="TestManager", resources=[module])
        with pytest.raises(MiddlewareTargetMismatchError, match="Service"):
            manager.add_middleware_to_service("Commerce", ConcreteToolMiddleware())

    def test_add_middleware_to_module(self):
        """add_middleware_to_module appends middleware to a module (to_tool_manager.py:198-203)."""
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
        manager = ToToolManager(name="TestManager", resources=[module])
        mw = ConcreteToolMiddleware()
        manager.add_middleware_to_module("Commerce", mw)
        assert mw in module.middleware

    def test_add_middleware_to_module_init_none(self):
        """add_middleware_to_module initializes None middleware list (to_tool_manager.py:200-201)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=None
        )
        manager = ToToolManager(name="TestManager", resources=[module])
        mw = ConcreteToolMiddleware()
        manager.add_middleware_to_module("Commerce", mw)
        assert mw in module.middleware

    def test_add_middleware_to_module_target_mismatch(self):
        """add_middleware_to_module raises on service target (to_tool_manager.py:204)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(name="TestManager", resources=[service])
        with pytest.raises(MiddlewareTargetMismatchError, match="Module"):
            manager.add_middleware_to_module("User", ConcreteToolMiddleware())

    def test_remove_middleware_to_service(self):
        """remove_middleware_to_service removes by type (to_tool_manager.py:212-215)."""
        mw = ConcreteToolMiddleware()
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            middleware=[mw]
        )
        manager = ToToolManager(name="TestManager", resources=[service])
        manager.remove_middleware_to_service("User", ConcreteToolMiddleware)
        assert service.middleware == []

    def test_remove_middleware_to_service_target_mismatch(self):
        """remove_middleware_to_service raises on module target (to_tool_manager.py:217)."""
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
        manager = ToToolManager(name="TestManager", resources=[module])
        with pytest.raises(MiddlewareTargetMismatchError, match="Service"):
            manager.remove_middleware_to_service("Commerce", ConcreteToolMiddleware)

    def test_remove_middleware_to_module(self):
        """remove_middleware_to_module removes by type (to_tool_manager.py:225-228)."""
        mw = ConcreteToolMiddleware()
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
        manager = ToToolManager(name="TestManager", resources=[module])
        manager.remove_middleware_to_module("Commerce", ConcreteToolMiddleware)
        assert module.middleware == []

    def test_remove_middleware_to_module_target_mismatch(self):
        """remove_middleware_to_module raises on service target (to_tool_manager.py:230)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(name="TestManager", resources=[service])
        with pytest.raises(MiddlewareTargetMismatchError, match="Module"):
            manager.remove_middleware_to_module("User", ConcreteToolMiddleware)

    def test_build_agent_with_provided_resources(self):
        """build_agent accepts resources and middlewares overrides (to_tool_manager.py:245-251, 258)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        manager = ToToolManager(name="TestManager", resources=[])
        mw = ConcreteToolMiddleware()
        agent = manager.build_agent(resources=[service], middlewares=[mw])
        assert agent is not None
        assert agent.name == "TestManager"
        assert manager.middlewares == [mw]

    def test_build_agent_with_provided_module(self):
        """build_agent builds sub-agents from provided modules (to_tool_manager.py:250-251, 267)."""
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
        manager = ToToolManager(name="TestManager", resources=[])
        agent = manager.build_agent(resources=[module])
        assert agent is not None
        assert agent.name == "TestManager"
