"""Excepciones de middlewares.

Jerarquía:
    MiddlewareError
    ├── MiddlewareNotInitializedError
    └── MiddlewareTargetMismatchError
"""

from to_tool_manager.exception._ttm_error import TTMError


class MiddlewareError(TTMError):
    """Error relacionado con middlewares."""


class MiddlewareNotInitializedError(MiddlewareError):
    """La secuencia de middlewares no está inicializada (None)."""

    def __init__(self) -> None:
        super().__init__("Middleware sequence is not initialized (None)")


class MiddlewareTargetMismatchError(MiddlewareError):
    """Intento de add/remove de middleware en un tipo de target incorrecto."""

    def __init__(self, name: str, expected: str) -> None:
        self.name = name
        self.expected = expected
        super().__init__(
            f"'{name}' is not a {expected}. "
            f"Use the correct method for the target type."
        )
