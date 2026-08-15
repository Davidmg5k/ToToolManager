import pytest
from to_tool_manager.orchestrator.agent_orchestrator import AgentOrchestrator
from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface
from to_tool_manager.orchestrator.events import (
    OrchestratorEvent,
    OrchestratorEventHandler,
    OrchestratorEventType,
)


class DummyAgent(AgentInterface):
    def __init__(self, name: str = "dummy"):
        super().__init__(model="openai:gpt-4o")
        self._name = name

    @property
    def name(self):
        return self._name

    def _create_services(self):
        pass

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass


class EventCollector:
    def __init__(self):
        self.events = []

    async def on_event(self, event: OrchestratorEvent) -> None:
        self.events.append(event)


class SubAgentForTests(AgentInterface):
    """Like DummyAgent, but lets model/name be injected (e.g. TestModel).
    Not named `Test*` so pytest doesn't try to collect it as a test class."""

    def __init__(self, model, name: str = "sub_agent"):
        super().__init__(model=model, name=name)

    def _create_services(self):
        pass

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass


class TestAgentOrchestratorInitApp:
    """init_app() end-to-end against pydantic-ai's TestModel -- no mocks,
    no real provider/API key needed. Regression guard for two things:
    1. the `model` type hint, which used to be narrowed to `KnownModelName`
       (str) only, even though the underlying `Agent(model=...)` already
       accepted a real `models.Model` instance;
    2. `AgentSupport`/`AgentInterface` never forwarding `name` to
       `build_agent()`, which meant `init_app()` always raised
       ("Sub-agent has no name") for any agent built the standard way --
       this test would have caught it."""

    def test_init_app_accepts_test_model_instance(self):
        from pydantic_ai.models.test import TestModel

        orchestrator = AgentOrchestrator([SubAgentForTests(model=TestModel(call_tools=[]))])
        orchestrator.init_app(model=TestModel(call_tools=[]))
        assert orchestrator.agent is not None

    def test_init_app_with_test_model_runs_end_to_end(self):
        import asyncio
        from pydantic_ai.models.test import TestModel

        orchestrator = AgentOrchestrator([SubAgentForTests(model=TestModel(call_tools=[]), name="sub1")])
        orchestrator.init_app(model=TestModel(call_tools=[]))

        result = asyncio.run(orchestrator.agent.run("hello"))
        assert result.output is not None


class TestAgentOrchestratorInit:
    def test_init_empty(self):
        orchestrator = AgentOrchestrator()
        assert orchestrator.agents == []

    def test_init_with_agents(self):
        agent1 = DummyAgent("agent1")
        agent2 = DummyAgent("agent2")
        orchestrator = AgentOrchestrator([agent1, agent2])
        assert len(orchestrator.agents) == 2

    def test_agent_property_not_initialized(self):
        orchestrator = AgentOrchestrator()
        with pytest.raises(RuntimeError, match="Orchestrator not initialized"):
            _ = orchestrator.agent

    def test_agents_property_returns_copy(self):
        agent = DummyAgent()
        orchestrator = AgentOrchestrator([agent])
        agents = orchestrator.agents
        agents.clear()
        assert len(orchestrator.agents) == 1

    def test_event_handlers_property(self):
        orchestrator = AgentOrchestrator()
        assert orchestrator.event_handlers == []


class TestAgentOrchestratorAgentManagement:
    def test_add_agent(self):
        orchestrator = AgentOrchestrator()
        agent = DummyAgent()
        orchestrator.add_agent(agent)
        assert len(orchestrator.agents) == 1

    def test_add_agent_duplicate(self):
        orchestrator = AgentOrchestrator()
        agent = DummyAgent()
        orchestrator.add_agent(agent)
        with pytest.raises(ValueError, match="Agent already registered"):
            orchestrator.add_agent(agent)

    def test_add_agents(self):
        orchestrator = AgentOrchestrator()
        agent1 = DummyAgent("agent1")
        agent2 = DummyAgent("agent2")
        orchestrator.add_agents([agent1, agent2])
        assert len(orchestrator.agents) == 2

    def test_has_agent(self):
        orchestrator = AgentOrchestrator()
        agent = DummyAgent("test-agent")
        orchestrator.add_agent(agent)
        assert orchestrator.has_agent("test-agent") is True
        assert orchestrator.has_agent("nonexistent") is False

    def test_get_agent(self):
        orchestrator = AgentOrchestrator()
        agent = DummyAgent("test-agent")
        orchestrator.add_agent(agent)
        assert orchestrator.get_agent("test-agent") is agent
        assert orchestrator.get_agent("nonexistent") is None

    def test_remove_agent(self):
        orchestrator = AgentOrchestrator()
        agent = DummyAgent()
        orchestrator.add_agent(agent)
        orchestrator.remove_agent(agent)
        assert len(orchestrator.agents) == 0

    def test_remove_agent_not_found(self):
        orchestrator = AgentOrchestrator()
        agent = DummyAgent()
        with pytest.raises(ValueError, match="Agent not found"):
            orchestrator.remove_agent(agent)

    def test_clear_agents(self):
        orchestrator = AgentOrchestrator()
        orchestrator.add_agent(DummyAgent("agent1"))
        orchestrator.add_agent(DummyAgent("agent2"))
        orchestrator.clear_agents()
        assert len(orchestrator.agents) == 0


class TestAgentOrchestratorEvents:
    def test_add_event_handler(self):
        orchestrator = AgentOrchestrator()
        handler = EventCollector()
        orchestrator.add_event_handler(handler)
        assert handler in orchestrator.event_handlers

    def test_remove_event_handler(self):
        orchestrator = AgentOrchestrator()
        handler = EventCollector()
        orchestrator.add_event_handler(handler)
        orchestrator.remove_event_handler(handler)
        assert handler not in orchestrator.event_handlers

    def test_remove_event_handler_not_registered(self):
        orchestrator = AgentOrchestrator()
        handler = EventCollector()
        with pytest.raises(ValueError, match="Handler not registered"):
            orchestrator.remove_event_handler(handler)

    @pytest.mark.anyio
    async def test_startup_emits_event(self):
        orchestrator = AgentOrchestrator()
        handler = EventCollector()
        orchestrator.add_event_handler(handler)

        await orchestrator.startup()

        assert len(handler.events) == 1
        assert handler.events[0].type == OrchestratorEventType.ORCHESTRATOR_STARTED

    @pytest.mark.anyio
    async def test_shutdown_emits_event(self):
        orchestrator = AgentOrchestrator()
        handler = EventCollector()
        orchestrator.add_event_handler(handler)

        await orchestrator.shutdown()

        assert len(handler.events) == 1
        assert handler.events[0].type == OrchestratorEventType.ORCHESTRATOR_STOPPED

    @pytest.mark.anyio
    async def test_multiple_handlers_receive_events(self):
        orchestrator = AgentOrchestrator()
        handler1 = EventCollector()
        handler2 = EventCollector()
        orchestrator.add_event_handler(handler1)
        orchestrator.add_event_handler(handler2)

        await orchestrator.startup()

        assert len(handler1.events) == 1
        assert len(handler2.events) == 1