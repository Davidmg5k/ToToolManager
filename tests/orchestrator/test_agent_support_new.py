"""FASE 8: Tests for add_service, add_module full signatures and skills support."""
import pytest
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport
from to_tool_manager.core.service import Service
from to_tool_manager.core.discovery import Visibility
from to_tool_manager.core.types import ErrorMap


class DummyService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


class AnotherService:
    def run(self) -> str:
        return "running"


class FailingService:
    def fail(self) -> str:
        raise ValueError("intentional failure")


# ============================================================
# add_service - happy path: all params
# ============================================================
class TestAddServiceFullParams:

    def test_all_params(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service(
            "Dummy",
            DummyService,
            description="A dummy service",
            visibility=frozenset({"public", "internal"}),
            include=frozenset({"greet"}),
            exclude=frozenset(),
            expose_properties=True,
            error_map=ErrorMap(),
            error_rules=tuple(),
            sanitize_system_errors=False,
            singleton=False,
            middlewares=(),
            disable_middlewares=("auth",),
            args=("arg1",),
            kwargs={"key": "val"},
        )
        svc = support.services[0]
        assert svc.name == "Dummy"
        assert svc.description == "A dummy service"
        assert svc.visibility == frozenset({"public", "internal"})
        assert svc.include == frozenset({"greet"})
        assert svc.exclude == frozenset()
        assert svc.expose_properties is True
        assert svc.singleton is False
        assert svc.sanitize_system_errors is False
        assert svc.disable_middlewares == ("auth",)
        assert svc.args == ("arg1",)
        assert svc.kwargs == {"key": "val"}

    def test_defaults_only_backward_compat(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        svc = support.services[0]
        assert svc.name == "Dummy"
        assert svc.service is DummyService
        assert svc.description == ""
        assert svc.singleton is True
        assert svc.sanitize_system_errors is True

    def test_visibility_frozen_set(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service(
            "Dummy", DummyService,
            visibility=frozenset({"internal"}),
        )
        assert support.services[0].visibility == frozenset({"internal"})

    def test_include_exclude_overlap_raises(self):
        support = AgentSupport(model="openai:gpt-4o")
        with pytest.raises(ValueError, match="both `include` and `exclude`"):
            support.add_service(
                "Dummy", DummyService,
                include=frozenset({"greet", "run"}),
                exclude=frozenset({"run"}),
            )

    def test_custom_error_map(self):
        em = ErrorMap().map(ValueError, category="bad_input")
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService, error_map=em)
        assert support.services[0].error_map is em

    def test_custom_error_rules(self):
        def my_rule(exc: Exception):
            return ("custom", False) if isinstance(exc, TypeError) else None

        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService, error_rules=(my_rule,))
        assert support.services[0].error_rules == (my_rule,)

    def test_non_singleton(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService, singleton=False)
        assert support.services[0].singleton is False

    def test_with_middlewares(self):
        from to_tool_manager.security.middleware import Middleware

        class TestMW(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        mw = TestMW()
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService, middlewares=(mw,))
        assert support.services[0].middlewares == (mw,)

    def test_disable_middlewares(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service(
            "Dummy", DummyService,
            disable_middlewares=("auth", "logging"),
        )
        assert support.services[0].disable_middlewares == ("auth", "logging")


# ============================================================
# add_module - happy path: all params
# ============================================================
class TestAddModuleFullParams:

    def test_all_params(self):
        svc = Service(name="Dummy", service=DummyService)
        support = AgentSupport(model="openai:gpt-4o")
        support.add_module(
            "TestModule",
            [svc],
            description="A test module",
            system_prompt="You are a test module.",
            instructions="be precise",
            model="openai:gpt-4o",
            subagent_mode="async",
            include_efficiency_appendix=False,
            middlewares=(),
            disable_middlewares=("auth",),
        )
        mod = support.modules[0]
        assert mod.name == "TestModule"
        assert mod.description == "A test module"
        assert mod.system_prompt == "You are a test module."
        assert mod.instructions == "be precise"
        assert mod.model == "openai:gpt-4o"
        assert mod.subagent_mode == "async"
        assert mod.include_efficiency_appendix is False
        assert mod.disable_middlewares == ("auth",)

    def test_defaults_only_backward_compat(self):
        svc = Service(name="Dummy", service=DummyService)
        support = AgentSupport(model="openai:gpt-4o")
        support.add_module("TestModule", [svc])
        mod = support.modules[0]
        assert mod.name == "TestModule"
        assert mod.description == ""
        assert mod.model is None
        assert mod.subagent_mode == "sync"
        assert mod.include_efficiency_appendix is True

    def test_custom_model(self):
        svc = Service(name="Dummy", service=DummyService)
        support = AgentSupport(model="openai:gpt-4o")
        support.add_module("M", [svc], model="groq:llama-3.1-8b-instant")
        assert support.modules[0].model == "groq:llama-3.1-8b-instant"

    def test_subagent_modes(self):
        svc = Service(name="Dummy", service=DummyService)
        for mode in ("sync", "async", "auto"):
            support = AgentSupport(model="openai:gpt-4o")
            support.add_module("M", [svc], subagent_mode=mode)
            assert support.modules[0].subagent_mode == mode


# ============================================================
# Skills support
# ============================================================
class TestSkillsSupport:

    def test_init_no_skills(self):
        support = AgentSupport(model="openai:gpt-4o")
        assert support.skills == []

    def test_init_with_skills(self):
        from pydantic_ai_skills import Skill
        sk = Skill(name="test", description="test", content="test content")
        support = AgentSupport(model="openai:gpt-4o", skills=[sk])
        assert len(support.skills) == 1

    def test_add_skill(self):
        from pydantic_ai_skills import Skill
        support = AgentSupport(model="openai:gpt-4o")
        sk = Skill(name="test", description="test", content="test content")
        support.add_skill(sk)
        assert len(support.skills) == 1
        assert support.skills[0] is sk

    def test_add_skills_batch(self):
        from pydantic_ai_skills import Skill
        support = AgentSupport(model="openai:gpt-4o")
        sk1 = Skill(name="s1", description="d1", content="c1")
        sk2 = Skill(name="s2", description="d2", content="c2")
        support.add_skills([sk1, sk2])
        assert len(support.skills) == 2

    def test_skills_property_returns_copy(self):
        from pydantic_ai_skills import Skill
        support = AgentSupport(model="openai:gpt-4o")
        support.add_skill(Skill(name="s", description="d", content="c"))
        skills = support.skills
        skills.clear()
        assert len(support.skills) == 1

    def test_skills_forwarded_to_build_agent(self):
        from pydantic_ai.models.test import TestModel
        from pydantic_ai_skills import Skill

        support = AgentSupport(model=TestModel(call_tools=[]))
        support.add_service("Dummy", DummyService)
        sk = Skill(name="test", description="test", content="test content")
        support.add_skill(sk)
        support.build_agent()
        assert support.agent is not None

    def test_empty_skills_no_effect(self):
        from pydantic_ai.models.test import TestModel

        support = AgentSupport(model=TestModel(call_tools=[]))
        support.add_service("Dummy", DummyService)
        support.build_agent()
        assert support.agent is not None
