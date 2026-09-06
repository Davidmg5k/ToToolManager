"""Excepciones de módulos.

Jerarquía:
    ModuleError
    └── ModuleAlreadyRegisteredError
"""

from to_tool_manager.exception._ttm_error import TTMError


class ModuleError(TTMError):
    """Error relacionado con módulos."""


class ModuleAlreadyRegisteredError(ModuleError):
    """Módulo ya registrado con el mismo nombre."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Module '{name}' already registered")
