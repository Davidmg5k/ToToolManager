"""Middleware exceptions.

Hierarchy:
    MiddlewareError
    ├── MiddlewareNotInitializedError
    └── MiddlewareTargetMismatchError
"""

from to_tool_manager.exception._ttm_error import TTMError


class MiddlewareError(TTMError):
    """Error related to middlewares."""


class MiddlewareNotInitializedError(MiddlewareError):
    """Middleware sequence is not initialized (None)."""

    def __init__(self) -> None:
        super().__init__("Middleware sequence is not initialized (None)")


class MiddlewareTargetMismatchError(MiddlewareError):
    """Attempted add/remove of middleware on an incorrect target type."""

    def __init__(self, name: str, expected: str) -> None:
        self.name = name
        self.expected = expected
        super().__init__(
            f"'{name}' is not a {expected}. "
            f"Use the correct method for the target type."
        )
