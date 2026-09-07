import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service
from to_tool_manager.infra.types.main.service import Include, Exclude
from to_tool_manager.infra.types.main.signature import MethodsType
from to_tool_manager.exception import AgentNotBuiltError, SelfDisableMiddlewareError


class UserService:
    """Example service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class TestTTMBuilder:
    """Tests for the TTMBuilder class."""

    def test_empty_builder(self):
        """Empty builder raises error when accessing agent"""
        builder = TTMBuilder(name="TestBuilder")
        with pytest.raises(AgentNotBuiltError):
            _ = builder.agent

    def test_add_service_returns_self(self):
        """add_service returns self (fluent API)"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        assert result is builder

    def test_fluent_interface(self):
        """Fluent API allows chaining calls"""
        builder = TTMBuilder(name="TestBuilder")
        result = (
            builder
            .add_service(
                name="User",
                service=UserService,
                instructions="User management"
            )
        )
        assert result is builder

    def test_build_creates_agent(self):
        """build() creates valid agent"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build()
        assert builder.agent is not None
        assert builder.agent.name == "TestBuilder"

    def test_context_manager(self):
        """Context manager calls build() automatically"""
        with TTMBuilder(name="TestBuilder") as builder:
            builder.add_service(
                name="User",
                service=UserService,
                instructions="User management"
            )
        assert builder.agent is not None

    def test_agent_property_before_build_raises(self):
        """agent property raises error before build"""
        builder = TTMBuilder(name="TestBuilder")
        with pytest.raises(AgentNotBuiltError):
            _ = builder.agent


class TestTTMBuilderAgentParams:
    """Tests for Agent parameters in TTMBuilder."""

    def test_builder_stores_model(self):
        """TTMBuilder stores model"""
        builder = TTMBuilder(name="TestBuilder", model="gpt-4o")
        assert builder._TTMBuilder__model == "gpt-4o"

    def test_builder_stores_instructions(self):
        """TTMBuilder stores instructions"""
        builder = TTMBuilder(name="TestBuilder", instructions="Custom instructions")
        assert builder._TTMBuilder__instructions == "Custom instructions"

    def test_builder_stores_system_prompt(self):
        """TTMBuilder stores system_prompt"""
        builder = TTMBuilder(name="TestBuilder", system_prompt=["prompt1"])
        assert builder._TTMBuilder__system_prompt == ["prompt1"]

    def test_builder_stores_tool_timeout(self):
        """TTMBuilder stores tool_timeout"""
        builder = TTMBuilder(name="TestBuilder", tool_timeout=30.0)
        assert builder._TTMBuilder__tool_timeout == 30.0

    def test_builder_stores_retries(self):
        """TTMBuilder stores retries"""
        builder = TTMBuilder(name="TestBuilder", retries=3)
        assert builder._TTMBuilder__retries == 3

    def test_builder_stores_output_type(self):
        """TTMBuilder stores output_type"""
        builder = TTMBuilder(name="TestBuilder", output_type=dict)
        assert builder._TTMBuilder__output_type == dict

    def test_builder_stores_description(self):
        """TTMBuilder stores description"""
        builder = TTMBuilder(name="TestBuilder", description="Test description")
        assert builder._TTMBuilder__description == "Test description"

    def test_build_model_priority(self):
        """build() model has priority over __init__ model"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(model=None)
        assert builder.agent is not None

    def test_build_uses_init_model_when_no_param(self):
        """build() uses __init__ model when no parameter is passed"""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build()
        assert builder.agent is not None

    def test_build_defaults_agent_params(self):
        """TTMBuilder has correct defaults for Agent parameters"""
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
    """Tests for add_service parameters."""

    def test_add_service_with_disable_middlewares(self):
        """add_service accepts disable_middlewares"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management",
            disable_middlewares=("AuthMiddleware",)
        )
        assert result is builder

    def test_add_service_with_include(self):
        """add_service accepts include"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management",
            include=frozenset({"create"})
        )
        assert result is builder

    def test_add_service_with_exclude(self):
        """add_service accepts exclude"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management",
            exclude=frozenset({"delete"})
        )
        assert result is builder

    def test_add_service_with_include_class(self):
        """add_service accepts Include dataclass"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management",
            include=Include(include=["create", "get"])
        )
        assert result is builder

    def test_add_service_with_exclude_class(self):
        """add_service accepts Exclude dataclass"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management",
            exclude=Exclude(exclude=["delete"])
        )
        assert result is builder

    def test_add_service_with_args_kwargs(self):
        """add_service accepts args and kwargs"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_service(
            name="User",
            service=UserService,
            instructions="User management",
            args=(),
            kwargs={}
        )
        assert result is builder


