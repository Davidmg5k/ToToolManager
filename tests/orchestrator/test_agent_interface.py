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