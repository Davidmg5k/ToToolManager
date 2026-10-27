"""Builder exceptions.

Hierarchy:
    BuilderError
    ├── ToToolManagerAlreadyRegisteredError
    ├── ToToolManagerNotFoundError
    └── FastMCPNotInstalledError
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


class FastMCPNotInstalledError(BuilderError):
    """The optional `fastmcp` dependency is not installed.

    Raised by ``TTMBuilder.to_mcp_tool()`` when the environment does not
    provide ``fastmcp``. This is an expected, typed condition -- not an
    infrastructure surprise: `fastmcp` is declared as a dependency-group
    (PEP 735), which is not published in the package metadata, so a
    consumer that installs `to-tool-manager` alone will not receive it.

    Precondition: the caller invoked an MCP-export entry point
    Postcondition: the message states how to restore the capability
    """

    def __init__(self) -> None:
        super().__init__(
            "fastmcp is not installed, so TTMBuilder.to_mcp_tool() is unavailable. "
            'Install it in your project with: uv add "fastmcp>=4.0.9" '
            "(inside this repository: uv sync --all-groups)."
        )
