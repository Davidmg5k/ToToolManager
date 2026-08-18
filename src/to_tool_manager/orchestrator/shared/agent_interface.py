from abc import ABC, abstractmethod
from typing import Any, Sequence

from pydantic_ai import models

from to_tool_manager import Middleware, Planner
from to_tool_manager.adapters.pydantic_ai import (
    AgentInstructions,
    AgentMetadata,
    AgentModelSettings,
    AgentRetries,
    AnyConcurrencyLimit,
    EndStrategy,
    TemplateStr,
)
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport, _UNSET


class AgentInterface(ABC):
    """Abstract interface for agents that can be orchestrated.

    Concrete agents must implement _create_plan(), _create_services(),
    and _create_modules() to define their services, modules, and planning.
    """

    def __init__(self, 
        model: models.Model | models.KnownModelName | str, 
        middleware: Sequence[Middleware] | None = None,
        capabilities: Sequence[Any] | None = None,
        name: str | None = None,
        *,
        output_type: Any = str,
        system_prompt: str | Sequence[str] | None = None,
        instructions: AgentInstructions = None,
        description: TemplateStr | str | None = None,
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        deps_type: type | None = None,
        validation_context: Any | None = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
        end_strategy: EndStrategy = "graceful",
        defer_model_check: bool = False,
        metadata: AgentMetadata | None = None,
        planner: Planner | None = None,
        planning_mode: str = "manual",
        include_general_purpose_subagent: bool = False,
        subagent_usage_limits: Any = _UNSET,
    ):
        """Initializes the agent with the given model and middlewares.

        Args:
            model: Model to use. Either a model name (e.g. 'openai:gpt-4o')
                or a `pydantic_ai.models.Model` instance -- including
                `pydantic_ai.models.test.TestModel`, so a concrete
                `AgentInterface` can be built and run in tests without a
                real provider/API key.
            middleware: Optional sequence of middlewares to intercept calls.
            capabilities: Optional sequence of pydantic-ai agent capabilities
                (e.g. `Planning()` from `pydantic_ai_harness.planning`),
                forwarded to the underlying `AgentSupport`. To add more after
                construction, use `self.agent.add_capability(...)` -- there
                is deliberately no separate capability list kept here.
            name: Optional name for the underlying `Agent`, forwarded to
                `AgentSupport`. Required if this agent will be registered
                with `AgentOrchestrator` (`SubAgents` needs each sub-agent's
                `Agent` to have a name -- see `AgentOrchestrator.init_app()`).
            output_type: Pydantic BaseModel / dataclass / TypedDict / ``str``
                for structured output.
            system_prompt: Static system prompt(s). If ``None``,
                auto-generated from registered services.
            instructions: Dynamic instructions (str or callable).
            description: Human-readable description attached to OTel spans.
            model_settings: Static model settings (temperature, max_tokens,
                etc.).
            retries: Per-category retry budget. ``None`` uses Agent defaults.
            deps_type: Dependency injection type for static typing.
            validation_context: Validation context.
            tool_timeout: Default timeout in seconds for tool execution.
            max_concurrency: Limit on concurrent agent runs.
            end_strategy: How to handle tool calls alongside final result.
            defer_model_check: Defer model evaluation until first run.
            metadata: Agent metadata.
            planner: Optional ``Planner`` (from
                ``manager.with_planner(...)``).
            planning_mode: ``"off"``, ``"manual"`` (default), or
                ``"gated"``.
            include_general_purpose_subagent: If ``True``, adds a generic
                fallback sub-agent alongside Module-derived ones.
            subagent_usage_limits: ``UsageLimits`` applied to every
                delegated Module run. Uses framework default if not provided.
        """
        self.__agent_support = AgentSupport(
            model, middleware, capabilities, name,
            output_type=output_type,
            system_prompt=system_prompt,
            instructions=instructions,
            description=description,
            model_settings=model_settings,
            retries=retries,
            deps_type=deps_type,
            validation_context=validation_context,
            tool_timeout=tool_timeout,
            max_concurrency=max_concurrency,
            end_strategy=end_strategy,
            defer_model_check=defer_model_check,
            metadata=metadata,
            planner=planner,
            planning_mode=planning_mode,
            include_general_purpose_subagent=include_general_purpose_subagent,
            subagent_usage_limits=subagent_usage_limits,
        )

    @property
    def agent(self) -> AgentSupport:
        """Access the agent support for advanced configuration."""
        return self.__agent_support

    def build_agent(self) -> None:
        """Builds the agent with its services, modules, and planning.

        This method:
        1. Calls _create_plan() to configure planning
        2. Calls _create_services() to register services
        3. Calls _create_modules() to register modules
        4. Builds the underlying Agent from everything registered above

        Note: the underlying `AgentSupport.build_agent()` snapshots the
        registered services/modules into the `ToToolManager` (and from
        there into the pydantic-ai `Agent`'s tool list) at the moment it
        runs -- so it must run LAST, after `_create_services()` /
        `_create_modules()` have populated `self.agent`'s services/modules
        list, or the built `Agent` ends up with no tools regardless of
        what those hooks register (hallazgo 1.1).
        """
        self._create_plan()
        self._create_services()
        self._create_modules()
        self.__agent_support.build_agent()

    @abstractmethod
    def _create_services(self) -> None:
        """Creates and registers the agent's services.

        Implement this method to add services using:
            self.agent.add_service(name, service_class)
        """
        ...

    @abstractmethod
    def _create_modules(self) -> None:
        """Creates and registers the agent's modules.

        Implement this method to add modules using:
            self.agent.add_module(name, services)
        """
        ...

    @abstractmethod
    def _create_plan(self) -> None:
        """Configures the agent's planning.

        Implement this method to configure the execution plan.
        """
        ...