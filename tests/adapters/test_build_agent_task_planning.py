"""
Tests for `build_agent`'s interaction with pydantic-ai-harness `Planning`.

These are split into two groups on purpose:

1. Baseline tests (no `Planning` involved) -- these exist because
   `build_agent`, despite being the central integration point documented
   under Niveles 5/12/15/19 of the README, had zero direct unit tests
   before this change. They pin down the exact contract this module
   relies on: no `capabilities=` passed -> no capability-related content
   anywhere in the resulting agent's system prompt.
2. Task-planning detection tests -- verify `build_agent` auto-detects a
   `Planning` capability instance and injects the boundary-guidance skill
   ONLY in that case, appended to the static (non-gated) part of the
   prompt so it stays cache-stable across turns.
"""
from __future__ import annotations

import pytest

from to_tool_manager import Service, ToToolManager
from to_tool_manager.adapters.pydantic_ai import build_agent, _has_task_planning_capability
from to_tool_manager.skills.task_planning import task_planning_skill

from pydantic_ai_harness.planning import Planning, InMemoryPlanStore


class Order:
    """Manages customer orders."""

    def __init__(self) -> None:
        self._orders: list[str] = []

    def create(self, product_name: str) -> str:
        """Creates a new order.

        Args:
            product_name: Name of the product to order.
        """
        self._orders.append(product_name)
        return f"Order '{product_name}' created"


@pytest.fixture
def manager() -> ToToolManager:
    return ToToolManager([
        Service(name="Order", service=Order, description="Manages orders."),
    ])


def _resolve_system_prompt_text(agent) -> str:
    """The dynamic system prompt is registered post-construction via
    `agent.system_prompt(fn)` (see the fix in `build_agent`), so it lives
    in `_system_prompt_functions[0]`, not in a constructor kwarg.
    """
    import asyncio

    class _FakeCtx:
        prompt = "irrelevant for the static-prefix assertions below"

    runner = agent._system_prompt_functions[0]
    return asyncio.run(runner.function(_FakeCtx()))


# ---------------------------------------------------------------------------
# 1. Baseline -- byte-identical behavior with no `capabilities` involved.
# ---------------------------------------------------------------------------


class TestBuildAgentConstructsRealAgent:
    """Regression test for a pre-existing, unrelated bug found while
    writing these tests: `Agent.__init__` in currently-resolved
    `pydantic-ai` (>=2.10.0 resolves to 2.27.0 today) only accepts
    `system_prompt: str | Sequence[str]`, not the dynamic callable
    `_make_gated_system_prompt` produces -- `build_agent()` raised
    `TypeError: 'function' object is not iterable` for every call,
    unconditionally, before the fix. Confirmed via `git stash` that this
    reproduced on a clean `main` checkout, unrelated to task planning.
    """

    def test_build_agent_constructs_a_real_pydantic_ai_agent(self, manager):
        from pydantic_ai import Agent

        agent = build_agent("test", manager)
        assert isinstance(agent, Agent)

    def test_dynamic_system_prompt_is_registered_and_resolves(self, manager):
        agent = build_agent("test", manager)
        assert len(agent._system_prompt_functions) == 1
        prompt = _resolve_system_prompt_text(agent)
        assert isinstance(prompt, str) and prompt != ""


class TestBuildAgentBaseline:
    def test_build_agent_without_capabilities_has_no_task_planning_content(self, manager):
        agent = build_agent("test", manager)
        prompt = _resolve_system_prompt_text(agent)
        assert task_planning_skill.content not in prompt

    def test_build_agent_with_unrelated_capabilities_has_no_task_planning_content(self, manager):
        class NotPlanning:
            """Looks nothing like a harness Planning capability."""

        agent = build_agent("test", manager, capabilities=[NotPlanning()])
        prompt = _resolve_system_prompt_text(agent)
        assert task_planning_skill.content not in prompt

    def test_detection_helper_false_on_empty_list(self):
        assert _has_task_planning_capability([]) is False

    def test_detection_helper_false_on_unrelated_object(self):
        assert _has_task_planning_capability([object()]) is False


# ---------------------------------------------------------------------------
# 2. Detection -- Planning() present -> guidance injected, and ONLY then.
# ---------------------------------------------------------------------------


class TestTaskPlanningDetection:
    def test_detection_helper_true_for_planning_instance(self):
        assert _has_task_planning_capability([Planning()]) is True

    def test_detection_helper_true_when_planning_mixed_with_other_capabilities(self):
        class Other:
            pass

        assert _has_task_planning_capability([Other(), Planning()]) is True

    def test_build_agent_with_planning_capability_injects_guidance(self, manager):
        agent = build_agent("test", manager, capabilities=[Planning()])
        prompt = _resolve_system_prompt_text(agent)
        assert task_planning_skill.content in prompt

    def test_build_agent_with_planning_capability_and_store_injects_guidance(self, manager):
        agent = build_agent(
            "test",
            manager,
            capabilities=[Planning(store=InMemoryPlanStore())],
        )
        prompt = _resolve_system_prompt_text(agent)
        assert task_planning_skill.content in prompt

    def test_build_agent_with_custom_system_prompt_still_gets_guidance_appended(self, manager):
        agent = build_agent(
            "test",
            manager,
            system_prompt="You are a custom assistant.",
            capabilities=[Planning()],
        )
        prompt = _resolve_system_prompt_text(agent)
        assert "You are a custom assistant." in prompt
        assert task_planning_skill.content in prompt


# ---------------------------------------------------------------------------
# 3. No tool-name collisions between the built-in Planner and harness
#    Planning, when both are wired into the same agent (Requerimiento 3).
# ---------------------------------------------------------------------------


class TestNoToolNameCollisionWithPlanner:
    def test_planner_and_planning_tool_names_are_disjoint(self, manager):
        from to_tool_manager.core.planner import Planner
        from pydantic_ai_harness.planning._toolset import available_tool_names

        planner = manager.with_planner()
        planner_tool_names = {t["name"] for t in planner.build_tools()}
        harness_tool_names = available_tool_names(subtasks=True)

        assert planner_tool_names.isdisjoint(harness_tool_names)

    def test_build_agent_with_both_planner_and_planning_capability_does_not_raise(self, manager):
        planner = manager.with_planner()
        agent = build_agent(
            "test",
            manager,
            planner=planner,
            planning_mode="manual",
            capabilities=[Planning()],
        )
        prompt = _resolve_system_prompt_text(agent)
        # Both boundary-guidance skills should be reachable: the harness
        # one is static (always present once Planning() is passed); the
        # cross-service one is gated and only shows for complex-looking
        # requests, so we only assert the static one here.
        assert task_planning_skill.content in prompt
