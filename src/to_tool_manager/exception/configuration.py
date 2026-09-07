"""Configuration exceptions.

Hierarchy:
    ConfigurationError
    ├── InvalidResourceTypeError
    └── SelfDisableMiddlewareError
"""

from to_tool_manager.exception._ttm_error import TTMError


class ConfigurationError(TTMError):
    """Invalid configuration error."""


class InvalidResourceTypeError(ConfigurationError):
    """Resource is neither Service nor Module."""

    def __init__(self, got_type: str) -> None:
        self.got_type = got_type
        super().__init__(
            f"Expected Service or Module, got {got_type}"
        )


class SelfDisableMiddlewareError(ConfigurationError):
    """Module attempts to disable a middleware declared in the same class."""

    def __init__(self, middleware_name: str) -> None:
        self.middleware_name = middleware_name
        super().__init__(
            f"Cannot disable middleware '{middleware_name}' in the same class "
            f"that declares it. Disable it in the parent layer "
            f"(ToToolManager or Module) instead."
        )
