"""Excepciones de servicios.

Jerarquía:
    ServiceError
    ├── ServiceNotFoundError
    ├── ServiceAlreadyRegisteredError
    └── DependencyNotSetError
"""

from to_tool_manager.exception._ttm_error import TTMError


class ServiceError(TTMError):
    """Error relacionado con servicios."""


class ServiceNotFoundError(ServiceError):
    """Servicio no encontrado por nombre."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown service '{name}'")


class ServiceAlreadyRegisteredError(ServiceError):
    """Servicio ya registrado con el mismo nombre."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Service '{name}' already registered")


class DependencyNotSetError(ServiceError):
    """Atributo no existe en DinamicDepend."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"DinamicDepend has no attribute '{name}'")
