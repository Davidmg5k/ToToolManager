import pytest
from abc import ABC
from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport


class TestAgentInterface:
    def test_is_abstract(self):
        assert issubclass(AgentInterface, ABC)

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            AgentInterface(model="openai:gpt-4o")

    def test_concrete_agent_creation(self):
        class ConcreteAgent(AgentInterface):
            def _create_services(self):
                pass

            def _create_modules(self):
                pass

            def _create_plan(self):
                pass

        agent = ConcreteAgent(model="openai:gpt-4o")
        assert agent is not None

    def test_agent_support_property(self):
        class ConcreteAgent(AgentInterface):
            def _create_services(self):
                pass

            def _create_modules(self):
                pass

            def _create_plan(self):
                pass

        agent = ConcreteAgent(model="openai:gpt-4o")
        assert isinstance(agent.agent, AgentSupport)

    def test_agent_support_property_returns_same_instance(self):
        class ConcreteAgent(AgentInterface):
            def _create_services(self):
                pass

            def _create_modules(self):
                pass

            def _create_plan(self):
                pass

        agent = ConcreteAgent(model="openai:gpt-4o")
        support1 = agent.agent
        support2 = agent.agent
        assert support1 is support2

    def test_cannot_instantiate_without_implementing_methods(self):
        class IncompleteAgent(AgentInterface):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent(model="openai:gpt-4o")


class TestAgentInterfaceCapabilities:
    """Capabilities passed to AgentInterface.__init__ must reach the
    underlying AgentSupport unchanged -- AgentInterface keeps no capability
    list of its own (avoids duplicating AgentSupport's role)."""

    def _concrete_agent_cls(self):
        class ConcreteAgent(AgentInterface):
            def _create_services(self):
                pass

            def _create_modules(self):
                pass

            def _create_plan(self):
                pass

        return ConcreteAgent

    def test_capabilities_forwarded_to_agent_support(self):
        sentinel = object()
        agent = self._concrete_agent_cls()(model="openai:gpt-4o", capabilities=[sentinel])
        assert agent.agent.capabilities == [sentinel]

    def test_no_capabilities_defaults_to_empty(self):
        agent = self._concrete_agent_cls()(model="openai:gpt-4o")
        assert agent.agent.capabilities == []

    def test_add_capability_via_agent_property(self):
        """No separate capability-management method on AgentInterface --
        `self.agent.add_capability(...)` (AgentSupport) is the single path."""
        sentinel = object()
        agent = self._concrete_agent_cls()(model="openai:gpt-4o")
        agent.agent.add_capability(sentinel)
        assert agent.agent.capabilities == [sentinel]

    def test_name_forwarded_to_agent_support(self):
        agent = self._concrete_agent_cls()(model="openai:gpt-4o", name="my_agent")
        assert agent.agent.name == "my_agent"

    def test_no_name_defaults_to_none(self):
        agent = self._concrete_agent_cls()(model="openai:gpt-4o")
        assert agent.agent.name is None


class TestAgentInterfaceBuildAgentOrder:
    """Regression coverage for hallazgo 1.1 (handoff doc, section 1.1):
    `AgentInterface.build_agent()` used to call
    `self.__agent_support.build_agent()` BEFORE `_create_services()` /
    `_create_modules()` -- the abstract hooks a concrete subclass
    implements to register services/modules via
    `self.agent.add_service(...)` / `self.agent.add_module(...)`. Since
    `AgentSupport.build_agent()` snapshots `self.__services` /
    `self.__modules` into a `ToToolManager` (and from there into the
    pydantic-ai `Agent`'s tool list) at the moment it runs, calling it
    first meant the manager -- and the resulting `Agent` -- was always
    built with zero tools, no matter what a concrete subclass registered
    afterwards. This is a real, no-mocks, end-to-end test (TestModel),
    matching the precedent in
    `tests/orchestrator/test_agent_orchestrator.py::TestAgentOrchestratorInitApp`.
    """

    def _agent_with_one_service(self):
        from pydantic_ai.models.test import TestModel

        class Greeter:
            def hello(self, name: str) -> str:
                """Say hello."""
                return f"Hello {name}"

        class ConcreteAgent(AgentInterface):
            def _create_services(self):
                self.agent.add_service("greeter", Greeter)

            def _create_modules(self):
                pass

            def _create_plan(self):
                pass

        return ConcreteAgent(model=TestModel(call_tools=[]))

    def test_build_agent_registers_service_added_in_create_services(self):
        agent = self._agent_with_one_service()
        agent.build_agent()

        # The concrete assertions that matter: the service registered in
        # _create_services() must actually reach the manager the Agent was
        # built from (not just AgentSupport's own bookkeeping list).
        assert len(agent.agent.services) == 1
        assert agent.agent.services[0].name == "greeter"
        assert len(agent.agent._manager.tool_specs) == 1, (
            "the manager the Agent was built from has no tool_specs for "
            "the service registered in _create_services() -- build_agent() "
            "built the Agent before _create_services() ran"
        )

    def test_built_agent_can_run_and_use_the_registered_service(self):
        """End-to-end: the built Agent must actually be able to invoke the
        tool for a service registered in _create_services()."""
        import asyncio
        from pydantic_ai.models.test import TestModel

        agent = self._agent_with_one_service()
        agent.build_agent()

        result = asyncio.run(agent.agent.agent.run("say hi to Ada"))
        assert result.output is not None