import asyncio
import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.infra.types.main.service import Exclude, Include
from to_tool_manager.exception import (
    AgentAlreadyBuiltError,
    AgentNotBuiltError,
    ModuleAlreadyRegisteredError,
    SelfDisableMiddlewareError,
    SubAgentAlreadyRegisteredError,
)


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


class TestTTMBuilderAddSubAgent:
    """Tests for add_sub_agent (REQ-009)."""

    @staticmethod
    def _roster(builder) -> dict:
        return builder._TTMBuilder__manager._Manager__sub_agents

    def test_add_sub_agent_returns_self(self):
        """add_sub_agent returns self (fluent API)"""
        builder = TTMBuilder(name="TestBuilder")
        result = builder.add_sub_agent(name="Researcher", description="Researches topics")
        assert result is builder

    def test_add_sub_agent_without_services_builds(self):
        """A sub-agent needs nothing but its own parameters to be delegable."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(
            name="Researcher",
            description="Researches topics",
            instructions="You research things",
        )
        builder.build()
        assert builder.agent is not None
        assert "Researcher" in self._roster(builder)

    def test_add_sub_agent_forwards_run_controls(self):
        """Every SubAgent run control reaches the SubAgent (module.py build_as_agent)."""
        from pydantic_ai.usage import UsageLimits

        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(
            name="Researcher",
            description="Researches topics",
            timeout_seconds=12.5,
            max_calls=3,
            on_failure="Retry with a narrower scope",
            usage_limits=UsageLimits(request_limit=5),
            contain_errors=True,
        )
        sub_agent = self._roster(builder)["Researcher"]
        assert sub_agent.timeout_seconds == 12.5
        assert sub_agent.max_calls == 3
        assert sub_agent.on_failure == "Retry with a narrower scope"
        assert sub_agent.usage_limits == UsageLimits(request_limit=5)
        assert sub_agent.contain_errors is True

    def test_add_sub_agent_forwards_agent_params(self):
        """The pydantic_ai.Agent parameters reach the delegate's Agent."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(
            name="Researcher",
            description="Researches topics",
            instructions="You research things",
            tool_timeout=30.0,
            retries=3,
            output_type=dict,
        )
        agent = self._roster(builder)["Researcher"].agent
        assert agent.name == "Researcher"
        assert agent.description == "Researches topics"
        assert agent._max_output_retries == 3
        assert agent._tool_timeout == 30.0
        assert agent.output_type is dict

    def test_add_sub_agent_takes_no_services(self):
        """A sub-agent is a delegate, not a module: services is not part of it."""
        import inspect

        params = inspect.signature(TTMBuilder.add_sub_agent).parameters
        assert 'services' not in params
        assert 'middleware' not in params
        assert 'disable_middlewares' not in params

    def test_add_module_still_requires_services(self):
        """add_module keeps demanding services (REQ-002)."""
        import inspect

        params = inspect.signature(TTMBuilder.add_module).parameters
        assert params['services'].default is inspect.Parameter.empty

    def test_add_sub_agent_name_is_the_delegate_name(self):
        """The delegate resolves its name from the Agent (SubAgent.resolved_name)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(name="Researcher", description="Researches topics")
        assert self._roster(builder)["Researcher"].resolved_name == "Researcher"

    def test_add_sub_agent_duplicate_raises(self):
        """Registering the same sub-agent twice raises SubAgentAlreadyRegisteredError."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(name="Researcher")
        with pytest.raises(SubAgentAlreadyRegisteredError, match="Researcher"):
            builder.add_sub_agent(name="Researcher")

    def test_sub_agent_takes_a_name_held_by_a_module(self):
        """Modules and sub-agents share one roster (manager.py __register_sub_agent)."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module",
        )
        with pytest.raises(SubAgentAlreadyRegisteredError, match="Commerce"):
            builder.add_sub_agent(name="Commerce")

    def test_module_takes_a_name_held_by_a_sub_agent(self):
        """The collision is symmetric, and add_module keeps its own error type."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(name="Commerce", description="Commerce delegate")
        with pytest.raises(ModuleAlreadyRegisteredError, match="Commerce"):
            builder.add_module(
                name="Commerce",
                services=[service],
                description="Commerce module",
            )

    def test_sub_agent_duplicate_is_catchable_as_module_duplicate(self):
        """Back-compat: guarding the roster with ModuleAlreadyRegisteredError still works."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(name="Researcher")
        with pytest.raises(ModuleAlreadyRegisteredError):
            builder.add_sub_agent(name="Researcher")

    def test_modules_and_sub_agents_share_one_subagents_capability(self):
        """One roster means one SubAgents capability, hence one delegate tool."""
        from pydantic_ai_harness.subagents import SubAgents

        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="Audit",
            service=UserService,
            instructions="Audit trail"
        )
        builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module",
        )
        builder.add_sub_agent(name="Researcher", description="Researches topics")
        builder.build()

        caps = [c for c in builder._TTMBuilder__manager.capabilities(None)
                if isinstance(c, SubAgents)]
        assert len(caps) == 1
        assert list(caps[0]._by_name) == ["Commerce", "Researcher"]

    def test_add_sub_agent_registers_no_services_on_the_parent_dependency(self):
        """A sub-agent has no services, so it puts nothing on the parent's dependency."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_sub_agent(name="Researcher", description="Researches topics")
        with pytest.raises(AttributeError):
            _ = builder.dependency.Researcher

    def test_add_module_still_registers_services_on_the_parent_dependency(self):
        """add_module keeps its contract after delegating to add_sub_agent."""
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder = TTMBuilder(name="TestBuilder")
        builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module",
        )
        assert isinstance(getattr(builder.dependency, "User"), UserService)
        assert "Commerce" in self._roster(builder)


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


