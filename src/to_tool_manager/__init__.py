"""to_tool_manager — Main package.

Public API:
- Service: Exposes methods as tools for LLMs
- Module: Groups services as a sub-agent
- ToToolManager: Orchestrator of services and modules
- TTMBuilder: Builder for creating agents declaratively
- Middleware: Abstract base middleware
- ToolMiddleware: Middleware with method filtering
- NodeMiddleware: Base middleware for graph nodes
- GraphMiddlewareRunner: Graph executor with middleware
- EventEmitter: Protocol for HITL event emission
- HumanInTheLoop: Core class for the human-in-the-loop flow
- HumanInTheLoopMiddleware: Global HITL (applies to all tools)
- HumanInTheLoopToolMiddleware: Per-method HITL (with include/exclude)
- HumanInputRetry: Exception for HITL validation retries
- Exceptions: TTMError and subtypes for error handling
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
