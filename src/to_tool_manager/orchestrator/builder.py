from typing import Any, Sequence

from pydantic_ai import models
from pydantic_ai.agent.abstract import AgentMetadata, AgentModelSettings, AgentRetries
from pydantic_ai._instructions import AgentInstructions
from pydantic_ai._agent_graph import EndStrategy
from pydantic_ai.concurrency import AnyConcurrencyLimit
from pydantic_ai.template import TemplateStr

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
            .system_prompt("You are a helpful assistant.")
            .build()
        )
        await orchestrator.init_app("openai:gpt-4o")
    """

    def __init__(self) -> None:
        self._agents: list[AgentInterface] = []
        self._model: models.Model | models.KnownModelName | str | None = None
        self._middlewares: list[Middleware] = []
        self._config: dict[str, Any] = {}
        self._init_kwargs: dict[str, Any] = {}

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

    def output_type(self, output_type: Any) -> "OrchestratorBuilder":
        """Sets the structured output type."""
        self._init_kwargs["output_type"] = output_type
        return self

    def instructions(self, instructions: AgentInstructions) -> "OrchestratorBuilder":
        """Sets dynamic instructions."""
        self._init_kwargs["instructions"] = instructions
        return self

    def system_prompt(self, system_prompt: str | Sequence[str]) -> "OrchestratorBuilder":
        """Sets static system prompt(s)."""
        self._init_kwargs["system_prompt"] = system_prompt
        return self

    def name(self, name: str) -> "OrchestratorBuilder":
        """Sets the agent name."""
        self._init_kwargs["name"] = name
        return self

    def description(self, description: TemplateStr | str) -> "OrchestratorBuilder":
        """Sets the agent description."""
        self._init_kwargs["description"] = description
        return self

    def model_settings(self, model_settings: AgentModelSettings) -> "OrchestratorBuilder":
        """Sets model settings (temperature, max_tokens, etc.)."""
        self._init_kwargs["model_settings"] = model_settings
        return self

    def retries(self, retries: int | AgentRetries) -> "OrchestratorBuilder":
        """Sets per-category retry budget."""
        self._init_kwargs["retries"] = retries
        return self

    def end_strategy(self, end_strategy: EndStrategy) -> "OrchestratorBuilder":
        """Sets how to handle tool calls alongside final result."""
        self._init_kwargs["end_strategy"] = end_strategy
        return self

    def metadata(self, metadata: AgentMetadata) -> "OrchestratorBuilder":
        """Sets agent metadata."""
        self._init_kwargs["metadata"] = metadata
        return self

    def tool_timeout(self, tool_timeout: float) -> "OrchestratorBuilder":
        """Sets default timeout in seconds for tool execution."""
        self._init_kwargs["tool_timeout"] = tool_timeout
        return self

    def max_concurrency(self, max_concurrency: AnyConcurrencyLimit) -> "OrchestratorBuilder":
        """Sets limit on concurrent agent runs."""
        self._init_kwargs["max_concurrency"] = max_concurrency
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
        orchestrator.init_app(self._model, **self._init_kwargs)
        return orchestrator