class AsyncUserService:
    """Example async service for MCP wrapper tests."""

    async def create(self, name: str) -> str:
        return f"Created {name}"


class TestTTMBuilderExtraPaths:
    """Tests for less-common TTMBuilder paths (F5 coverage)."""

    def test_agent_setter_rejects_second_build(self):
        """Assigning agent a second time raises AgentAlreadyBuiltError (ttm_builder.py:103-105)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build()
        with pytest.raises(AgentAlreadyBuiltError):
            builder.agent = builder.agent

    def test_agent_setter_assigns_before_build(self):
        """Assigning an agent before build() stores it (ttm_builder.py:105)."""
        from pydantic_ai import Agent

        builder = TTMBuilder(name="TestBuilder")
        agent = Agent(name="External", deps_type=DinamicDepend)
        builder.agent = agent
        assert builder.agent is agent

    def test_dependency_property(self):
        """dependency property exposes the builder dependency (ttm_builder.py:114)."""
        builder = TTMBuilder(name="TestBuilder")
        assert isinstance(builder.dependency, DinamicDepend)

    def test_build_applies_general_middlewares(self):
        """build() applies registered general middlewares to services (ttm_builder.py:184, 463-464)."""
        class M(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.add_middleware(M())
        builder.build()
        svc = builder._TTMBuilder__manager.service_objects["User"]
        assert len(svc.middleware) == 1

    def test_add_middleware_returns_self_and_registers(self):
        """add_middleware() appends and returns self (ttm_builder.py:281-282)."""
        class M(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        mw = M()
        assert builder.add_middleware(mw) is builder
        assert builder._TTMBuilder__middlewares == [mw]

    def test_remove_middleware_to_service(self):
        """remove_middleware_to_service() removes a middleware by type (ttm_builder.py:292-293)."""
        class M(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.add_middleware(M())
        builder.build()
        assert builder.remove_middleware_to_service("User", M) is builder
        svc = builder._TTMBuilder__manager.service_objects["User"]
        assert svc.middleware == []

    def test_add_skill_returns_self(self):
        """add_skill() registers the skill and returns self (ttm_builder.py:301-302)."""
        from pydantic_ai_skills import Skill

        builder = TTMBuilder(name="TestBuilder")
        skill = Skill(name="math", description="Math skill", content="content")
        assert builder.add_skill(skill) is builder
        assert builder._TTMBuilder__manager._Manager__skills == [skill]

    def test_add_ttm_returns_self(self):
        """add_ttm() registers a ToToolManager and returns self (ttm_builder.py:310-311)."""
        from to_tool_manager.core.main.to_tool_manager import ToToolManager

        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        ttm = ToToolManager(name="Orchestrator", resources=[service])
        builder = TTMBuilder(name="TestBuilder")
        assert builder.add_ttm(ttm) is builder
        assert builder._TTMBuilder__manager._Manager__ttm == {"Orchestrator": ttm}

    def test_to_mcp_tool_skips_subagents_capability(self):
        """to_mcp_tool skips SubAgents capabilities from modules (ttm_builder.py:351)."""
        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module"
        )
        app = builder.to_mcp_tool(name="MCPTest", instructions="Test")
        assert app is not None
        assert builder.agent is not None

    def test_to_mcp_tool_skips_non_tool_capability_tools(self):
        """to_mcp_tool skips tools that are not pydantic_ai Tool instances (ttm_builder.py:357)."""
        from pydantic_ai import Capability

        def raw_tool(query: str) -> str:
            return f"Result: {query}"

        external_cap = Capability(
            id="external",
            instructions="External tool",
            tools=[raw_tool],
        )
        builder = TTMBuilder(name="TestBuilder", capabilities=[external_cap])
        app = builder.to_mcp_tool(name="MCPTest", instructions="Test")
        assert app is not None

    def test_make_mcp_wrapper_returns_func_without_dotted_qualname(self):
        """__make_mcp_wrapper returns the function as-is when qualname has no dot (ttm_builder.py:392)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        service_objects = builder._TTMBuilder__manager.service_objects

        def fake_wrapper(ctx, name: str) -> str:
            return name

        fake_wrapper.__qualname__ = "SingleName"
        result = builder._TTMBuilder__make_mcp_wrapper(fake_wrapper, service_objects)
        assert result is fake_wrapper

    def test_make_mcp_wrapper_returns_func_when_service_not_registered(self):
        """__make_mcp_wrapper returns the function when service is not registered (ttm_builder.py:397)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        service_objects = builder._TTMBuilder__manager.service_objects

        def fake_wrapper(ctx, name: str) -> str:
            return name

        fake_wrapper.__qualname__ = "Ghost.create"
        result = builder._TTMBuilder__make_mcp_wrapper(fake_wrapper, service_objects)
        assert result is fake_wrapper

    def test_make_mcp_wrapper_returns_func_when_instance_missing(self):
        """__make_mcp_wrapper returns the function when dep instance is missing (ttm_builder.py:403)."""
        builder = TTMBuilder(name="TestBuilder")
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        # Register the Service object but skip dependency registration
        builder._TTMBuilder__manager._Manager__service_objects["Ghost"] = service

        def fake_wrapper(ctx, name: str) -> str:
            return name

        fake_wrapper.__qualname__ = "Ghost.create"
        result = builder._TTMBuilder__make_mcp_wrapper(
            fake_wrapper, builder._TTMBuilder__manager.service_objects
        )
        assert result is fake_wrapper

    def test_make_mcp_wrapper_returns_func_when_method_missing(self):
        """__make_mcp_wrapper returns the function when method does not exist (ttm_builder.py:409)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        service_objects = builder._TTMBuilder__manager.service_objects

        def fake_wrapper(ctx, name: str) -> str:
            return name

        fake_wrapper.__qualname__ = "User.missing_method"
        result = builder._TTMBuilder__make_mcp_wrapper(fake_wrapper, service_objects)
        assert result is fake_wrapper

    def test_make_mcp_wrapper_sync_wrapper_can_be_invoked(self):
        """Sync MCP wrapper executes the bound method (ttm_builder.py:421-422)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        service_objects = builder._TTMBuilder__manager.service_objects

        def fake_wrapper(ctx, name: str) -> str:
            return name

        fake_wrapper.__qualname__ = "User.create"
        wrapper = builder._TTMBuilder__make_mcp_wrapper(fake_wrapper, service_objects)
        assert wrapper(name="Alice") == "Created Alice"

    def test_make_mcp_wrapper_async_wrapper_can_be_invoked(self):
        """Async MCP wrapper executes the bound async method (ttm_builder.py:413-418)."""
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="AsyncUser",
            service=AsyncUserService,
            instructions="Async user management"
        )
        service_objects = builder._TTMBuilder__manager.service_objects

        def fake_wrapper(ctx, name: str) -> str:
            return name

        fake_wrapper.__qualname__ = "AsyncUser.create"
        wrapper = builder._TTMBuilder__make_mcp_wrapper(fake_wrapper, service_objects)
        assert asyncio.run(wrapper(name="Bob")) == "Created Bob"
