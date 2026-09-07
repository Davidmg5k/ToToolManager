"""Agent exceptions.

Hierarchy:
    AgentError
    ├── AgentNotBuiltError
    └── AgentAlreadyBuiltError
"""

from to_tool_manager.exception._ttm_error import TTMError


class AgentError(TTMError):
    """Error in agent construction."""


class AgentNotBuiltError(AgentError):
    """Agent was accessed before calling build()."""

    def __init__(self, component: str) -> None:
        self.component = component
        super().__init__(
            f"Agent not built. Call build() first on {component}."
        )


class AgentAlreadyBuiltError(AgentError):
    """Attempted to build the agent when it was already built."""

    def __init__(self, component: str) -> None:
        self.component = component
        super().__init__(
            f"Agent already built on {component}. Cannot rebuild."
        )
