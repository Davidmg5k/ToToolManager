from typing import Any, Dict, List, Sequence

from pydantic_ai import (
    Agent,
    AgentModelSettings,
    AgentRetries,
    AgentToolset,
    AnyConcurrencyLimit,
    EndStrategy,
)
from pydantic_ai.models import Model, KnownModelName
from pydantic_ai_harness.subagents import SubAgents

from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.exception import (
    AgentAlreadyBuiltError,
    AgentNotBuiltError,
    InvalidResourceTypeError,
    MiddlewareNotInitializedError,
    MiddlewareTargetMismatchError,
    ServiceNotFoundError,
)


class ToToolManager:
    """Orchestrator of services and modules.

    Precondition: resources is not empty, middlewares are valid
    Postcondition: services and modules registered, ready to build agents

    Reference: REQ-003, REQ-005, REQ-007
    """

    def __init__(self,
        name: str,
        resources: Sequence[Service | Module],
        middlewares: Sequence[Middleware] | None = None,
        model: Model | KnownModelName | str | None = None,
        instructions: Any = None,
        system_prompt: str | Sequence[str] = (),
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        validation_context: Any = None,
        tools: Sequence[Any] = (),
        toolsets: Sequence[AgentToolset] | None = None,
        defer_model_check: bool = False,
        end_strategy: EndStrategy = 'graceful',
        metadata: Any = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
        output_type: Any = str,
        description: str | None = None,
    ) -> None:
        """
        Precondition: resources is not empty
        Postcondition: __services, __modules and __middlewares initialized
        """
        self.__name = name
        self.__agent: Agent[DinamicDepend] | None = None
        self.__dep = DinamicDepend()

        # Store Agent parameters for build_agent()
        self.__agent_params: Dict[str, Any] = {
            'model': model,
            'instructions': instructions,
            'system_prompt': system_prompt,
            'model_settings': model_settings,
            'retries': retries,
            'validation_context': validation_context,
            'tools': tools,
            'toolsets': toolsets,
            'defer_model_check': defer_model_check,
            'end_strategy': end_strategy,
            'metadata': metadata,
            'tool_timeout': tool_timeout,
            'max_concurrency': max_concurrency,
            'output_type': output_type,
            'description': description,
        }

        # Store services and modules
        self.__services: Dict[str, Service] = {}
        self.__modules: Dict[str, Module] = {}
        self.__middlewares: Sequence[Middleware] | None = middlewares

        # Parse resources
        for item in resources:
            if isinstance(item, Service):
                self.__services[item.name] = item
            elif isinstance(item, Module):
                self.__modules[item.name] = item
            else:
                raise InvalidResourceTypeError(type(item).__name__)

    @property
    def name(self) -> str:
        """Returns the orchestrator name."""
        return self.__name

    @property
    def agent(self) -> Agent[DinamicDepend]:
        """Returns the built agent.

        Precondition: build_agent() has been called
        Postcondition: returns a valid Agent
        """
        if self.__agent is None:
            raise AgentNotBuiltError("ToToolManager")
        return self.__agent

    @property
    def middlewares(self) -> Sequence[Middleware]:
        """Returns the list of global middlewares.

        Precondition: middlewares is initialized
        Postcondition: returns Sequence[Middleware]
        """
        if self.__middlewares is None:
            raise MiddlewareNotInitializedError()
        return self.__middlewares

    def get_service(self, name: str) -> Service | Module:
        """Gets a service or module by name.

        Precondition: name exists in services or modules
        Postcondition: returns Service or Module
        
        Reference: REQ-001, REQ-002
        """
        if name in self.__services:
            return self.__services[name]
        if name in self.__modules:
            return self.__modules[name]
        all_names = list(self.__services.keys()) + list(self.__modules.keys())
        raise ServiceNotFoundError(name)

    @property
    def services(self) -> Dict[str, Service]:
        """Returns a copy of registered services."""
        return dict(self.__services)

    @property
    def modules(self) -> Dict[str, Module]:
        """Returns a copy of registered modules."""
        return dict(self.__modules)

    def _resolve_middlewares(self, service: Service) -> list[Middleware]:
        """Resolves which middlewares apply to a given service.

        Starts with global middlewares (ToToolManager level), removes
        those disabled by service.disable_middlewares, and adds
        service-level middlewares.

        Precondition: service has disable_middlewares defined
        Postcondition: returns filtered list of middlewares
        
        Reference: REQ-007
        """
        global_mws: Sequence[Middleware] = self.__middlewares or ()
        service_disable = set(getattr(service, "disable_middlewares", ()))
        service_mws = getattr(service, "middleware", []) or []

        resolved: list[Middleware] = []
        for mw in global_mws:
            mw_name = getattr(mw, "name", type(mw).__name__)
            if mw_name in service_disable:
                continue
            resolved.append(mw)

        # Add service-level middlewares
        for mw in service_mws:
            if isinstance(mw, Middleware):
                resolved.append(mw)

        return resolved

    def _apply_middlewares(
        self,
        dispatch_call: Any,
        middlewares: Sequence[Middleware],
    ) -> Any:
        """Applies a chain of middlewares around dispatch_call.

        Middlewares are applied in reverse order so that the first
        in the list is the one that executes first (outermost).
        ToolMiddleware instances are skipped here because they operate
        at the method level (handled in _build_dispatch_table).

        Precondition: middlewares are valid
        Postcondition: dispatch_call wrapped in middlewares
        """
        for mw in reversed(middlewares):
            if isinstance(mw, ToolMiddleware):
                continue
            original = dispatch_call

            async def _wrapped(*args: Any, _mw: Middleware = mw, _fn: Any = original, **kw: Any) -> Any:
                return await _mw.dispatch(_fn, *args, **kw)

            dispatch_call = _wrapped
        return dispatch_call

    def add_middleware_to_service(self, service_name: str, middleware: Middleware) -> None:
        """Adds a middleware to a specific service.

        Precondition: service_name exists, middleware is valid
        Postcondition: middleware added to the service
        """
        service = self.get_service(service_name)
        if isinstance(service, Service):
            if service.middleware is None:
                service.middleware = []
            service.middleware.append(middleware)
        else:
            raise MiddlewareTargetMismatchError(service_name, "Service")

    def add_middleware_to_module(self, module_name: str, middleware: Middleware) -> None:
        """Adds a middleware to a specific module.

        Precondition: module_name exists, middleware is valid
        Postcondition: middleware added to the module
        """
        module = self.get_service(module_name)
        if isinstance(module, Module):
            if module.middleware is None:
                module.middleware = []
            module.middleware.append(middleware)
        else:
            raise MiddlewareTargetMismatchError(module_name, "Module")

    def remove_middleware_to_service(self, service_name: str, middleware_type: type) -> None:
        """Removes a middleware from a service by type.

        Precondition: service_name exists, middleware_type is a valid type
        Postcondition: middleware removed from the service
        """
        service = self.get_service(service_name)
        if isinstance(service, Service):
            if service.middleware is not None:
                service.middleware = [m for m in service.middleware if not isinstance(m, middleware_type)]
        else:
            raise MiddlewareTargetMismatchError(service_name, "Service")

    def remove_middleware_to_module(self, module_name: str, middleware_type: type) -> None:
        """Removes a middleware from a module by type.

        Precondition: module_name exists, middleware_type is a valid type
        Postcondition: middleware removed from the module
        """
        module = self.get_service(module_name)
        if isinstance(module, Module):
            if module.middleware:
                module.middleware = [m for m in module.middleware if not isinstance(m, middleware_type)]
        else:
            raise MiddlewareTargetMismatchError(module_name, "Module")

    def build_agent(self,
        resources: Sequence[Service | Module] | None = None,
        middlewares: Sequence[Middleware] | None = None
    ) -> Agent[DinamicDepend]:
        """Builds the agent with registered services and modules.

        Precondition: services or modules registered
        Postcondition: __agent created

        Reference: REQ-003
        """
        # Use provided resources or registered ones
        if resources is not None:
            services_to_use = {}
            modules_to_use = {}
            for item in resources:
                if isinstance(item, Service):
                    services_to_use[item.name] = item
                elif isinstance(item, Module):
                    modules_to_use[item.name] = item
        else:
            services_to_use = self.__services
            modules_to_use = self.__modules

        # Use provided middlewares or registered ones
        if middlewares is not None:
            self.__middlewares = middlewares

        # Register services as dependencies
        for service in services_to_use.values():
            service.service_to_dependency(self.__dep)

        # Build module sub-agents
        sagents = []
        for module in modules_to_use.values():
            sagents.append(module.build_as_agent())

        sub_agents = SubAgents(agents=sagents)

        # Combine toolsets from __agent_params with sub-agents
        agent_params = dict(self.__agent_params)
        existing_toolsets = list(agent_params.pop('toolsets', None) or [])
        agent_params['toolsets'] = existing_toolsets + [sub_agents]

        agent = Agent(
            name=self.__name,
            deps_type=DinamicDepend,
            **agent_params,
        )

        self.__agent = agent
        return agent
