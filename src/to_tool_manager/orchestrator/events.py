from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class OrchestratorEventType(str, Enum):
    """Event types for the orchestrator lifecycle."""
    AGENT_ADDED = "agent_added"
    AGENT_REMOVED = "agent_removed"
    AGENT_INITIALIZED = "agent_initialized"
    ORCHESTRATOR_STARTED = "orchestrator_started"
    ORCHESTRATOR_STOPPED = "orchestrator_stopped"


@dataclass(frozen=True, slots=True)
class OrchestratorEvent:
    """Event emitted by the orchestrator during its lifecycle."""
    type: OrchestratorEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class OrchestratorEventHandler(Protocol):
    """Protocol for handlers that consume orchestrator events.

    Example::

        class MyHandler:
            async def on_event(self, event: OrchestratorEvent) -> None:
                print(f"Event: {event.type.value}")
    """
    async def on_event(self, event: OrchestratorEvent) -> None: ...