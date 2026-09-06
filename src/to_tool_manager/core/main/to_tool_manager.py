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
    """Orquestador de servicios y módulos.

    Precondición: resources no está vacío, middlewares son válidos
    Postcondición: servicios y módulos registrados, listos para construir agentes

    Referencia: REQ-003, REQ-005, REQ-007
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
        Precondición: resources no está vacío
        Postcondición: __services, __modules y __middlewares inicializados
        """
        self.__name = name
        self.__agent: Agent[DinamicDepend] | None = None
        self.__dep = DinamicDepend()

        # Almacenar parámetros del Agent para build_agent()
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

        # Almacenar servicios y módulos
        self.__services: Dict[str, Service] = {}
        self.__modules: Dict[str, Module] = {}
        self.__middlewares: Sequence[Middleware] | None = middlewares

        # Parsear resources
        for item in resources:
            if isinstance(item, Service):
                self.__services[item.name] = item
            elif isinstance(item, Module):
                self.__modules[item.name] = item
            else:
                raise InvalidResourceTypeError(type(item).__name__)

    @property
    def name(self) -> str:
        """Retorna el nombre del orquestador."""
        return self.__name

    @property
    def agent(self) -> Agent[DinamicDepend]:
        """Retorna el agente construido.

        Precondición: build_agent() ha sido llamado
        Postcondición: retorna Agent válido
        """
        if self.__agent is None:
            raise AgentNotBuiltError("ToToolManager")
        return self.__agent

    @property
    def dep(self):
        return self.__dep

    @property
    def middlewares(self) -> Sequence[Middleware]:
        """Retorna la lista de middlewares globales.

        Precondición: middlewares está inicializado
        Postcondición: retorna Sequence[Middleware]
        """
        if self.__middlewares is None:
            raise MiddlewareNotInitializedError()
        return self.__middlewares

    def get_service(self, name: str) -> Service | Module:
        """Obtiene un servicio o módulo por nombre.

        Precondición: name existe en servicios o módulos
        Postcondición: retorna Service o Module
        
        Referencia: REQ-001, REQ-002
        """
        if name in self.__services:
            return self.__services[name]
        if name in self.__modules:
            return self.__modules[name]
        all_names = list(self.__services.keys()) + list(self.__modules.keys())
        raise ServiceNotFoundError(name)

    @property
    def services(self) -> Dict[str, Service]:
        """Retorna copia de servicios registrados."""
        return dict(self.__services)

    @property
    def modules(self) -> Dict[str, Module]:
        """Retorna copia de módulos registrados."""
        return dict(self.__modules)

    def _resolve_middlewares(self, service: Service) -> list[Middleware]:
        """Resuelve qué middlewares aplican a un servicio dado.

        Comienza con middlewares globales (nivel ToToolManager), remueve
        los deshabilitados por service.disable_middlewares, y añade
        los middlewares del nivel servicio.

        Precondición: service tiene disable_middlewares definido
        Postcondición: retorna lista filtrada de middlewares
        
        Referencia: REQ-007
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

        # Añadir middlewares de nivel servicio
        for mw in service_mws:
            if isinstance(mw, Middleware):
                resolved.append(mw)

        return resolved

    def _apply_middlewares(
        self,
        dispatch_call: Any,
        middlewares: Sequence[Middleware],
    ) -> Any:
        """Aplica una cadena de middlewares alrededor de dispatch_call.

        Los middlewares se aplican en orden inverso para que el primero
        de la lista sea el que se ejecuta primero (más externo).
        Las instancias de ToolMiddleware se saltan aquí porque operan
        a nivel de método (manejado en _build_dispatch_table).

        Precondición: middlewares son válidos
        Postcondición: dispatch_call envuelto en middlewares
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
        """Añade un middleware a un servicio específico.

        Precondición: service_name existe, middleware es válido
        Postcondición: middleware añadido al servicio
        """
        service = self.get_service(service_name)
        if isinstance(service, Service):
            if service.middleware is None:
                service.middleware = []
            service.middleware.append(middleware)
        else:
            raise MiddlewareTargetMismatchError(service_name, "Service")

    def add_middleware_to_module(self, module_name: str, middleware: Middleware) -> None:
        """Añade un middleware a un módulo específico.

        Precondición: module_name existe, middleware es válido
        Postcondición: middleware añadido al módulo
        """
        module = self.get_service(module_name)
        if isinstance(module, Module):
            if module.middleware is None:
                module.middleware = []
            module.middleware.append(middleware)
        else:
            raise MiddlewareTargetMismatchError(module_name, "Module")

    def remove_middleware_to_service(self, service_name: str, middleware_type: type) -> None:
        """Remueve un middleware de un servicio por tipo.

        Precondición: service_name existe, middleware_type es un tipo válido
        Postcondición: middleware removido del servicio
        """
        service = self.get_service(service_name)
        if isinstance(service, Service):
            if service.middleware is not None:
                service.middleware = [m for m in service.middleware if not isinstance(m, middleware_type)]
        else:
            raise MiddlewareTargetMismatchError(service_name, "Service")

    def remove_middleware_to_module(self, module_name: str, middleware_type: type) -> None:
        """Remueve un middleware de un módulo por tipo.

        Precondición: module_name existe, middleware_type es un tipo válido
        Postcondición: middleware removido del módulo
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
        """Construye el agente con los servicios y módulos registrados.

        Precondición: servicios o módulos registrados
        Postcondición: __agent creado

        Referencia: REQ-003
        """
        # Usar recursos proporcionados o los registrados
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

        # Usar middlewares proporcionados o los registrados
        if middlewares is not None:
            self.__middlewares = middlewares

        # Registrar servicios como dependencias
        for service in services_to_use.values():
            service.service_to_dependency(self.__dep)

        # Construir sub-agentes de módulos
        sagents = []
        for module in modules_to_use.values():
            sagents.append(module.build_as_agent())

        sub_agents = SubAgents(agents=sagents)

        # Combinar toolsets de __agent_params con los sub-agentes
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
