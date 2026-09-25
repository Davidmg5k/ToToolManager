"""Service exceptions.

Hierarchy:
    ServiceError
    ├── ServiceNotFoundError
    ├── ServiceAlreadyRegisteredError
    └── DependencyNotSetError
"""

from to_tool_manager.exception._ttm_error import TTMError


class ServiceError(TTMError):
    """Error related to services."""


class ServiceNotFoundError(ServiceError):
    """Service not found by name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown service '{name}'")


class ServiceAlreadyRegisteredError(ServiceError):
    """Service already registered with the same name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Service '{name}' already registered")


class DependencyNotSetError(ServiceError, AttributeError):
    """Attribute does not exist in DinamicDepend.

    Inherits from AttributeError so that Python's data-model contract is
    preserved: hasattr() returns False and getattr(obj, name, default)
    returns the default. Direct attribute access still raises this error.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"DinamicDepend has no attribute '{name}'")
