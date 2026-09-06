"""to_tool_manager — Paquete principal.

Public API:
- Service: Expone métodos como tools para LLMs
- Module: Agrupa servicios como sub-agente
- ToToolManager: Orquestador de servicios y módulos
- TTMBuilder: Builder para crear agentes de forma declarativa
- Middleware: Base middleware abstracta
- ToolMiddleware: Middleware con filtrado por método
- NodeMiddleware: Base middleware para nodos de grafo
- GraphMiddlewareRunner: Ejecutor de grafo con middleware
- EventEmitter: Protocolo para emisión de eventos HITL
- HumanInTheLoop: Clase central del flujo human-in-the-loop
- HumanInTheLoopMiddleware: HITL global (aplica a todas las tools)
- HumanInTheLoopToolMiddleware: HITL por método (con include/exclude)
- HumanInputRetry: Exception para reintentos de validación HITL
- Excepciones: TTMError y subtipos para manejo de errores
"""

from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.middleware.middleware import (
    Middleware,
    NodeMiddleware,
    ToolMiddleware,
)
from to_tool_manager.middleware.graph_runner import GraphMiddlewareRunner
from to_tool_manager.provider import (
    EventEmitter,
    HumanInTheLoop,
    HumanInputRetry,
)
from to_tool_manager.middleware import (
    HumanInTheLoopMiddleware,
    HumanInTheLoopToolMiddleware,
)
from to_tool_manager.exception import (
    TTMError,
    ConfigurationError,
    InvalidResourceTypeError,
    SelfDisableMiddlewareError,
    ServiceError,
    ServiceNotFoundError,
    ServiceAlreadyRegisteredError,
    DependencyNotSetError,
    ModuleError,
    ModuleAlreadyRegisteredError,
    AgentError,
    AgentNotBuiltError,
    AgentAlreadyBuiltError,
    MiddlewareError,
    MiddlewareNotInitializedError,
    MiddlewareTargetMismatchError,
    BuilderError,
    ToToolManagerAlreadyRegisteredError,
    ToToolManagerNotFoundError,
)

__all__ = [
    "Service",
    "Module",
    "ToToolManager",
    "TTMBuilder",
    "Middleware",
    "ToolMiddleware",
    "NodeMiddleware",
    "GraphMiddlewareRunner",
    "EventEmitter",
    "HumanInTheLoop",
    "HumanInTheLoopMiddleware",
    "HumanInTheLoopToolMiddleware",
    "HumanInputRetry",
    "TTMError",
    "ConfigurationError",
    "InvalidResourceTypeError",
    "SelfDisableMiddlewareError",
    "ServiceError",
    "ServiceNotFoundError",
    "ServiceAlreadyRegisteredError",
    "DependencyNotSetError",
    "ModuleError",
    "ModuleAlreadyRegisteredError",
    "AgentError",
    "AgentNotBuiltError",
    "AgentAlreadyBuiltError",
    "MiddlewareError",
    "MiddlewareNotInitializedError",
    "MiddlewareTargetMismatchError",
    "BuilderError",
    "ToToolManagerAlreadyRegisteredError",
    "ToToolManagerNotFoundError",
]


__version__ = "0.9.0"