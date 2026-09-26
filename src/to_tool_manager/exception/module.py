"""Module and sub-agent exceptions.

Hierarchy:
    ModuleError
    ├── ModuleAlreadyRegisteredError
    │   └── SubAgentAlreadyRegisteredError
"""

from to_tool_manager.exception._ttm_error import TTMError


class ModuleError(TTMError):
    """Error related to modules."""


class ModuleAlreadyRegisteredError(ModuleError):
    """Module already registered with the same name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Module '{name}' already registered")


class SubAgentAlreadyRegisteredError(ModuleAlreadyRegisteredError):
    """Sub-agent already registered with the same name in the sub-agent roster.

    Sub-agents and modules share one roster, so a name is taken whichever way it
    was registered. Inherits `ModuleAlreadyRegisteredError` so callers already
    guarding the roster keep catching this.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        TTMError.__init__(self, f"Sub-agent '{name}' already registered in the sub-agent roster")
