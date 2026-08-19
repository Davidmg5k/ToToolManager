import pytest
from to_tool_manager.orchestrator.builder import OrchestratorBuilder
from to_tool_manager.orchestrator.agent_orchestrator import AgentOrchestrator
from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface


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


class TestOrchestratorBuilder:
    def test_empty_builder(self):
        builder = OrchestratorBuilder()
        orchestrator = builder.build()
        assert isinstance(orchestrator, AgentOrchestrator)
        assert orchestrator.agents == []

    def test_builder_model(self):
        builder = OrchestratorBuilder().model("openai:gpt-4o")
        assert builder._model == "openai:gpt-4o"

    def test_builder_agent(self):
        agent = DummyAgent()
        builder = OrchestratorBuilder().agent(agent)
        assert len(builder._agents) == 1
        assert builder._agents[0] is agent

    def test_builder_agents(self):
        agent1 = DummyAgent("agent1")
        agent2 = DummyAgent("agent2")
        builder = OrchestratorBuilder().agents([agent1, agent2])
        assert len(builder._agents) == 2

    def test_builder_middleware(self):
        from to_tool_manager.security.middleware import Middleware

        class TestMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        mw = TestMiddleware()
        builder = OrchestratorBuilder().middleware(mw)
        assert len(builder._middlewares) == 1
        assert builder._middlewares[0] is mw

    def test_builder_middlewares(self):
        from to_tool_manager.security.middleware import Middleware

        class MW1(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        class MW2(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        builder = OrchestratorBuilder().middlewares([MW1(), MW2()])
        assert len(builder._middlewares) == 2

    def test_builder_config(self):
        builder = OrchestratorBuilder().config(key1="value1", key2=42)
        assert builder._config == {"key1": "value1", "key2": 42}

    def test_builder_build(self):
        agent = DummyAgent()
        orchestrator = OrchestratorBuilder().agent(agent).build()
        assert isinstance(orchestrator, AgentOrchestrator)
        assert len(orchestrator.agents) == 1

    def test_builder_build_and_init_no_model(self):
        agent = DummyAgent()
        builder = OrchestratorBuilder().agent(agent)
        with pytest.raises(ValueError, match="You must configure a model"):
            builder.build_and_init()

    def test_builder_fluent_interface(self):
        from to_tool_manager.security.middleware import Middleware

        class TestMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        agent1 = DummyAgent("agent1")
        agent2 = DummyAgent("agent2")

        orchestrator = (
            OrchestratorBuilder()
            .model("openai:gpt-4o")
            .agent(agent1)
            .agent(agent2)
            .middleware(TestMiddleware())
            .config(key="value")
            .build()
        )
        assert len(orchestrator.agents) == 2


class TestOrchestratorBuilderAdvancedInitKwargs:
    """Coverage for the fluent setters added alongside hallazgo 1.1's
    build_agent() reorder fix -- each just stashes a value into
    `_init_kwargs` for `build_and_init()` to forward to
    `AgentOrchestrator.init_app()`. Table-driven since every setter
    follows the exact same one-line pattern."""

    @pytest.mark.parametrize(
        "method_name, value",
        [
            ("output_type", str),
            ("instructions", "be helpful"),
            ("system_prompt", "You are a helpful assistant."),
            ("name", "my_agent"),
            ("description", "A test agent"),
            ("model_settings", {"temperature": 0.2}),
            ("retries", 3),
            ("end_strategy", "early"),
            ("metadata", {"team": "test"}),
            ("tool_timeout", 30.0),
            ("max_concurrency", 5),
        ],
    )
    def test_setter_stores_value_in_init_kwargs(self, method_name, value):
        builder = OrchestratorBuilder()
        result = getattr(builder, method_name)(value)

        assert result is builder, f"{method_name}() must return self for chaining"
        assert builder._init_kwargs[method_name] == value

    def test_multiple_setters_accumulate_in_init_kwargs(self):
        builder = (
            OrchestratorBuilder()
            .output_type(str)
            .name("my_agent")
            .retries(2)
            .tool_timeout(10.0)
        )
        assert builder._init_kwargs == {
            "output_type": str,
            "name": "my_agent",
            "retries": 2,
            "tool_timeout": 10.0,
        }

    def test_build_and_init_forwards_init_kwargs_to_orchestrator(self, monkeypatch):
        """build_and_init() must actually pass what the fluent setters
        accumulated through to AgentOrchestrator.init_app() -- not just
        store them."""
        agent = DummyAgent()
        captured: dict = {}

        def fake_init_app(self_, model, **kwargs):
            captured["model"] = model
            captured.update(kwargs)

        monkeypatch.setattr(AgentOrchestrator, "init_app", fake_init_app)

        (
            OrchestratorBuilder()
            .model("openai:gpt-4o")
            .agent(agent)
            .name("my_agent")
            .retries(3)
            .build_and_init()
        )

        assert captured["model"] == "openai:gpt-4o"
        assert captured["name"] == "my_agent"
        assert captured["retries"] == 3