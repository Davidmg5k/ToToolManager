from dataclasses import dataclass, field
from typing import Any, Callable, Generator, List, Sequence, Tuple

from pydantic_ai import (
    Agent,
    AgentModelSettings,
    AgentRetries,
    AgentToolset,
    AnyConcurrencyLimit,
    Capability,
    EndStrategy,
    Tool,
)
from pydantic_ai.models import Model, KnownModelName
from pydantic_ai_harness.subagents import SubAgent

from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.main.shared.util import build_module_capabilities
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.exception import (
    AgentAlreadyBuiltError,
    AgentNotBuiltError,
    SelfDisableMiddlewareError,
)


@dataclass
class Module:
    """Agrupa servicios como sub-agente.

    Precondición: name es único, services no está vacío
    Postcondición: Module puede construirse como SubAgent vía build_as_agent()

    Referencia: REQ-002, REQ-007
    """
    name: str
    services: Sequence[Service]
    description: str
    capabilities: List[Capability] | None = None
    middleware: List | None = None
    disable_middlewares: Tuple[str, ...] = field(default_factory=tuple)
    model: Model | KnownModelName | str | None = None
    instructions: Any = None
    system_prompt: str | Sequence[str] = ()
    model_settings: AgentModelSettings | None = None
    retries: int | AgentRetries | None = None
    validation_context: Any | Callable | None = None
    tools: Sequence[Any] = ()
    toolsets: Sequence[AgentToolset] | None = None
    defer_model_check: bool = False
    end_strategy: EndStrategy = 'graceful'
    metadata: Any = None
    tool_timeout: float | None = None
    max_concurrency: Any = None
    output_type: Any = str

    def __post_init__(self):
        self.__agent: Agent[DinamicDepend] | None = None
        self.__dep = DinamicDepend()
        self._validate_no_self_disable()

    @property
    def agent(self) -> Agent[DinamicDepend]:
        if self.__agent is None:
            raise AgentNotBuiltError("Module")
        return self.__agent

    @agent.setter
    def agent(self, agent: Agent[DinamicDepend]):
        if self.__agent:
            raise AgentAlreadyBuiltError("Module")
        self.__agent = agent

    @property
    def dependency(self):
        return self.__dep

    def _validate_no_self_disable(self) -> None:
        """Valida que no se deshabiliten middlewares declarados en la misma clase.

        Precondición: ninguno
        Postcondición: ValueError si se intenta deshabilitar un middleware propio

        Referencia: REQ-007
        """
        if not self.middleware or not self.disable_middlewares:
            return
        disable_set = set(self.disable_middlewares)
        for mw in self.middleware:
            if not isinstance(mw, Middleware):
                continue
            mw_name = getattr(mw, "name", type(mw).__name__)
            if mw_name in disable_set:
                raise SelfDisableMiddlewareError(mw_name)

    def build_as_agent(self) -> SubAgent[DinamicDepend]:
        """Construye el módulo como SubAgent con sus servicios.

        Precondición: services no está vacío
        Postcondición: SubAgent creado con capabilities de cada servicio

        Flujo: Para cada servicio → filtrar middlewares deshabilitados →
               añadir middlewares del módulo → construir capability

        Referencia: REQ-002, REQ-007
        """
        cp = self.capabilities
        capabilities = [] + cp if cp else []

        build_module_capabilities(
            services=list(self.__get_services()),
            capabilities=capabilities,
            apply_middleware_fn=self._apply_module_middlewares,
            dep=self.__dep,
        )

        agent = Agent(
            name=self.name,
            description=self.description,
            deps_type=DinamicDepend,
            capabilities=capabilities,
            model=self.model,
            instructions=self.instructions,
            system_prompt=self.system_prompt,
            model_settings=self.model_settings,
            retries=self.retries,
            validation_context=self.validation_context,
            tools=self.tools,
            toolsets=self.toolsets,
            defer_model_check=self.defer_model_check,
            end_strategy=self.end_strategy,
            metadata=self.metadata,
            tool_timeout=self.tool_timeout,
            max_concurrency=self.max_concurrency,
            output_type=self.output_type,
        )

        self.agent = agent
        return SubAgent(agent)

    def _apply_module_middlewares(self, service: Service) -> None:
        """Aplica middlewares del módulo a un servicio, respetando disable_middlewares.

        Precondición: service es un Service válido
        Postcondición: middlewares del módulo añadidos al servicio (excepto los deshabilitados)

        Referencia: REQ-007
        """
        if not self.middleware:
            return

        service_disable = set(getattr(service, "disable_middlewares", ()))
        for mw in self.middleware:
            if not isinstance(mw, Middleware):
                continue
            mw_name = getattr(mw, "name", type(mw).__name__)
            if mw_name in self.disable_middlewares:
                continue
            if mw_name in service_disable:
                continue
            if service.middleware is None:
                service.middleware = []
            service.middleware.append(mw)

    def __get_services(self) -> Generator[Service, Any, None]:
        services = self.services 
        for service in services:
            yield service
   

    