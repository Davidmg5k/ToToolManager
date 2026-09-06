"""Excepciones del builder.

Jerarquía:
    BuilderError
    ├── ToToolManagerAlreadyRegisteredError
    └── ToToolManagerNotFoundError
"""

from to_tool_manager.exception._ttm_error import TTMError


class BuilderError(TTMError):
    """Error en el builder (TTMBuilder / Manager)."""


class ToToolManagerAlreadyRegisteredError(BuilderError):
    """ToToolManager ya registrado con el mismo nombre."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"ToToolManager '{name}' already registered")


class ToToolManagerNotFoundError(BuilderError):
    """ToToolManager no encontrado por nombre."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"ToToolManager '{name}' not found")
