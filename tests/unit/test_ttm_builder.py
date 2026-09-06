import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service
from to_tool_manager.infra.types.main.service import Include, Exclude
from to_tool_manager.infra.types.main.signature import MethodsType
from to_tool_manager.exception import AgentNotBuiltError, SelfDisableMiddlewareError


class UserService:
    """Servicio de ejemplo para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class TestTTMBuilder:
    """Tests para la clase TTMBuilder."""

    def test_empty_builder(self):
        """Builder vacío lanza error al acceder a agent"""
        builder = TTMBuilder(name="TestBuilder")
        with pytest.raises(AgentNotBuiltError):
            _ = builder.agent

    def test_add_service_returns_self(self):
        """add_service retorna self (fluent API)"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        assert result is builder

    def test_fluent_interface(self):
        """Fluent API permite encadenar llamadas"""
        builder = TTMBuilder(name="TestBuilder")
        result = (
            builder
            .add_service(
                name="User",
                service=UserService,
                instructions="Gestión de usuarios"
            )
        )
        assert result is builder

    def test_build_creates_agent(self):
        """build() crea agente válido"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        builder.build()
        assert builder.agent is not None
        assert builder.agent.name == "TestBuilder"

    def test_context_manager(self):
        """Context manager llama build() automáticamente"""
        with TTMBuilder(name="TestBuilder") as builder:
            builder.add_service(
                name="User",
                service=UserService,
                instructions="Gestión de usuarios"
            )
        assert builder.agent is not None

    def test_agent_property_before_build_raises(self):
        """agent property lanza error antes de build"""
        builder = TTMBuilder(name="TestBuilder")
        with pytest.raises(AgentNotBuiltError):
            _ = builder.agent


class TestTTMBuilderAgentParams:
    """Tests para parámetros Agent en TTMBuilder."""

    def test_builder_stores_model(self):
        """TTMBuilder almacena model"""
        builder = TTMBuilder(name="TestBuilder", model="gpt-4o")
        assert builder._TTMBuilder__model == "gpt-4o"

    def test_builder_stores_instructions(self):
        """TTMBuilder almacena instructions"""
        builder = TTMBuilder(name="TestBuilder", instructions="Custom instructions")
        assert builder._TTMBuilder__instructions == "Custom instructions"

    def test_builder_stores_system_prompt(self):
        """TTMBuilder almacena system_prompt"""
        builder = TTMBuilder(name="TestBuilder", system_prompt=["prompt1"])
        assert builder._TTMBuilder__system_prompt == ["prompt1"]

    def test_builder_stores_tool_timeout(self):
        """TTMBuilder almacena tool_timeout"""
        builder = TTMBuilder(name="TestBuilder", tool_timeout=30.0)
        assert builder._TTMBuilder__tool_timeout == 30.0

    def test_builder_stores_retries(self):
        """TTMBuilder almacena retries"""
        builder = TTMBuilder(name="TestBuilder", retries=3)
        assert builder._TTMBuilder__retries == 3

    def test_builder_stores_output_type(self):
        """TTMBuilder almacena output_type"""
        builder = TTMBuilder(name="TestBuilder", output_type=dict)
        assert builder._TTMBuilder__output_type == dict

    def test_builder_stores_description(self):
        """TTMBuilder almacena description"""
        builder = TTMBuilder(name="TestBuilder", description="Test description")
        assert builder._TTMBuilder__description == "Test description"

    def test_build_model_priority(self):
        """build() model tiene prioridad sobre __init__ model"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        builder.build(model=None)
        assert builder.agent is not None

    def test_build_uses_init_model_when_no_param(self):
        """build() usa model de __init__ cuando no se pasa parámetro"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        builder.build()
        assert builder.agent is not None

    def test_build_defaults_agent_params(self):
        """TTMBuilder tiene defaults correctos para parámetros Agent"""
        builder = TTMBuilder(name="TestBuilder")
        assert builder._TTMBuilder__model is None
        assert builder._TTMBuilder__instructions is None
        assert builder._TTMBuilder__system_prompt == ()
        assert builder._TTMBuilder__tool_timeout is None
        assert builder._TTMBuilder__retries is None
        assert builder._TTMBuilder__output_type is str
        assert builder._TTMBuilder__defer_model_check is False
        assert builder._TTMBuilder__end_strategy == 'graceful'


class TestTTMBuilderAddServiceParams:
    """Tests para parámetros de add_service."""

    def test_add_service_with_disable_middlewares(self):
        """add_service acepta disable_middlewares"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            disable_middlewares=("AuthMiddleware",)
        )
        assert result is builder

    def test_add_service_with_include(self):
        """add_service acepta include"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            include=frozenset({"create"})
        )
        assert result is builder

    def test_add_service_with_exclude(self):
        """add_service acepta exclude"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            exclude=frozenset({"delete"})
        )
        assert result is builder

    def test_add_service_with_include_class(self):
        """add_service acepta Include dataclass"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            include=Include(include=["create", "get"])
        )
        assert result is builder

    def test_add_service_with_exclude_class(self):
        """add_service acepta Exclude dataclass"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            exclude=Exclude(exclude=["delete"])
        )
        assert result is builder

    def test_add_service_with_args_kwargs(self):
        """add_service acepta args y kwargs"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            args=(),
            kwargs={}
        )
        assert result is builder


class TestTTMBuilderAddModuleParams:
    """Tests para parámetros de add_module."""

    def test_add_module_with_middleware(self):
        """add_module acepta middleware"""
        from to_tool_manager.core.middleware.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        result = builder.add_module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[TestMW()]
        )
        assert result is builder

    def test_add_module_with_disable_middlewares(self):
        """add_module acepta disable_middlewares (desde padre)"""
        from to_tool_manager.core.middleware.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            disable_middlewares=("TestMW",)
        )
        result = builder.add_module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[TestMW()],
        )
        assert result is builder

    def test_add_module_self_disable_raises(self):
        """add_module lanza error si deshabilita su propio middleware"""
        from to_tool_manager.core.middleware.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        with pytest.raises(SelfDisableMiddlewareError, match="Cannot disable middleware"):
            builder.add_module(
                name="Commerce",
                services=[service],
                description="Módulo de comercio",
                middleware=[TestMW()],
                disable_middlewares=("TestMW",)
            )

    def test_add_module_with_agent_params(self):
        """add_module acepta parámetros Agent"""
        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        result = builder.add_module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            instructions="Custom instructions",
            tool_timeout=30.0,
            retries=3,
            output_type=dict,
        )
        assert result is builder
