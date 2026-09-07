"""Module exceptions.

Hierarchy:
    ModuleError
    └── ModuleAlreadyRegisteredError
"""

from to_tool_manager.exception._ttm_error import TTMError


class ModuleError(TTMError):
    """Error related to modules."""


class ModuleAlreadyRegisteredError(ModuleError):
    """Module already registered with the same name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Module '{name}' already registered")
