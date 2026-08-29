from typing import Any, List, Literal, Sequence

from pydantic_ai import Agent, models

from to_tool_manager import Middleware, Planner, Service, ServiceDependencyGraph, Step, build_agent
from to_tool_manager.core.discovery import Visibility
from to_tool_manager.core.service import ErrorRule
from to_tool_manager.core.types import ErrorMap
from to_tool_manager.adapters.pydantic_ai import (
    AgentInstructions,
    AgentMetadata,
    AgentModelSettings,
    AgentRetries,
    AnyConcurrencyLimit,
    EndStrategy,
    TemplateStr,
)
from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.module import Module
from to_tool_manager.skills import build_skills_toolset
from pydantic_ai_skills import Skill

_UNSET: Any = object()


class AgentSupport:
    """Support for building and configuring agents.

    Provides methods to add services, modules, and build
    the agent with the configured model and middlewares.
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
        skills: list[Skill] | None = None,
        tools: list[Any] | None = None,
        toolsets: list[Any] | None = None,
    ) -> None:
        """Initializes the agent support.

        Args:
            model: Model to use. Either a model name (e.g. 'openai:gpt-4o')
                or a `pydantic_ai.models.Model` instance -- including
                `pydantic_ai.models.test.TestModel`, so this can be built
                and run without a real provider/API key. Forwarded as-is to
                `build_agent()`, whose own `model` parameter already accepts
                both.
            middleware: Optional sequence of middlewares.
            capabilities: Optional sequence of pydantic-ai agent capabilities
                (e.g. ``Planning()`` from ``pydantic_ai_harness.planning``).
                Forwarded as-is to ``build_agent()``'s own ``capabilities``
                parameter -- this is only a thin passthrough, no new
                capability-wiring mechanism is introduced here. Additional
                capabilities can be appended later via `add_capability()`.
            name: Optional name for the underlying `Agent`. Forwarded as-is
                to `build_agent()`'s own `name` parameter, which already
                existed but was never reachable from this class. Required
                if this agent will be registered with `AgentOrchestrator`
                (`SubAgents` needs each sub-agent's `Agent` to have a name).
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
                delegated Module run. ``_UNSET`` uses framework default.
            skills: Additional pydantic-ai Skills to include. These are
                built into a separate ``SkillsToolset`` and merged with the
                built-in skills.
            tools: Additional tools to include beyond the auto-registered services.
                Forwarded to ``build_agent()``.
            toolsets: Additional toolsets to merge with the built-in skills toolset.
                Forwarded to ``build_agent()``.
        """
        self.__model: models.Model | models.KnownModelName | str = model
        self.__middleware: Sequence[Middleware] | None = middleware
        self.__capabilities: List[Any] = list(capabilities or [])
        self.__name: str | None = name
        self.__output_type: Any = output_type
        self.__system_prompt: str | Sequence[str] | None = system_prompt
        self.__instructions: AgentInstructions = instructions
        self.__description: TemplateStr | str | None = description
        self.__model_settings: AgentModelSettings | None = model_settings
        self.__retries: int | AgentRetries | None = retries
        self.__deps_type: type | None = deps_type
        self.__validation_context: Any | None = validation_context
        self.__tool_timeout: float | None = tool_timeout
        self.__max_concurrency: AnyConcurrencyLimit = max_concurrency
        self.__end_strategy: EndStrategy = end_strategy
        self.__defer_model_check: bool = defer_model_check
        self.__metadata: AgentMetadata | None = metadata
        self.__planner: Planner | None = planner
        self.__planning_mode: str = planning_mode
        self.__include_general_purpose_subagent: bool = include_general_purpose_subagent
        self.__subagent_usage_limits: Any = subagent_usage_limits
        self.__skills: List[Skill] = list(skills or [])
        self.__tools: list[Any] | None = tools
        self.__toolsets: list[Any] | None = toolsets

        self.__manager: ToToolManager | None = None
        self.__agent: Agent | None = None
        self.__services: List[Service] = []
        self.__modules: List[Module] = []

    @property
    def manager(self) -> ToToolManager:
        """The underlying manager. Raises RuntimeError if build_agent() has not been called."""
        if self.__manager is None:
            raise RuntimeError(
                "Manager not initialized. Call build_agent() first."
            )
        return self.__manager

    @property
    def agent(self) -> Agent:
        """The built agent. Raises RuntimeError if build_agent() has not been called."""
        if self.__agent is None:
            raise RuntimeError(
                "Agent not initialized. Call build_agent() first."
            )
        return self.__agent

    @property
    def services(self) -> List[Service]:
        """List of registered services."""
        return list(self.__services)

    @property
    def modules(self) -> List[Module]:
        """List of registered modules."""
        return list(self.__modules)

    @property
    def capabilities(self) -> List[Any]:
        """List of registered agent capabilities."""
        return list(self.__capabilities)

    @property
    def name(self) -> str | None:
        """Name configured for the underlying `Agent`, if any."""
        return self.__name

    def add_capability(self, capability: Any):
        """Adds an agent capability (e.g. `Planning()`), fluent-style.

        Same pattern as `add_service`/`add_module`: purely additive,
        forwarded verbatim to `build_agent()`'s `capabilities` list. Must be
        called before `build_agent()`.

        Args:
            capability: A pydantic-ai agent capability instance.
        """
        self.__capabilities.append(capability)

    @property
    def skills(self) -> List[Skill]:
        """List of registered skills."""
        return list(self.__skills)

    def add_skill(self, skill: Skill) -> None:
        """Adds a pydantic-ai Skill instance.

        Must be called before ``build_agent()``. The skill will be built
        into a ``SkillsToolset`` and merged with the built-in skills.

        Args:
            skill: A ``pydantic_ai_skills.Skill`` instance.
        """
        self.__skills.append(skill)

    def add_skills(self, skills: Sequence[Skill]) -> None:
        """Adds multiple Skills at once.

        Must be called before ``build_agent()``.

        Args:
            skills: Sequence of ``pydantic_ai_skills.Skill`` instances.
        """
        self.__skills.extend(skills)

    def add_service(self,
        name: str,
        service: type,
        *,
        description: str = "",
        visibility: frozenset[Visibility] | None = None,
        include: frozenset[str] | None = None,
        exclude: frozenset[str] | None = None,
        expose_properties: bool = False,
        error_map: ErrorMap | dict[type[BaseException], Any] | None = None,
        error_rules: Sequence[ErrorRule] | None = None,
        sanitize_system_errors: bool = True,
        singleton: bool = True,
        middlewares: Sequence[Middleware] | None = None,
        disable_middlewares: Sequence[str] | None = None,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> None:
        """Adds a service to the agent.

        All keyword arguments beyond ``name`` and ``service`` are forwarded
        to the ``Service`` dataclass.  Omitted ``None``-defaulted params
        use the ``Service`` dataclass defaults.

        Args:
            name: Unique name for the service.
            service: Service class to register.
            description: Group-level description for this service.
            visibility: Which method-visibility buckets to expose.
            include: If set, ONLY these method names are exposed.
            exclude: Method names to exclude even if otherwise eligible.
            expose_properties: Expose read-only @property members.
            error_map: Exception classification rules.
            error_rules: Ordered list of exception classifiers.
            sanitize_system_errors: Hide raw exception text from callers.
            singleton: Share one instance across all tool calls.
            middlewares: Middlewares applied at the method level.
            disable_middlewares: Names of global middlewares to disable.
            args: Positional args passed to the service constructor.
            kwargs: Keyword args passed to the service constructor.
        """
        svc_kwargs: dict[str, Any] = {
            "name": name, "service": service,
            "description": description,
            "expose_properties": expose_properties,
            "sanitize_system_errors": sanitize_system_errors,
            "singleton": singleton,
            "args": args, "kwargs": kwargs or {},
        }
        if visibility is not None:
            svc_kwargs["visibility"] = visibility
        if include is not None:
            svc_kwargs["include"] = include
        if exclude is not None:
            svc_kwargs["exclude"] = exclude
        if error_map is not None:
            svc_kwargs["error_map"] = error_map
        if error_rules is not None:
            svc_kwargs["error_rules"] = error_rules
        if middlewares is not None:
            svc_kwargs["middlewares"] = middlewares
        if disable_middlewares is not None:
            svc_kwargs["disable_middlewares"] = disable_middlewares
        self.__services.append(Service(**svc_kwargs))

    def add_module(self,
        name: str,
        services: List[Service],
        *,
        description: str = "",
        system_prompt: str | None = None,
        instructions: str | None = None,
        model: str | None = None,
        subagent_mode: Literal["sync", "async", "auto"] = "sync",
        include_efficiency_appendix: bool = True,
        middlewares: Sequence[Middleware] | None = None,
        disable_middlewares: Sequence[str] | None = None,
    ) -> None:
        """Adds a module to the agent.

        All keyword arguments beyond ``name`` and ``services`` are forwarded
        to the ``Module`` dataclass.

        Args:
            name: Unique name for the module.
            services: List of services composing the module.
            description: Group-level description for this module.
            system_prompt: Independent system prompt for this module.
            instructions: Dynamic instructions for this module.
            model: Optional model override for this module's sub-agent.
            subagent_mode: Preferred execution mode (sync/async/auto).
            include_efficiency_appendix: Append batch-efficiency appendix.
            middlewares: Middlewares applied at the tool level.
            disable_middlewares: Names of global middlewares to disable.
        """
        mod_kwargs: dict[str, Any] = {
            "name": name, "services": services,
            "description": description,
            "system_prompt": system_prompt,
            "instructions": instructions,
            "model": model,
            "subagent_mode": subagent_mode,
            "include_efficiency_appendix": include_efficiency_appendix,
        }
        if middlewares is not None:
            mod_kwargs["middlewares"] = middlewares
        if disable_middlewares is not None:
            mod_kwargs["disable_middlewares"] = disable_middlewares
        self.__modules.append(Module(**mod_kwargs))

    def add_services_to_module(self, module_name: str, services: List[Service]) -> None:
        """Adds services to an existing module.

        Args:
            module_name: Name of the target module.
            services: List of services to add.

        Raises:
            ValueError: If the module does not exist or a service with the same name already exists.
        """
        for module in self.__modules:
            if module.name == module_name:
                existing_names = {s.name for s in module.services}
                for svc in services:
                    if svc.name in existing_names:
                        raise ValueError(
                            f"Service '{svc.name}' already exists in module '{module_name}'."
                        )
                module.services = list(module.services) + services
                return
        raise ValueError(f"Module '{module_name}' not found.")

    async def create_plan(self, 
        steps: List[Step],
        dependency_graph: ServiceDependencyGraph | None = None
    ):
        """Creates an execution plan with the given steps.

        Args:
            steps: List of steps to execute.
            dependency_graph: Optional graph of service dependencies.

        Returns:
            Plan created with the configured steps and dependencies.
        """
        planner = self.manager.with_planner(dependency_graph)
        plan = await planner.create_plan(steps)
        return plan        

    def build_agent(self) -> None:
        """Builds the agent with the configured manager and model.

        This method must be called after adding all services
        and modules, and before using the `agent` property.
        """
        self.__build_ttm(self.__middleware)

        kw: dict[str, Any] = {}
        if self.__output_type is not str:
            kw["output_type"] = self.__output_type
        if self.__system_prompt is not None:
            kw["system_prompt"] = self.__system_prompt
        if self.__instructions is not None:
            kw["instructions"] = self.__instructions
        if self.__name is not None:
            kw["name"] = self.__name
        if self.__description is not None:
            kw["description"] = self.__description
        if self.__model_settings is not None:
            kw["model_settings"] = self.__model_settings
        if self.__retries is not None:
            kw["retries"] = self.__retries
        if self.__deps_type is not None:
            kw["deps_type"] = self.__deps_type
        if self.__validation_context is not None:
            kw["validation_context"] = self.__validation_context
        if self.__tool_timeout is not None:
            kw["tool_timeout"] = self.__tool_timeout
        if self.__max_concurrency is not None:
            kw["max_concurrency"] = self.__max_concurrency
        if self.__end_strategy != "graceful":
            kw["end_strategy"] = self.__end_strategy
        if self.__defer_model_check:
            kw["defer_model_check"] = self.__defer_model_check
        if self.__metadata is not None:
            kw["metadata"] = self.__metadata
        if self.__planner is not None:
            kw["planner"] = self.__planner
        if self.__planning_mode != "manual":
            kw["planning_mode"] = self.__planning_mode
        if self.__include_general_purpose_subagent:
            kw["include_general_purpose_subagent"] = self.__include_general_purpose_subagent
        if self.__subagent_usage_limits is not _UNSET:
            kw["subagent_usage_limits"] = self.__subagent_usage_limits
        if self.__skills:
            kw["skills"] = self.__skills
        if self.__tools is not None:
            kw["tools"] = self.__tools
        if self.__toolsets is not None:
            kw["toolsets"] = self.__toolsets

        self.__agent = build_agent(
            self.__model, 
            self.__manager, 
            capabilities=self.__capabilities or None,
            **kw,
        )

    def __build_ttm(self, middleware: Sequence[Middleware] | None) -> None:
        """Builds the ToToolManager with the registered services and modules."""
        services = self.__services + self.__modules
        self.__manager = ToToolManager(
            services,
            middlewares=middleware
        )