from typing import Any, List, Sequence

from pydantic_ai import Agent, models

from to_tool_manager import Middleware, Service, ServiceDependencyGraph, Step, build_agent
from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.module import Module


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
        """
        self.__model: models.Model | models.KnownModelName | str = model
        self.__middleware: Sequence[Middleware] | None = middleware
        self.__capabilities: List[Any] = list(capabilities or [])
        self.__name: str | None = name

        self.__manager: ToToolManager | None = None
        self.__agent: Agent | None = None
        self.__services: List[Service] = []
        self.__modules: List[Module] = []

    @property
    def _manager(self) -> ToToolManager:
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

    def add_capability(self, capability: Any) -> "AgentSupport":
        """Adds an agent capability (e.g. `Planning()`), fluent-style.

        Same pattern as `add_service`/`add_module`: purely additive,
        forwarded verbatim to `build_agent()`'s `capabilities` list. Must be
        called before `build_agent()`.

        Args:
            capability: A pydantic-ai agent capability instance.

        Returns:
            self, to allow chaining (`support.add_capability(a).add_capability(b)`).
        """
        self.__capabilities.append(capability)
        return self

    def add_service(self, name: str, service: type) -> None:
        """Adds a service to the agent.

        Args:
            name: Unique name for the service.
            service: Service class to register.
        """
        self.__services.append(Service(
            name=name, 
            service=service
        ))

    def add_module(self, name: str, services: List[Service]) -> None:
        """Adds a module to the agent.

        Args:
            name: Unique name for the module.
            services: List of services composing the module.
        """
        self.__modules.append(Module(
            name=name,
            services=services
        ))

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
        planner = self._manager.with_planner(dependency_graph)
        plan = await planner.create_plan(steps)
        return plan        

    def build_agent(self) -> None:
        """Builds the agent with the configured manager and model.

        This method must be called after adding all services
        and modules, and before using the `agent` property.
        """
        self.__build_ttm(self.__middleware)
        self.__agent = build_agent(
            self.__model, 
            self.__manager,
            capabilities=self.__capabilities or None,
            name=self.__name,
        )

    def __build_ttm(self, middleware: Sequence[Middleware] | None) -> None:
        """Builds the ToToolManager with the registered services and modules."""
        services = self.__services + self.__modules
        self.__manager = ToToolManager(
            services,
            middlewares=middleware
        )