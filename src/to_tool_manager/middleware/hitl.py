from __future__ import annotations

from typing import Any, Callable

from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.infra.types.main.service import Include, Exclude
from to_tool_manager.infra.types.main.signature import MethodsType
from to_tool_manager.provider.human_in_the_loop import (
    HumanInTheLoop,
    HumanInputRetry,
)


def _build_event_func(
    func: Callable[..., Any],
    kwargs: dict[str, Any],
) -> Callable[[], Any]:
    """Construye event_fn que encapsula la llamada a la tool.

    Precondición: func es callable
    Postcondición: retorna callable que puede ser usado como event_fn
    """
    def event_fn() -> Any:
        return func(**kwargs)
    return event_fn


async def run_hitl_dispatch(
    hitl: HumanInTheLoop,
    func: Callable[..., Any],
    max_retries: int,
    /,
    *args: Any,
    **kw: Any,
) -> Any:
    """Dispatch compartido para HITL middlewares.

    Precondición: hitl es válido, func es callable
    Postcondición: tool ejecutada si validación HITL pasó, o error si agotó reintentos

    Flujo:
    1. Loop de max_retries intentos
    2. Cada intento: hitl.execute(event_fn)
    3. Si HumanInputRetry → reintenta
    4. Si pasa → ejecuta func(*args, **kw)
    5. Si agota reintentos → retorna mensaje de error
    """
    for attempt in range(max_retries):
        try:
            await hitl.execute(_build_event_func(func, kw))
            break
        except HumanInputRetry:
            if attempt == max_retries - 1:
                return "Máximo de reintentos alcanzado."
            continue
    return await Middleware.call_func(func, *args, **kw)


class HumanInTheLoopMiddleware(Middleware):
    """Middleware HITL global — aplica a todas las tools.

    Intercepta las llamadas a tools y ejecuta el ciclo HITL
    (emit → esperar → validar) ANTES de permitir la ejecución
    de la tool. Reintentos internos si la validación falla.
    """

    __slots__ = ("_hitl", "_max_retries")

    def __init__(self, hitl: HumanInTheLoop, max_retries: int = 3) -> None:
        """
        Precondición: hitl es HumanInTheLoop válido, max_retries > 0
        Postcondición: hitl y max_retries inicializados
        """
        super().__init__()
        self._hitl = hitl
        self._max_retries = max_retries

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        return await run_hitl_dispatch(
            self._hitl, func, self._max_retries, *args, **kw,
        )


class HumanInTheLoopToolMiddleware(ToolMiddleware):
    """Middleware HITL por método — con include/exclude.

    Igual que HumanInTheLoopMiddleware pero con filtrado
    de métodos vía include/exclude heredado de ToolMiddleware.
    """

    __slots__ = ("__hitl", "__max_retries")

    def __init__(
        self,
        hitl: HumanInTheLoop,
        max_retries: int = 3,
        include: MethodsType | Include | None = None,
        exclude: MethodsType | Exclude | None = None,
    ) -> None:
        """
        Precondición: hitl es HumanInTheLoop válido, max_retries > 0
        Postcondición: hitl, max_retries, include, exclude inicializados
        """
        super().__init__(include=include, exclude=exclude)
        self.__hitl = hitl
        self.__max_retries = max_retries

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        return await run_hitl_dispatch(
            self.__hitl, func, self.__max_retries, *args, **kw,
        )
