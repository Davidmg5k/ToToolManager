"""Fase 0.5 (D6) smoke test.

`pydantic-ai>=2.10.0` used to have no upper bound in pyproject.toml. A
routine dependency resolution bump (no code change on our side) once
silently pulled in a version whose `Agent.__init__` no longer accepted a
callable `system_prompt` -- crashing `build_agent()` on EVERY call, with
nothing in the test suite catching it (see section 2.1 of the roadmap).

This module is that missing safety net: it builds and RUNS a real `Agent`
(no stubs/mocks) against whatever pydantic-ai-family versions actually get
resolved for this environment, and fails loudly if that stops working --
regardless of whether the reason is a code change here or a dependency
bump. It intentionally does not assert exact version numbers (that's what
the ranges in pyproject.toml are for); it asserts *behavior*.
"""
import asyncio

import pytest


def test_resolved_versions_are_within_declared_ranges():
    """Documents (and fails loudly if violated) the version ranges
    pinned in pyproject.toml's `pydantic-ai` optional-dependency group,
    so a resolver picking something outside the tested range is caught
    here instead of silently in production."""
    from importlib.metadata import version

    from packaging.specifiers import SpecifierSet
    from packaging.version import Version

    declared = {
        "pydantic-ai": ">=2.10.0,<3.0.0",
        "pydantic-ai-harness": ">=0.7.0,<1.0.0",
        "pydantic-ai-skills": ">=1.2.0,<2.0.0",
        "subagents-pydantic-ai": ">=0.2.10,<0.3.0",
    }
    for package, spec in declared.items():
        installed = Version(version(package))
        assert installed in SpecifierSet(spec), (
            f"{package}=={installed} is outside the range declared in "
            f"pyproject.toml ({spec}) -- pyproject.toml and this smoke "
            f"test have drifted apart."
        )


def test_build_agent_smoke_service_only():
    """Real Agent, real Service, real TestModel -- no mocks anywhere in
    this call chain. If a future pydantic-ai-family release changes how
    Agent.__init__ handles any of build_agent()'s arguments, this fails
    here instead of at the first real user call."""
    from pydantic_ai.models.test import TestModel

    from to_tool_manager.adapters.pydantic_ai import build_agent
    from to_tool_manager.core.manager import ToToolManager
    from to_tool_manager.core.service import Service

    class Greeter:
        def hello(self, name: str) -> str:
            """Say hello to someone."""
            return f"Hello {name}"

    manager = ToToolManager([Service(name="greeter", service=Greeter)])
    agent = build_agent(TestModel(call_tools=[]), manager)

    result = asyncio.run(agent.run("say hi to Bob"))
    assert result.output is not None


def test_build_agent_smoke_with_capabilities_and_module():
    """Same as above, but exercises the two riskiest surfaces at once:
    a dynamic (callable) system_prompt via a real Planning() capability,
    and a Module (real sub-agent wiring via subagents-pydantic-ai)."""
    from pydantic_ai.models.test import TestModel
    from pydantic_ai_harness.planning import Planning

    from to_tool_manager.adapters.pydantic_ai import build_agent
    from to_tool_manager.core.manager import ToToolManager
    from to_tool_manager.core.module import Module
    from to_tool_manager.core.service import Service

    class Greeter:
        def hello(self, name: str) -> str:
            """Say hello to someone."""
            return f"Hello {name}"

    module = Module(name="GreeterModule", services=[Service(name="g", service=Greeter)])
    manager = ToToolManager([module])

    agent = build_agent(TestModel(call_tools=[]), manager, capabilities=[Planning()])

    result = asyncio.run(agent.run("plan something"))
    assert result.output is not None
    planning_msgs = [
        m for m in result.all_messages()
        if getattr(m, "instructions", None) and "write_plan" in m.instructions
    ]
    assert planning_msgs, "Planning capability guidance not found -- capabilities wiring regressed."


def test_build_agent_smoke_via_agent_interface_orchestrator():
    """End-to-end through the higher-level AgentInterface/AgentOrchestrator
    layer too, not just the low-level build_agent() -- catches regressions
    in AgentSupport/AgentInterface/AgentOrchestrator's own passthrough of
    model/capabilities/name, not only in the adapter itself."""
    from pydantic_ai.models.test import TestModel

    from to_tool_manager.orchestrator.agent_orchestrator import AgentOrchestrator
    from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface

    class Greeter:
        def hello(self, name: str) -> str:
            """Say hello to someone."""
            return f"Hello {name}"

    class SmokeAgent(AgentInterface):
        def _create_services(self):
            from to_tool_manager.core.service import Service
            self.agent.add_service("greeter", Greeter)

        def _create_modules(self):
            pass

        def _create_plan(self):
            pass

    orchestrator = AgentOrchestrator([SmokeAgent(model=TestModel(call_tools=[]), name="smoke")])
    orchestrator.init_app(model=TestModel(call_tools=[]))

    result = asyncio.run(orchestrator.agent.run("say hi"))
    assert result.output is not None
