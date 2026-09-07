"""Builder exceptions.

Hierarchy:
    BuilderError
    ├── ToToolManagerAlreadyRegisteredError
    └── ToToolManagerNotFoundError
"""

from to_tool_manager.exception._ttm_error import TTMError


class BuilderError(TTMError):
    """Error in the builder (TTMBuilder / Manager)."""


class ToToolManagerAlreadyRegisteredError(BuilderError):
    """ToToolManager already registered with the same name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"ToToolManager '{name}' already registered")


class ToToolManagerNotFoundError(BuilderError):
    """ToToolManager not found by name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"ToToolManager '{name}' not found")
