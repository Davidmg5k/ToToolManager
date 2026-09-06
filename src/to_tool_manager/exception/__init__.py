"""Excepciones personalizadas de to_tool_manager.

Todas las excepciones del paquete heredan de TTMError para permitir
capture genérico y discriminación por subtipo.

Jerarquía:
    TTMError
    ├── ConfigurationError
    │   ├── InvalidResourceTypeError
    │   └── SelfDisableMiddlewareError
    ├── ServiceError
    │   ├── ServiceNotFoundError
    │   ├── ServiceAlreadyRegisteredError
    │   └── DependencyNotSetError
    ├── ModuleError
    │   └── ModuleAlreadyRegisteredError
    ├── AgentError
    │   ├── AgentNotBuiltError
    │   └── AgentAlreadyBuiltError
    ├── MiddlewareError
    │   ├── MiddlewareNotInitializedError
    │   └── MiddlewareTargetMismatchError
    └── BuilderError
        ├── ToToolManagerAlreadyRegisteredError
        └── ToToolManagerNotFoundError
"""

from to_tool_manager.exception._ttm_error import TTMError
from to_tool_manager.exception.configuration import (
    ConfigurationError,
    InvalidResourceTypeError,
    SelfDisableMiddlewareError,
)
from to_tool_manager.exception.service import (
    ServiceError,
    ServiceNotFoundError,
    ServiceAlreadyRegisteredError,
    DependencyNotSetError,
)
from to_tool_manager.exception.module import (
    ModuleError,
    ModuleAlreadyRegisteredError,
)
from to_tool_manager.exception.agent import (
    AgentError,
    AgentNotBuiltError,
    AgentAlreadyBuiltError,
)
from to_tool_manager.exception.middleware import (
    MiddlewareError,
    MiddlewareNotInitializedError,
    MiddlewareTargetMismatchError,
)
from to_tool_manager.exception.builder import (
    BuilderError,
    ToToolManagerAlreadyRegisteredError,
    ToToolManagerNotFoundError,
)

__all__ = [
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
