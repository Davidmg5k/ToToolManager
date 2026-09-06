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
    """Servicio de ejemplo para testing."""

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


class TestModule:
    """Tests para la clase Module."""

    def test_create_module(self):
        """Module se crea correctamente"""
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
        assert module.name == "Commerce"
        assert len(module.services) == 1
        assert module.description == "Módulo de comercio"

    def test_module_disable_middlewares_default_empty(self):
        """disable_middlewares es tuple vacío por defecto"""
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
        assert module.disable_middlewares == ()

    def test_module_disable_middlewares_custom(self):
        """disable_middlewares acepta tupla de strings"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            disable_middlewares=("AuthMiddleware",)
        )
        assert "AuthMiddleware" in module.disable_middlewares

    def test_build_as_agent_creates_subagent(self):
        """build_as_agent() crea un SubAgent válido"""
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
        subagent = module.build_as_agent()
        assert subagent is not None

    def test_build_as_agent_has_agent(self):
        """Module tiene agent después de build_as_agent()"""
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
        module.build_as_agent()
        assert module.agent is not None
        assert module.agent.name == "Commerce"

    def test_build_as_agent_with_multiple_services(self):
        """build_as_agent() funciona con múltiples servicios"""
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
        module = Module(
            name="Commerce",
            services=[user_service, order_service],
            description="Módulo de comercio"
        )
        subagent = module.build_as_agent()
        assert subagent is not None

    def test_build_as_agent_applies_module_middlewares(self):
        """build_as_agent() aplica middlewares del módulo a servicios"""
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
        module.build_as_agent()
        # El middleware debe haberse añadido al servicio
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_build_as_agent_respects_disable_middlewares(self):
        """build_as_agent() respeta disable_middlewares del Service (padre)"""
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
        # AuthMiddleware debe haberse filtrado
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        # LogMiddleware debe estar presente
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_build_as_agent_without_module_middlewares(self):
        """build_as_agent() funciona sin middlewares del módulo"""
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
        module.build_as_agent()
        # Service middleware debe permanecer como estaba
        assert service.middleware == []

    def test_agent_property_before_build_raises(self):
        """agent property lanza error antes de build_as_agent()"""
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
        with pytest.raises(AgentNotBuiltError):
            _ = module.agent


class TestModuleAgentParams:
    """Tests para parámetros Agent en Module."""

    def test_module_stores_model(self):
        """Module almacena el parámetro model"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            model="gpt-4o"
        )
        assert module.model == "gpt-4o"

    def test_module_stores_instructions(self):
        """Module almacena instructions"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            instructions="Custom instructions"
        )
        assert module.instructions == "Custom instructions"

    def test_module_stores_system_prompt(self):
        """Module almacena system_prompt"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            system_prompt=["prompt1", "prompt2"]
        )
        assert module.system_prompt == ["prompt1", "prompt2"]

    def test_module_stores_tool_timeout(self):
        """Module almacena tool_timeout"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            tool_timeout=30.0
        )
        assert module.tool_timeout == 30.0

    def test_module_stores_retries(self):
        """Module almacena retries"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            retries=3
        )
        assert module.retries == 3

    def test_module_stores_output_type(self):
        """Module almacena output_type"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            output_type=dict
        )
        assert module.output_type == dict

    def test_module_defaults_agent_params(self):
        """Module tiene defaults correctos para parámetros Agent"""
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
        assert module.model is None
        assert module.instructions is None
        assert module.system_prompt == ()
        assert module.tool_timeout is None
        assert module.retries is None
        assert module.output_type is str
        assert module.defer_model_check is False
        assert module.end_strategy == 'graceful'


class TestModuleSelfDisableValidation:
    """Tests para validación de self-disable en middlewares."""

    def test_self_disable_raises_error(self):
        """Module lanza error si deshabilita su propio middleware"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        with pytest.raises(SelfDisableMiddlewareError, match="Cannot disable middleware"):
            Module(
                name="Commerce",
                services=[service],
                description="Módulo de comercio",
                middleware=[AuthMiddleware()],
                disable_middlewares=("AuthMiddleware",)
            )

    def test_self_disable_multiple_middleware(self):
        """Module lanza error si deshabilita cualquier middleware propio"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        with pytest.raises(SelfDisableMiddlewareError, match="Cannot disable middleware"):
            Module(
                name="Commerce",
                services=[service],
                description="Módulo de comercio",
                middleware=[AuthMiddleware(), LogMiddleware()],
                disable_middlewares=("LogMiddleware",)
            )

    def test_parent_disable_works(self):
        """Service puede deshabilitar middlewares del padre (Module)"""
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
            middleware=[AuthMiddleware(), LogMiddleware()]
        )
        module.build_as_agent()
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_no_middlewares_no_validation(self):
        """Module sin middlewares no valida disable_middlewares"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            disable_middlewares=("AuthMiddleware",)
        )
        assert module.disable_middlewares == ("AuthMiddleware",)

    def test_no_disable_no_validation(self):
        """Module sin disable_middlewares no valida"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[AuthMiddleware()]
        )
        assert len(module.middleware) == 1
