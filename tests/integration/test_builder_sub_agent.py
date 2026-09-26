"""Delegation end-to-end tests for TTMBuilder.add_sub_agent (REQ-009).

These drive a real agent run with `FunctionModel`, so they exercise the
delegation path itself rather than just registration. No network, no API key.
"""

from typing import ClassVar

from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from to_tool_manager.core.builder.manager import Manager
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.exception import DependencyNotSetError


class UserService:
    """Records the calls it receives, so a delegation can be observed.

    A `Service` is instantiated by the framework from `args`/`kwargs`
    (util.py service_to_dependency), so the recorder is class-level.
    """

    calls: ClassVar[list[str]] = []

    def create(self, name: str) -> str:
        UserService.calls.append(name)
        return f"Created {name}"


def _delegating_model(service_name: str) -> FunctionModel:
    """A model that delegates once, then lets the delegate load, call and finish.

    A `Service` capability is deferred, so the delegate's first turn only offers
    `load_capability`; the real tool shows up on the turn after.
    """
    state = {"delegated": False, "created": False, "loaded": False}

    def respond(messages, info: AgentInfo) -> ModelResponse:
        names = [tool.name for tool in info.function_tools]

        if "delegate_task" in names:
            if state["delegated"]:
                return ModelResponse(parts=[TextPart("parent finished")])
            state["delegated"] = True
            return ModelResponse(parts=[ToolCallPart(
                "delegate_task",
                {"agent_name": "Commerce", "task": "create Alice"},
            )])

        if "create" in names and not state["created"]:
            state["created"] = True
            return ModelResponse(parts=[ToolCallPart("create", {"name": "Alice"})])

        if "load_capability" in names and not state["loaded"]:
            state["loaded"] = True
            return ModelResponse(parts=[ToolCallPart(
                "load_capability", {"id": service_name},
            )])

        return ModelResponse(parts=[TextPart("delegate finished")])

    return FunctionModel(respond)


class TestSubAgentDelegation:
    """REQ-009: a sub-agent's services are reachable through the delegate run."""

    async def test_delegate_runs_its_service_tool(self):
        """A module's agent invokes the real service method on delegation."""
        UserService.calls = []
        builder = TTMBuilder(name="Root")
        builder.add_module(
            name="Commerce",
            description="Commerce delegate",
            services=[Service(
                name="User",
                service=UserService,
                instructions="User management",
            )],
        )
        builder.build(_delegating_model("User"))

        await builder.agent.run("go", deps=builder.dependency)

        assert UserService.calls == ["Alice"]

    async def test_sub_agent_without_services_answers(self):
        """A sub-agent needs nothing but its own parameters to be delegable."""
        def respond(messages, info: AgentInfo) -> ModelResponse:
            names = [tool.name for tool in info.function_tools]
            if "delegate_task" in names and not any(
                type(p).__name__ == "ToolReturnPart" for m in messages for p in m.parts
            ):
                return ModelResponse(parts=[ToolCallPart(
                    "delegate_task",
                    {"agent_name": "Reasoner", "task": "think"},
                )])
            return ModelResponse(parts=[TextPart("answered")])

        builder = TTMBuilder(name="Root")
        builder.add_sub_agent(
            name="Reasoner",
            description="Reasons without tools",
            instructions="Answer from the task alone",
        )
        builder.build(FunctionModel(respond))

        result = await builder.agent.run("go", deps=builder.dependency)

        assert result.output is not None

    async def test_delegate_tool_needs_the_services_on_the_parent_dependency(self):
        """Guards the invariant `add_module` upholds.

        `SubAgents` forwards the parent's deps, and a service tool resolves its
        instance from `ctx.deps` (tool_factory.py). Registering the module
        straight on the Manager -- skipping the builder's parent-dependency step
        -- is what makes delegation fail, so this pins why that step exists.
        """
        manager = Manager()
        manager.add_module(Module(
            name="Commerce",
            description="Commerce delegate",
            services=[Service(
                name="User",
                service=UserService,
                instructions="User management",
            )],
        ))
        agent = Agent(
            _delegating_model("User"),
            name="Root",
            deps_type=DinamicDepend,
            capabilities=manager.capabilities(None),
        )

        UserService.calls = []
        try:
            await agent.run("go", deps=DinamicDepend())
        except DependencyNotSetError as exc:
            assert "User" in str(exc)
        else:
            raise AssertionError(
                "expected the delegate to fail without the parent's dependency"
            )
        assert UserService.calls == []
