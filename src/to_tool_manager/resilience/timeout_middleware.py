"""Explicit timeout middleware (Bloque 3 -- Resiliencia).

Opt-in only, same registration path as any other `Middleware` -- a
`ToToolManager`/`Service` built without it behaves identically to
before this module existed.

Why this exists alongside `build_agent()`'s existing `tool_timeout`
kwarg: that one is a pure passthrough to pydantic-ai's own `Agent`
constructor -- it only applies when going through that specific
adapter, and its behavior (what happens on expiry, what the LLM sees)
is entirely up to pydantic-ai. `TimeoutMiddleware` is adapter-agnostic:
it applies at the `ToToolManager`/`Service` dispatch layer itself, so it
works the same way regardless of which adapter (or none) sits on top,
and it surfaces expiry the same way any other tool failure already does
in this project -- a `ToolResponse` with a `ToolError`, not a raised
exception -- using the exact `category="timeout", retryable=True`
convention already documented in `ErrorMap`'s own docstring example
(`core/types.py`). Both can be used together with no interaction: this
middleware never touches pydantic-ai's `tool_timeout`, and vice versa.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from to_tool_manager.core.types import ToolError, ToolResponse
from to_tool_manager.security.middleware import Middleware


class TimeoutMiddleware(Middleware):
    """Bounds how long a single dispatch_call batch may run.

    Applies to the whole batch passed to one `Service`'s `dispatch_call`
    (i.e. one `{"operations": [...]}` call, which may itself contain
    several `{"method", "args"}` entries) -- not to each individual
    operation inside it, matching the granularity `Middleware.dispatch()`
    actually intercepts at.

    On expiry, the in-flight call is cancelled (via `asyncio.timeout`)
    and a `ToolResponse(error=ToolError(category="timeout",
    retryable=True, ...))` is returned -- never a raised
    `TimeoutError`/`CancelledError` -- so the LLM sees an ordinary,
    already-familiar tool error it can react to (e.g. retry with a
    smaller batch), rather than an unhandled exception reaching the
    agent framework.

    Args:
        seconds: Timeout in seconds for the whole dispatch_call batch.
            Must be positive.

    Example::

        service = Service(
            name="Orders",
            service=OrderService,
            middlewares=[TimeoutMiddleware(seconds=10.0)],
        )
    """

    __slots__ = ("__seconds",)

    def __init__(self, seconds: float) -> None:
        super().__init__()
        if seconds <= 0:
            raise ValueError(f"seconds must be positive, got {seconds!r}")
        self.__seconds = seconds

    @property
    def seconds(self) -> float:
        return self.__seconds

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        try:
            async with asyncio.timeout(self.__seconds):
                return await func(*args, **kw)
        except TimeoutError:
            return ToolResponse(
                error=ToolError(
                    category=frozenset({"timeout"}),
                    message=f"Tool call exceeded the {self.__seconds}s timeout.",
                    exception_type="TimeoutError",
                    retryable=True,
                )
            )
