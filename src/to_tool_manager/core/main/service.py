import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from pydantic_ai import Capability
from pydantic_ai.tools import Tool

from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.main.shared.discover import MethodMeta, discover_methods
from to_tool_manager.core.main.shared.tool_factory import make_tool
from to_tool_manager.core.main.shared.util import service_to_dependency
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.infra.types.main.service import Exclude, Include
from to_tool_manager.infra.types.main.signature import MethodsType


@dataclass(slots=True)
class Service:
    """Representa un servicio que expone métodos como herramientas para LLMs.

    Precondición: service es una clase válida con métodos públicos
    Postcondición: Service puede convertirse en Capability vía build_as_capability()
    
    Referencia: REQ-001, REQ-006, REQ-007
    """
    name: str
    service: type
    instructions: str
    middleware: List[ToolMiddleware | Middleware] | None = field(default_factory=list)
    disable_middlewares: Tuple[str, ...] = field(default_factory=tuple)
    include: MethodsType | Include | None = None
    exclude: MethodsType | Exclude | None = None
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def add_middleware(self, middleware: ToolMiddleware) -> None:
        """Añade un ToolMiddleware o Middleware a la lista de middlewares del servicio.

        Precondición: middleware es un ToolMiddleware válido
        Postcondición: middleware añadido a self.middleware
        
        Referencia: REQ-006
        """
        if self.middleware is None:
            self.middleware = []
        self.middleware.append(middleware)

    def build_as_capability(self) -> Capability:
        """Convierte el servicio en una Capability para pydantic-ai.

        Descubre automáticamente los métodos públicos del servicio, aplica
        los ToolMiddlewares según include/exclude, y crea tools wrapper.

        Flujo: Método → Middleware (si aplica) → Tool

        Precondición: service es una clase válida con métodos
        Postcondición: retorna Capability con tools registradas
        
        Referencia: REQ-001
        """
        methods = discover_methods(self.service)
        tools: list[Tool] = []

        for method_meta in methods:
            func = method_meta.func
            is_async = method_meta.is_async

            # Aplicar ToolMiddlewares (siempre ANTES de crear la tool)
            for mw in (self.middleware or []):
                if isinstance(mw, ToolMiddleware) and mw.is_allowed(method_meta.name):
                    func = mw(func)
                    # Si el middleware es async, el wrapper resultante es async
                    is_async = inspect.iscoroutinefunction(func)

            # Crear wrapper automática
            decorated_meta = MethodMeta(
                name=method_meta.name,
                func=func,
                is_async=is_async,
                docstring=method_meta.docstring,
                parameters=method_meta.parameters,
            )
            tool_func = make_tool(self.name, decorated_meta)
            tools.append(Tool(tool_func))

        return Capability(
            id=self.name,
            instructions=self.instructions,
            tools=tools,
            defer_loading=True,
        )

    def service_to_dependency(self, dinamic_depend: DinamicDepend) -> None:
        """Registra el servicio como dependencia dinámica.

        Precondición: dinamic_depend es un DinamicDepend válido
        Postcondición: servicio registrado como dependencia
        """
        service_to_dependency(self, dinamic_depend)