class TestTTMBuilderAddModuleParams:
    """Tests for add_module parameters."""

    def test_add_module_with_middleware(self):
        """add_module accepts middleware"""
        from to_tool_manager.core.middleware.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        result = builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[TestMW()]
        )
        assert result is builder

    def test_add_module_with_disable_middlewares(self):
        """add_module accepts disable_middlewares (from parent)"""
        from to_tool_manager.core.middleware.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="User management",
            disable_middlewares=("TestMW",)
        )
        result = builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[TestMW()],
        )
        assert result is builder

    def test_add_module_self_disable_raises(self):
        """add_module raises error if it disables its own middleware"""
        from to_tool_manager.core.middleware.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        with pytest.raises(SelfDisableMiddlewareError, match="Cannot disable middleware"):
            builder.add_module(
                name="Commerce",
                services=[service],
                description="Commerce module",
                middleware=[TestMW()],
                disable_middlewares=("TestMW",)
            )

    def test_add_module_with_agent_params(self):
        """add_module accepts Agent parameters"""
        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        result = builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            instructions="Custom instructions",
            tool_timeout=30.0,
            retries=3,
            output_type=dict,
        )
        assert result is builder


class TestTTMBuilderBuildParams:
    """Tests for build() parameters with priority over __init__."""

    def test_build_with_instructions_priority(self):
        """build() instructions has priority over __init__ instructions"""
        builder = TTMBuilder(
            name="TestBuilder",
            instructions="Init instructions"
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(instructions="Build instructions")
        assert builder.agent is not None

    def test_build_with_system_prompt_priority(self):
        """build() system_prompt has priority over __init__ system_prompt"""
        builder = TTMBuilder(
            name="TestBuilder",
            system_prompt=["Init prompt"]
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(system_prompt=["Build prompt"])
        assert builder.agent is not None

    def test_build_with_tool_timeout_priority(self):
        """build() tool_timeout has priority over __init__ tool_timeout"""
        builder = TTMBuilder(
            name="TestBuilder",
            tool_timeout=10.0
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(tool_timeout=30.0)
        assert builder.agent is not None

    def test_build_with_retries_priority(self):
        """build() retries has priority over __init__ retries"""
        builder = TTMBuilder(
            name="TestBuilder",
            retries=1
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(retries=5)
        assert builder.agent is not None

    def test_build_with_output_type_priority(self):
        """build() output_type has priority over __init__ output_type"""
        builder = TTMBuilder(
            name="TestBuilder",
            output_type=str
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(output_type=dict)
        assert builder.agent is not None

    def test_build_with_description_priority(self):
        """build() description has priority over __init__ description"""
        builder = TTMBuilder(
            name="TestBuilder",
            description="Init description"
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build(description="Build description")
        assert builder.agent is not None

    def test_build_uses_init_params_when_none(self):
        """build() uses __init__ parameters when build() passes None"""
        builder = TTMBuilder(
            name="TestBuilder",
            instructions="Init instructions",
            tool_timeout=10.0,
            retries=1,
            output_type=str,
            description="Init description"
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        # build() without parameters should use __init__ ones
        builder.build()
        assert builder.agent is not None

    def test_build_mixed_params_priority(self):
        """build() mixed priority: some params from build, others from __init__"""
        builder = TTMBuilder(
            name="TestBuilder",
            instructions="Init instructions",
            tool_timeout=10.0,
            retries=1
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        # Only override instructions and tool_timeout
        builder.build(
            instructions="Build instructions",
            tool_timeout=30.0
        )
        assert builder.agent is not None


class TestTTMBuilderToMcpTool:
    """Tests for TTMBuilder.to_mcp_tool (REQ-008)."""

    def test_to_mcp_tool_returns_fastmcp(self):
        """to_mcp_tool returns FastMCP instance."""
        from fastmcp import FastMCP

        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        app = builder.to_mcp_tool(name="MCPTest", instructions="Test MCP")
        assert isinstance(app, FastMCP)

    def test_to_mcp_tool_name_and_instructions(self):
        """to_mcp_tool passes name and instructions correctly."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        app = builder.to_mcp_tool(name="MyMCP", instructions="My instructions")
        assert app.name == "MyMCP"
        assert app.instructions == "My instructions"

    def test_to_mcp_tool_extracts_tools_from_service(self):
        """to_mcp_tool extracts tools from registered service."""
        import asyncio

        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        app = builder.to_mcp_tool(name="MCPTest", instructions="Test")
        tools = asyncio.run(app.list_tools())
        tool_names = {t.name for t in tools}
        assert "User__create" in tool_names
        assert "User__get" in tool_names

    def test_to_mcp_tool_auto_builds(self):
        """to_mcp_tool auto-builds if build() was not called."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        # We don't call build() explicitly
        app = builder.to_mcp_tool(name="MCPTest", instructions="Test")
        assert builder.agent is not None
        assert app is not None

    def test_to_mcp_tool_with_external_capabilities(self):
        """to_mcp_tool includes external capabilities."""
        import asyncio
        from pydantic_ai import Capability
        from pydantic_ai.tools import Tool

        def external_tool(query: str) -> str:
            return f"Result: {query}"

        external_cap = Capability(
            id="external",
            instructions="External tool",
            tools=[Tool(external_tool)],
        )

        builder = TTMBuilder(
            name="TestBuilder",
            capabilities=[external_cap]
        )
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        app = builder.to_mcp_tool(name="MCPTest", instructions="Test")
        tools = asyncio.run(app.list_tools())
        tool_names = {t.name for t in tools}
        assert "external_tool" in tool_names
        assert "User__create" in tool_names
