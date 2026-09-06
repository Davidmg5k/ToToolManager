"""Excepciones de agentes.

Jerarquía:
    AgentError
    ├── AgentNotBuiltError
    └── AgentAlreadyBuiltError
"""

from to_tool_manager.exception._ttm_error import TTMError


class AgentError(TTMError):
    """Error en la construcción del agente."""


class AgentNotBuiltError(AgentError):
    """Se accedió al agente antes de llamar build()."""

    def __init__(self, component: str) -> None:
        self.component = component
        super().__init__(
            f"Agent not built. Call build() first on {component}."
        )


class AgentAlreadyBuiltError(AgentError):
    """Se intentó construir el agente cuando ya estaba construido."""

    def __init__(self, component: str) -> None:
        self.component = component
        super().__init__(
            f"Agent already built on {component}. Cannot rebuild."
        )
