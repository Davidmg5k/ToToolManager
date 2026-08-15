from typing import Any, Sequence

from pydantic_ai import models

from to_tool_manager.orchestrator.agent_orchestrator import AgentOrchestrator
from to_tool_manager.security.middleware import Middleware
from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface


class OrchestratorBuilder:
    """Builder pattern for configuring the orchestrator in a complex way.

    Allows building an AgentOrchestrator fluently and readably,
    configuring agents, model, middlewares, and advanced options.

    Example::

        orchestrator = (
            OrchestratorBuilder()
            .model("openai:gpt-4o")
            .agent(my_agent)
            .agent(other_agent)
            .middleware(auth_middleware)
            .config(enable_logging=True)
            .build()
        )
        await orchestrator.init_app("openai:gpt-4o")
    """

    def __init__(self) -> None:
        self._agents: list[AgentInterface] = []
        self._model: models.Model | models.KnownModelName | str | None = None
        self._middlewares: list[Middleware] = []
        self._config: dict[str, Any] = {}

    def model(self, model: models.Model | models.KnownModelName | str) -> "OrchestratorBuilder":
        """Sets the model to use for the orchestrator."""
        self._model = model
        return self

    def agent(self, agent: AgentInterface) -> "OrchestratorBuilder":
        """Adds an agent to the orchestrator."""
        self._agents.append(agent)
        return self

    def agents(self, agents: Sequence[AgentInterface]) -> "OrchestratorBuilder":
        """Adds multiple agents to the orchestrator."""
        self._agents.extend(agents)
        return self

    def middleware(self, middleware: Middleware) -> "OrchestratorBuilder":
        """Adds a middleware to the orchestrator."""
        self._middlewares.append(middleware)
        return self

    def middlewares(self, middlewares: Sequence[Middleware]) -> "OrchestratorBuilder":
        """Adds multiple middlewares to the orchestrator."""
        self._middlewares.extend(middlewares)
        return self

    def config(self, **kwargs: Any) -> "OrchestratorBuilder":
        """Adds additional configuration (key=value)."""
        self._config.update(kwargs)
        return self

    def build(self) -> "AgentOrchestrator":
        """Builds and returns the configured AgentOrchestrator.

        Note:
            After calling build(), you must call init_app(model)
            to initialize the orchestrator with the model.
        """
        from to_tool_manager.orchestrator.agent_orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(self._agents)
        return orchestrator

    def build_and_init(self) -> "AgentOrchestrator":
        """Builds and initializes the orchestrator in a single step.

        Raises:
            ValueError: If no model has been configured with .model().
        """
        if self._model is None:
            raise ValueError(
                "You must configure a model with .model() before using build_and_init()."
            )
        orchestrator = self.build()
        orchestrator.init_app(self._model)
        return orchestrator