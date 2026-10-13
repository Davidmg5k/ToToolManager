"""Module and sub-agent exceptions.

Hierarchy:
    ModuleError
    ├── ModuleAlreadyRegisteredError
    │   └── SubAgentAlreadyRegisteredError
    └── SubAgentNameRequiredError
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


class SubAgentNameRequiredError(ModuleError):
    """A delegate Agent was registered without a name to delegate to.

    The sub-agent roster is keyed by name, and that name is how the parent
    model refers to the delegate, so an Agent built without one cannot be
    registered. Raised at registration time instead of at build time, where
    the failure would surface as a harness error far from its cause.
    """

    def __init__(self) -> None:
        super().__init__(
            "Sub-agent has no name. Build it as Agent(name=..., ...) -- "
            "the name is what the parent model delegates to."
        )
