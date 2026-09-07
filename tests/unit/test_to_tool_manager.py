import pytest
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.exception import (
    AgentNotBuiltError,
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
