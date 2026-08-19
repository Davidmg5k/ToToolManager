import pytest
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport
from to_tool_manager.core.service import Service


class DummyService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


class AnotherService:
    def run(self) -> str:
        return "running"


class TestAgentSupport:
    def test_init(self):
        support = AgentSupport(model="openai:gpt-4o")
        assert support.services == []
        assert support.modules == []

    def test_init_with_middleware(self):
        from to_tool_manager.security.middleware import Middleware

        class TestMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        support = AgentSupport(model="openai:gpt-4o", middleware=[TestMiddleware()])
        assert support.services == []

    def test_manager_property_not_initialized(self):
        support = AgentSupport(model="openai:gpt-4o")
        with pytest.raises(RuntimeError, match="Manager not initialized"):
            _ = support._manager

    def test_agent_property_not_initialized(self):
        support = AgentSupport(model="openai:gpt-4o")
        with pytest.raises(RuntimeError, match="Agent not initialized"):
            _ = support.agent

    def test_add_service(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        assert len(support.services) == 1
        assert support.services[0].name == "Dummy"

    def test_add_multiple_services(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        support.add_service("Another", AnotherService)
        assert len(support.services) == 2

    def test_add_module(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc])
        assert len(support.modules) == 1
        assert support.modules[0].name == "TestModule"

    def test_add_services_to_module(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc1 = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc1])

        svc2 = Service(name="Another", service=AnotherService)
        support.add_services_to_module("TestModule", [svc2])

        module = support.modules[0]
        assert len(module.services) == 2

    def test_add_services_to_module_not_found(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc = Service(name="Dummy", service=DummyService)
        with pytest.raises(ValueError, match="Module 'Nonexistent' not found"):
            support.add_services_to_module("Nonexistent", [svc])

    def test_add_services_to_module_duplicate_name(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc1 = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc1])

        svc2 = Service(name="Dummy", service=AnotherService)
        with pytest.raises(ValueError, match="Service 'Dummy' already exists"):
            support.add_services_to_module("TestModule", [svc2])

    def test_services_property_returns_copy(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        services = support.services
        services.clear()
        assert len(support.services) == 1

    def test_modules_property_returns_copy(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc])
        modules = support.modules
        modules.clear()
        assert len(support.modules) == 1


