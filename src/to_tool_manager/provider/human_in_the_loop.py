from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable


class EventEmitter(ABC):
    """Protocol that the framework implements to emit events to the client.

    Implementation examples:
    - FastAPI + SSE: send event via Server-Sent Events
    - Django + WebSocket: send via WebSocket channel
    - Any transport: custom callback
    """

    @abstractmethod
    async def emit(self, event_id: str, payload: dict[str, Any]) -> None:
        """Emits a human input event to the client.

        Precondition: event_id is valid, payload contains event data
        Postcondition: event sent to client
        """
        ...


class HumanInputRetry(Exception):
    """Exception that logic throws when validation fails.

    The middleware catches this exception and retries the HITL cycle
    (emit -> wait for response -> validate).
    """


class HumanInTheLoop:
    """Core class of the human-in-the-loop flow.

    Coordinates event emission and suspension/resolution
    of tools that require human input before execution.

    Precondition: emitter is valid, logic is callable
    Postcondition: instance ready for execute()
    """

    __slots__ = ("_emitter", "_logic", "_args", "_kwargs", "_is_async_logic")

    def __init__(
        self,
        emitter: EventEmitter,
        logic: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Precondition: emitter implements EventEmitter, logic is callable
        Postcondition: emitter, logic, args, kwargs initialized

        Args:
            emitter: framework implementation for emitting events
            logic: async def logic(emit, event_fn, *args, **kwargs) -> None
                   Handles the full cycle: emit, wait, validate.
                   If validation fails -> raises HumanInputRetry.
            *args: positional arguments injected into logic
            **kwargs: named arguments injected into logic
        """
        self._emitter = emitter
        self._logic = logic
        self._args = args
        self._kwargs = kwargs
        self._is_async_logic = inspect.iscoroutinefunction(logic)

    async def execute(self, event_fn: Callable[[], Any]) -> None:
        """Executes the complete HITL cycle.

        Precondition: event_fn is callable that wraps the tool
        Postcondition: logic executed with emit and event_fn

        Flow:
        1. Creates emit_fn bound to the emitter
        2. Executes logic(emit_fn, event_fn, *args, **kwargs)
        3. If logic raises HumanInputRetry -> middleware retries
        4. If logic returns -> validation passed
        """
        async def emit_fn(event_id: str, payload: dict[str, Any]) -> None:
            await self._emitter.emit(event_id, payload)

        if self._is_async_logic:
            await self._logic(emit_fn, event_fn, *self._args, **self._kwargs)
        else:
            self._logic(emit_fn, event_fn, *self._args, **self._kwargs)
