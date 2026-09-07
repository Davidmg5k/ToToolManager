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
    """Represents a service that exposes methods as tools for LLMs.

    Precondition: service is a valid class with public methods
    Postcondition: Service can be converted to Capability via build_as_capability()
    
    Reference: REQ-001, REQ-006, REQ-007
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
        """Adds a ToolMiddleware or Middleware to the service's middleware list.

        Precondition: middleware is a valid ToolMiddleware
        Postcondition: middleware added to self.middleware
        
        Reference: REQ-006
        """
        if self.middleware is None:
            self.middleware = []
        self.middleware.append(middleware)

    def build_as_capability(self) -> Capability:
        """Converts the service into a Capability for pydantic-ai.

        Automatically discovers public methods of the service, applies
        ToolMiddlewares according to include/exclude, and creates tool wrappers.

        Flow: Method -> Middleware (if applicable) -> Tool

        Precondition: service is a valid class with methods
        Postcondition: returns Capability with registered tools
        
        Reference: REQ-001
        """
        methods = discover_methods(self.service)
        tools: list[Tool] = []

        for method_meta in methods:
            func = method_meta.func
            is_async = method_meta.is_async

            # Apply ToolMiddlewares (always BEFORE creating the tool)
            for mw in (self.middleware or []):
                if isinstance(mw, ToolMiddleware) and mw.is_allowed(method_meta.name):
                    func = mw(func)
                    # If the middleware is async, the resulting wrapper is async
                    is_async = inspect.iscoroutinefunction(func)

            # Create automatic wrapper
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
        """Registers the service as a dynamic dependency.

        Precondition: dinamic_depend is a valid DinamicDepend
        Postcondition: service registered as a dependency
        """
        service_to_dependency(self, dinamic_depend)