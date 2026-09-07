import pytest
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.exception import (
    AgentNotBuiltError,
    SelfDisableMiddlewareError,
)
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Example service for testing."""

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


class TestModule:
    """Tests for the Module class."""

    def test_create_module(self):
        """Module is created correctly"""
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
        assert module.name == "Commerce"
        assert len(module.services) == 1
        assert module.description == "Commerce module"

    def test_module_disable_middlewares_default_empty(self):
        """disable_middlewares is empty tuple by default"""
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
        assert module.disable_middlewares == ()

    def test_module_disable_middlewares_custom(self):
        """disable_middlewares accepts tuple of strings"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            disable_middlewares=("AuthMiddleware",)
        )
        assert "AuthMiddleware" in module.disable_middlewares

    def test_build_as_agent_creates_subagent(self):
        """build_as_agent() creates a valid SubAgent"""
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
        subagent = module.build_as_agent()
        assert subagent is not None

    def test_build_as_agent_has_agent(self):
        """Module has agent after build_as_agent()"""
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
        module.build_as_agent()
        assert module.agent is not None
        assert module.agent.name == "Commerce"

    def test_build_as_agent_with_multiple_services(self):
        """build_as_agent() works with multiple services"""
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
        module = Module(
            name="Commerce",
            services=[user_service, order_service],
            description="Commerce module"
        )
        subagent = module.build_as_agent()
        assert subagent is not None

    def test_build_as_agent_applies_module_middlewares(self):
        """build_as_agent() applies module middlewares to services"""
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
        module.build_as_agent()
        # Middleware should have been added to the service
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_build_as_agent_respects_disable_middlewares(self):
        """build_as_agent() respects Service (parent) disable_middlewares"""
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
        # AuthMiddleware should have been filtered out
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        # LogMiddleware should be present
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_build_as_agent_without_module_middlewares(self):
        """build_as_agent() works without module middlewares"""
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
        module.build_as_agent()
        # Service middleware should remain as it was
        assert service.middleware == []

    def test_agent_property_before_build_raises(self):
        """agent property raises error before build_as_agent()"""
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
        with pytest.raises(AgentNotBuiltError):
            _ = module.agent


class TestModuleAgentParams:
    """Tests for Agent parameters in Module."""

    def test_module_stores_model(self):
        """Module stores the model parameter"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            model="gpt-4o"
        )
        assert module.model == "gpt-4o"

    def test_module_stores_instructions(self):
        """Module stores instructions"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            instructions="Custom instructions"
        )
        assert module.instructions == "Custom instructions"

    def test_module_stores_system_prompt(self):
        """Module stores system_prompt"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            system_prompt=["prompt1", "prompt2"]
        )
        assert module.system_prompt == ["prompt1", "prompt2"]

    def test_module_stores_tool_timeout(self):
        """Module stores tool_timeout"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            tool_timeout=30.0
        )
        assert module.tool_timeout == 30.0

    def test_module_stores_retries(self):
        """Module stores retries"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            retries=3
        )
        assert module.retries == 3

    def test_module_stores_output_type(self):
        """Module stores output_type"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            output_type=dict
        )
        assert module.output_type == dict

    def test_module_defaults_agent_params(self):
        """Module has correct defaults for Agent parameters"""
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
        assert module.model is None
        assert module.instructions is None
        assert module.system_prompt == ()
        assert module.tool_timeout is None
        assert module.retries is None
        assert module.output_type is str
        assert module.defer_model_check is False
        assert module.end_strategy == 'graceful'


class TestModuleSelfDisableValidation:
    """Tests for self-disable validation in middlewares."""

    def test_self_disable_raises_error(self):
        """Module raises error if it disables its own middleware"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        with pytest.raises(SelfDisableMiddlewareError, match="Cannot disable middleware"):
            Module(
                name="Commerce",
                services=[service],
                description="Commerce module",
                middleware=[AuthMiddleware()],
                disable_middlewares=("AuthMiddleware",)
            )

    def test_self_disable_multiple_middleware(self):
        """Module raises error if it disables any of its own middlewares"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        with pytest.raises(SelfDisableMiddlewareError, match="Cannot disable middleware"):
            Module(
                name="Commerce",
                services=[service],
                description="Commerce module",
                middleware=[AuthMiddleware(), LogMiddleware()],
                disable_middlewares=("LogMiddleware",)
            )

    def test_parent_disable_works(self):
        """Service can disable parent (Module) middlewares"""
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
            middleware=[AuthMiddleware(), LogMiddleware()]
        )
        module.build_as_agent()
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_no_middlewares_no_validation(self):
        """Module without middlewares does not validate disable_middlewares"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            disable_middlewares=("AuthMiddleware",)
        )
        assert module.disable_middlewares == ("AuthMiddleware",)

    def test_no_disable_no_validation(self):
        """Module without disable_middlewares does not validate"""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[AuthMiddleware()]
        )
        assert len(module.middleware) == 1
