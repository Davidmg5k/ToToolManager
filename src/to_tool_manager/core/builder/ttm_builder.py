from typing import Any, List, Sequence, Tuple

from fastmcp import FastMCP
from pydantic_ai import (
    Agent,
    AgentModelSettings,
    AgentRetries,
    AgentToolset,
    AnyConcurrencyLimit,
    EndStrategy,
)
from pydantic_ai.models import Model, KnownModelName
from pydantic_ai_skills import Skill

from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.builder.manager import Manager
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.infra.types.main.service import Include, Exclude
from to_tool_manager.infra.types.main.signature import MethodsType
from to_tool_manager.exception import AgentNotBuiltError


class TTMBuilder:
    """Builder para crear agentes de forma declarativa.

    Precondición: name es un str válido
    Postcondición: Agent configurado vía fluent API

    Referencia: REQ-004
    """

    def __init__(self,
        name: str,
        capabilities: List | None = None,
        toolsets: List | None = None,
        model: Model | KnownModelName | str | None = None,
        instructions: Any = None,
        system_prompt: str | Sequence[str] = (),
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        validation_context: Any = None,
        tools: Sequence[Any] = (),
        defer_model_check: bool = False,
        end_strategy: EndStrategy = 'graceful',
        metadata: Any = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
        output_type: Any = str,
        description: str | None = None,
    ) -> None:
        """
        Precondición: name es un str válido
        Postcondición: Manager y DinamicDepend inicializados
        """
        self.__manager = Manager()
        self.__agent: Agent | None = None
        self.__dep = DinamicDepend()

        self.__name = name
        self.__capabilities = capabilities
        self.__toolsets = toolsets
        self.__middlewares: List[Middleware] = []

        # Almacenar parámetros del Agent para build()
        self.__model = model
        self.__instructions = instructions
        self.__system_prompt = system_prompt
        self.__model_settings = model_settings
        self.__retries = retries
        self.__validation_context = validation_context
        self.__tools = tools
        self.__defer_model_check = defer_model_check
        self.__end_strategy = end_strategy
        self.__metadata = metadata
        self.__tool_timeout = tool_timeout
        self.__max_concurrency = max_concurrency
        self.__output_type = output_type
        self.__description = description

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.build()

    @property
    def agent(self) -> Agent:
        """Retorna el agente construido.

        Precondición: build() ha sido llamado
        Postcondición: retorna Agent válido
        """
        if self.__agent is None:
            raise AgentNotBuiltError("TTMBuilder")
        return self.__agent

    @property
    def deps(self) -> DinamicDepend:
        """Retorna la instancia de dependencias con los servicios registrados.

        Precondición: add_service() ha sido llamado al menos una vez
        Postcondición: retorna DinamicDepend con servicios registrados
        """
        return self.__dep

    def build(self, model: str | None = None) -> None:
        """Construye el agente final con los componentes añadidos.

        Precondición: al menos un servicio o módulo añadido
        Postcondición: __agent creado

        Referencia: REQ-004
        """
        toolsets = self.__manager.toolsets(self.__toolsets)
        capabilities = self.__manager.capabilities(self.__capabilities)

        # model del build() tiene prioridad sobre el del __init__
        effective_model = model if model is not None else self.__model

        self.__agent = Agent(
            model=effective_model,
            name=self.__name,
            toolsets=toolsets,  # type: ignore
            capabilities=capabilities,
            instructions=self.__instructions or self.__name,
            deps_type=DinamicDepend,
            system_prompt=self.__system_prompt,
            model_settings=self.__model_settings,
            retries=self.__retries,
            validation_context=self.__validation_context,
            tools=self.__tools,
            defer_model_check=self.__defer_model_check,
            end_strategy=self.__end_strategy,
            metadata=self.__metadata,
            tool_timeout=self.__tool_timeout,
            max_concurrency=self.__max_concurrency,
            output_type=self.__output_type,
            description=self.__description,
        )

        # Aplicar middlewares generales a servicios registrados
        if self.__middlewares:
            self.__apply_middlewares_to_services()

    def add_service(self,
        name: str,
        service: type,
        instructions: str,
        middleware: List | None = None,
        disable_middlewares: Tuple[str, ...] = (),
        include: MethodsType | Include | None = None,
        exclude: MethodsType | Exclude | None = None,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> 'TTMBuilder':
        """Añade un servicio al builder.

        Precondición: name es único, service es una clase válida
        Postcondición: servicio añadido al manager, retorna self

        Referencia: REQ-001
        """
        self.__manager.add_service(Service(
            name=name,
            service=service,
            instructions=instructions,
            middleware=middleware or [],
            disable_middlewares=disable_middlewares,
            include=include,
            exclude=exclude,
            args=args,
            kwargs=kwargs or {},
        ), self.__dep)
        return self

    def add_module(self,
        name: str,
        services: Sequence[Service],
        description: str,
        middleware: List | None = None,
        disable_middlewares: Tuple[str, ...] = (),
        capabilities: List | None = None,
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
    ) -> 'TTMBuilder':
        """Añade un módulo al builder.

        Precondición: name es único, services no está vacío
        Postcondición: módulo añadido al manager, retorna self

        Referencia: REQ-002
        """
        module = Module(
            name=name,
            services=services,
            description=description,
            middleware=middleware,
            disable_middlewares=disable_middlewares,
            capabilities=capabilities,
            model=model,
            instructions=instructions,
            system_prompt=system_prompt,
            model_settings=model_settings,
            retries=retries,
            validation_context=validation_context,
            tools=tools,
            toolsets=toolsets,
            defer_model_check=defer_model_check,
            end_strategy=end_strategy,
            metadata=metadata,
            tool_timeout=tool_timeout,
            max_concurrency=max_concurrency,
            output_type=output_type,
        )
        self.__manager.add_module(module)
        for svc in services:
            svc.service_to_dependency(self.__dep)
        return self

    def add_middleware(self, middleware: Middleware) -> 'TTMBuilder':
        """Añade un middleware general al builder.

        Precondición: middleware es un Middleware válido
        Postcondición: middleware registrado, retorna self

        Referencia: REQ-005
        """
        self.__middlewares.append(middleware)
        return self

    def remove_middleware_to_service(self, service_name: str, middleware_type: type) -> 'TTMBuilder':
        """Remueve un middleware de un servicio por tipo.

        Precondición: service_name existe en servicios registrados
        Postcondición: middleware removido del servicio, retorna self

        Referencia: REQ-005
        """
        self.__manager.remove_middleware_from_services(service_name, middleware_type)
        return self

    def add_skill(self, skill: Skill) -> 'TTMBuilder':
        """Añade un skill al builder.

        Precondición: skill es un Skill válido
        Postcondición: skill registrado, retorna self
        """
        self.__manager.add_skill(skill)
        return self

    def add_ttm(self, manager: ToToolManager) -> 'TTMBuilder':
        """Añade un ToToolManager existente al builder.

        Precondición: manager es un ToToolManager válido
        Postcondición: manager registrado, retorna self
        """
        self.__manager.add_ttm(manager)
        return self

    def to_mcp_tool(self, 
        name: str, 
        instructions: str
    ) -> FastMCP:
        """Convierte el builder en un servidor MCP.

        Precondición: build() ha sido llamado
        Postcondición: retorna FastMCP con tools registradas
        
        Referencia: REQ-008
        """
        tools = []

        capabilities = self.__get_capabilities()
        for capability in capabilities:
            tools.extend(capability.tools)

        
        app = FastMCP(
            name=name,
            instructions=instructions,
            tools=tools
        )

        return app

    def __get_capabilities(self):
        """Retorna las capabilities registradas."""
        capabilities = self.__capabilities
        if capabilities is None:
            return []
        for capability in capabilities:
            yield capability

    def __apply_middlewares_to_services(self) -> None:
        """Aplica middlewares generales a todos los servicios registrados.

        Precondición: __middlewares no está vacío
        Postcondición: middlewares añadidos a cada servicio y Capabilities reconstruidas
        """
        self.__manager.apply_middlewares_to_services(self.__middlewares)
        self.__manager.rebuild_capabilities()
