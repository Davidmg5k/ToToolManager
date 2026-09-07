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
    """Builds event_fn that wraps the tool call.

    Precondition: func is callable
    Postcondition: returns callable that can be used as event_fn
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
    """Shared dispatch for HITL middlewares.

    Precondition: hitl is valid, func is callable
    Postcondition: tool executed if HITL validation passed, or error if retries exhausted

    Flow:
    1. Loop of max_retries attempts
    2. Each attempt: hitl.execute(event_fn)
    3. If HumanInputRetry -> retry
    4. If passed -> execute func(*args, **kw)
    5. If retries exhausted -> return error message
    """
    for attempt in range(max_retries):
        try:
            await hitl.execute(_build_event_func(func, kw))
            break
        except HumanInputRetry:
            if attempt == max_retries - 1:
                return "Maximum retries reached."
            continue
    return await Middleware.call_func(func, *args, **kw)


class HumanInTheLoopMiddleware(Middleware):
    """Global HITL middleware -- applies to all tools.

    Intercepts tool calls and executes the HITL cycle
    (emit -> wait -> validate) BEFORE allowing the tool
    to execute. Internal retries if validation fails.
    """

    __slots__ = ("_hitl", "_max_retries")

    def __init__(self, hitl: HumanInTheLoop, max_retries: int = 3) -> None:
        """
        Precondition: hitl is a valid HumanInTheLoop, max_retries > 0
        Postcondition: hitl and max_retries initialized
        """
        super().__init__()
        self._hitl = hitl
        self._max_retries = max_retries

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        return await run_hitl_dispatch(
            self._hitl, func, self._max_retries, *args, **kw,
        )


class HumanInTheLoopToolMiddleware(ToolMiddleware):
    """Per-method HITL middleware -- with include/exclude.

    Same as HumanInTheLoopMiddleware but with method filtering
    via include/exclude inherited from ToolMiddleware.
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
        Precondition: hitl is a valid HumanInTheLoop, max_retries > 0
        Postcondition: hitl, max_retries, include, exclude initialized
        """
        super().__init__(include=include, exclude=exclude)
        self.__hitl = hitl
        self.__max_retries = max_retries

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        return await run_hitl_dispatch(
            self.__hitl, func, self.__max_retries, *args, **kw,
        )
