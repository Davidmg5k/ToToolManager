from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable


class EventEmitter(ABC):
    """Protocolo que el framework implementa para emitir eventos al cliente.

    Ejemplos de implementación:
    - FastAPI + SSE: enviar evento via Server-Sent Events
    - Django + WebSocket: enviar via canal WebSocket
    - Cualquier transport: callback personalizado
    """

    @abstractmethod
    async def emit(self, event_id: str, payload: dict[str, Any]) -> None:
        """Emite un evento de input humano al cliente.

        Precondición: event_id es válido, payload contiene datos del evento
        Postcondición: evento enviado al cliente
        """
        ...


class HumanInputRetry(Exception):
    """Exception que la logic lanza cuando la validación falla.

    El middleware captura esta exception y reintenta el ciclo
    HITL (emit → esperar respuesta → validar).
    """


class HumanInTheLoop:
    """Clase central del flujo human-in-the-loop.

    Coordina la emisión de eventos y la suspensión/resolución
    de tools que requieren input humano antes de ejecutarse.

    Precondición: emitter es válido, logic es callable
    Postcondición: instancia lista para execute()
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
        Precondición: emitter implementa EventEmitter, logic es callable
        Postcondición: emitter, logic, args, kwargs inicializados

        Args:
            emitter: implementación del framework para emitir eventos
            logic: async def logic(emit, event_fn, *args, **kwargs) -> None
                   Maneja todo el ciclo: emitir, esperar, validar.
                   Si validación falla → lanza HumanInputRetry.
            *args: argumentos posicionales que se inyectan a logic
            **kwargs: argumentos nombrados que se inyectan a logic
        """
        self._emitter = emitter
        self._logic = logic
        self._args = args
        self._kwargs = kwargs
        self._is_async_logic = inspect.iscoroutinefunction(logic)

    async def execute(self, event_fn: Callable[[], Any]) -> None:
        """Ejecuta el ciclo HITL completo.

        Precondición: event_fn es callable que encapsula la tool
        Postcondición: logic ejecutada con emit y event_fn

        Flujo:
        1. Crea emit_fn vinculada al emitter
        2. Ejecuta logic(emit_fn, event_fn, *args, **kwargs)
        3. Si logic lanza HumanInputRetry → middleware reintenta
        4. Si logic retorna → validación pasó
        """
        async def emit_fn(event_id: str, payload: dict[str, Any]) -> None:
            await self._emitter.emit(event_id, payload)

        if self._is_async_logic:
            await self._logic(emit_fn, event_fn, *self._args, **self._kwargs)
        else:
            self._logic(emit_fn, event_fn, *self._args, **self._kwargs)