class TestAgentSupportCapabilities:
    """Capabilities passthrough: AgentSupport does not implement any
    capability logic itself -- it only forwards to build_agent(), which
    already supports `capabilities` (see adapters/pydantic_ai.py)."""

    def test_init_with_no_capabilities_defaults_to_empty(self):
        support = AgentSupport(model="openai:gpt-4o")
        assert support.capabilities == []

    def test_init_with_capabilities(self):
        sentinel = object()
        support = AgentSupport(model="openai:gpt-4o", capabilities=[sentinel])
        assert support.capabilities == [sentinel]

    def test_add_capability_appends(self):
        support = AgentSupport(model="openai:gpt-4o")
        cap_a, cap_b = object(), object()
        support.add_capability(cap_a)
        support.add_capability(cap_b)
        assert support.capabilities == [cap_a, cap_b]

    def test_add_capability_is_fluent(self):
        support = AgentSupport(model="openai:gpt-4o")
        cap_a, cap_b = object(), object()
        result = support.add_capability(cap_a).add_capability(cap_b)
        assert result is support
        assert support.capabilities == [cap_a, cap_b]

    def test_name_defaults_to_none(self):
        support = AgentSupport(model="openai:gpt-4o")
        assert support.name is None

    def test_name_is_stored(self):
        support = AgentSupport(model="openai:gpt-4o", name="my_agent")
        assert support.name == "my_agent"

    def test_capabilities_property_returns_copy(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_capability(object())
        caps = support.capabilities
        caps.clear()
        assert len(support.capabilities) == 1

    def test_build_agent_with_planning_capability_end_to_end(self):
        """Real Agent construction (no mocks) with the Planning capability
        wired through AgentSupport, against pydantic-ai's own TestModel.
        Regression guard for the constructor bug in build_agent() (a
        dynamic system_prompt callable used to crash Agent.__init__) and
        for the capabilities passthrough added to AgentSupport."""
        from pydantic_ai.models.test import TestModel
        from pydantic_ai_harness.planning import Planning

        support = AgentSupport(model=TestModel(call_tools=[]))
        support.add_service("Dummy", DummyService)
        support.add_capability(Planning())
        support.build_agent()

        agent = support.agent
        assert agent is not None

        import asyncio
        result = asyncio.run(agent.run("plan something"))
        # The Planning capability injects `write_plan` guidance into the
        # agent's instructions -- confirms capabilities actually reached
        # the real Agent, not just that construction didn't crash.
        planning_msgs = [
            m for m in result.all_messages()
            if getattr(m, "instructions", None) and "write_plan" in m.instructions
        ]
        assert planning_msgs, "Planning capability guidance not found in agent instructions"


class TestAgentSupportAdvancedInitKwargs:
    """Coverage for the ~17 optional kwargs added to AgentSupport.__init__
    (alongside hallazgo 1.1's build_agent() reorder fix), which
    build_agent() only forwards to the underlying `build_agent()` call
    when explicitly set (Principio 1: no default-behavior change for
    existing callers)."""

    def test_build_agent_with_no_optional_kwargs_matches_pre_existing_behavior(self):
        """Baseline: omitting every new kwarg must build exactly the same
        Agent as before these kwargs existed."""
        from pydantic_ai.models.test import TestModel

        support = AgentSupport(model=TestModel(call_tools=[]))
        support.add_service("Dummy", DummyService)
        support.build_agent()

        assert support.agent.name is None

    def test_build_agent_forwards_name(self):
        from pydantic_ai.models.test import TestModel

        support = AgentSupport(model=TestModel(call_tools=[]), name="my_support_agent")
        support.add_service("Dummy", DummyService)
        support.build_agent()

        assert support.agent.name == "my_support_agent"

    def test_build_agent_forwards_system_prompt_end_to_end(self):
        """Real Agent construction with an explicit system_prompt --
        confirms the kwarg actually reaches Agent.__init__ and the agent
        still runs (also exercises the Sequence[str] normalization fix
        from hallazgo 1.2 #4)."""
        import asyncio
        from pydantic_ai.models.test import TestModel

        support = AgentSupport(
            model=TestModel(call_tools=[]),
            system_prompt=["You are terse.", "Never explain yourself."],
        )
        support.add_service("Dummy", DummyService)
        support.build_agent()

        result = asyncio.run(support.agent.run("hello"))
        assert result.output is not None

    def test_build_agent_forwards_output_type(self):
        from dataclasses import dataclass

        from pydantic_ai.models.test import TestModel

        @dataclass
        class Answer:
            text: str

        support = AgentSupport(model=TestModel(call_tools=[]), output_type=Answer)
        support.add_service("Dummy", DummyService)
        support.build_agent()

        assert support.agent.output_type is Answer

    def test_build_agent_forwards_remaining_optional_kwargs(self):
        """Exercises every other `kw[...] = ...` branch in
        AgentSupport.build_agent() not already covered by a more targeted
        test above -- instructions, description, model_settings, retries,
        deps_type, validation_context, tool_timeout, max_concurrency,
        end_strategy, defer_model_check, metadata, planning_mode,
        include_general_purpose_subagent, subagent_usage_limits. One
        combined construction (rather than one test per kwarg) since the
        only thing at risk per-kwarg is a typo'd dict key or an argument
        pydantic-ai's own Agent.__init__ rejects -- both of which surface
        as an exception from build_agent() either way."""
        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import UsageLimits

        support = AgentSupport(
            model=TestModel(call_tools=[]),
            instructions="be helpful",
            description="A test agent",
            model_settings={"temperature": 0.1},
            retries=2,
            deps_type=dict,
            validation_context={"env": "test"},
            tool_timeout=5.0,
            max_concurrency=2,
            end_strategy="early",
            defer_model_check=True,
            metadata={"team": "test"},
            planning_mode="off",
            include_general_purpose_subagent=True,
            subagent_usage_limits=UsageLimits(),
        )
        support.add_service("Dummy", DummyService)
        support.build_agent()

        assert support.agent is not None