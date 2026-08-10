"""
Tests for the orchestrator layer's `capabilities` pass-through -- the
Fase 6 gap found while integrating pydantic-ai-harness `Planning`:
`AgentSupport.build_agent()` called the module-level `build_agent()` with
NO `capabilities=` at all, so a `Planning` capability (or any other) could
never reach an orchestrated agent, regardless of what the caller did.

These are integration-style: they build a REAL `pydantic_ai.Agent`
through the full `AgentInterface -> AgentSupport -> build_agent()` chain,
now that build_agent() itself can construct one (see the constructor fix
in adapters/pydantic_ai.py).
"""
from __future__ import annotations

import asyncio

import pytest
from pydantic_ai import Agent
from pydantic_ai_harness.planning import Planning, InMemoryPlanStore

from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport
from to_tool_manager.skills.task_planning import task_planning_skill


class Order:
    """Manages customer orders."""

    def create(self, product_name: str) -> str:
        """Creates a new order.

        Args:
            product_name: Name of the product to order.
        """
        return f"Order '{product_name}' created"


def _resolve_system_prompt_text(agent: Agent) -> str:
    class _FakeCtx:
        prompt = "irrelevant for the static-prefix assertions below"

    runner = agent._system_prompt_functions[0]  # type: ignore[attr-defined]
    return asyncio.run(runner.function(_FakeCtx()))


class _ConcreteAgent(AgentInterface):
    def _create_services(self) -> None:
        self.agent.add_service("Order", Order)

    def _create_modules(self) -> None:
        pass

    def _create_plan(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 1. Baseline -- omitting `capabilities` preserves the exact prior behavior.
# ---------------------------------------------------------------------------


class TestAgentSupportCapabilitiesBaseline:
    def test_agent_support_without_capabilities_defaults_to_empty(self):
        support = AgentSupport(model="test")
        assert support.capabilities == []

    def test_orchestrated_agent_without_capabilities_has_no_task_planning_content(self):
        agent = _ConcreteAgent(model="test")
        agent.build_agent()
        prompt = _resolve_system_prompt_text(agent.agent.agent)
        assert task_planning_skill.content not in prompt


# ---------------------------------------------------------------------------
# 2. `capabilities` now actually reaches the built Agent, via both the
#    constructor kwarg and the fluent `add_capability()` method.
# ---------------------------------------------------------------------------


class TestAgentSupportCapabilitiesWiring:
    def test_add_capability_is_reflected_in_capabilities_property(self):
        support = AgentSupport(model="test")
        planning = Planning()
        support.add_capability(planning)
        assert support.capabilities == [planning]

    def test_orchestrated_agent_with_planning_via_constructor_injects_guidance(self):
        agent = _ConcreteAgent(model="test", capabilities=[Planning()])
        agent.build_agent()
        prompt = _resolve_system_prompt_text(agent.agent.agent)
        assert task_planning_skill.content in prompt

    def test_orchestrated_agent_with_planning_via_add_capability_injects_guidance(self):
        agent = _ConcreteAgent(model="test")
        agent.agent.add_capability(Planning(store=InMemoryPlanStore()))
        agent.build_agent()
        prompt = _resolve_system_prompt_text(agent.agent.agent)
        assert task_planning_skill.content in prompt

    def test_orchestrated_agent_with_planning_is_a_real_pydantic_ai_agent(self):
        agent = _ConcreteAgent(model="test", capabilities=[Planning()])
        agent.build_agent()
        assert isinstance(agent.agent.agent, Agent)
