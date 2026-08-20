"""Retry-with-backoff middleware (Bloque 3 -- Resiliencia).

Opt-in only, same registration path as any other `Middleware` -- a
`ToToolManager`/`Service` built without it behaves identically to
before this module existed.

Design decision, and why: this middleware only retries a dispatch_call
batch when the returned `ToolResponse` is explicitly marked
`retryable=True` on its `ToolError` -- the exact convention this
project already established (`ErrorMap`'s own docstring example: `.when(
lambda e: hasattr(e, 'timeout'), category="timeout", retryable=True)`,
and `TimeoutMiddleware`'s own error uses the same flag). It does NOT
retry on a raised exception by default. Rationale: an exception reaching
this middleware means something upstream chose to raise rather than
return a `ToolResponse` -- per the `Middleware` base class's own
documented contract, that's how "intentional blocking" (auth, rate
limiting, etc.) is expressed. Blindly retrying any raised exception
would silently retry things that were never meant to be retried (e.g.
a `PermissionError` from an auth middleware), which is a worse default
than under-retrying. Retrying raised exceptions too is possible via
`retry_on_exceptions` for callers who know their specific failure modes
raise instead of returning a retryable ToolResponse.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, Sequence, Type

from to_tool_manager.core.types import ToolResponse
from to_tool_manager.security.middleware import Middleware


class RetryMiddleware(Middleware):
    """Retries a dispatch_call batch with exponential backoff + jitter
    when the result is marked retryable.

    Args:
        max_attempts: Total attempts including the first (not
            "retries" -- `max_attempts=3` means up to 2 retries after
            the initial call). Must be >= 1.
        base_delay: Delay before the first retry, in seconds.
        max_delay: Upper bound on any single delay, in seconds.
        jitter: Fraction of the computed delay (before the cap) to
            randomize by, in `[0, 1]`, to avoid retry storms across
            many concurrent callers backing off in lockstep. Defaults
            to 0.1 (+/-10%).
        retry_on_exceptions: Exception types that should ALSO trigger a
            retry when raised by whatever this middleware wraps (see
            module docstring for why this isn't the default). Empty by
            default -- raised exceptions propagate immediately, exactly
            like without this middleware.

    Backoff formula for attempt `n` (0-indexed retry number, so the
    first retry is `n=0`): `min(max_delay, base_delay * 2**n)`, then
    jittered by +/- `jitter` fraction.

    Example::

        service = Service(
            name="Orders",
            service=OrderService,
            middlewares=[RetryMiddleware(max_attempts=3, base_delay=0.5)],
        )
    """

    __slots__ = ("__max_attempts", "__base_delay", "__max_delay", "__jitter", "__retry_on_exceptions", "__sleep")

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        jitter: float = 0.1,
        retry_on_exceptions: Sequence[Type[BaseException]] = (),
        _sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        super().__init__()
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts!r}")
        if base_delay < 0 or max_delay < 0:
            raise ValueError("base_delay and max_delay must be non-negative")
        if not (0.0 <= jitter <= 1.0):
            raise ValueError(f"jitter must be in [0, 1], got {jitter!r}")
        self.__max_attempts = max_attempts
        self.__base_delay = base_delay
        self.__max_delay = max_delay
        self.__jitter = jitter
        self.__retry_on_exceptions = tuple(retry_on_exceptions)
        self.__sleep = _sleep  # injectable for tests, so real backoff timing isn't needed to verify retry logic

    def _delay_for(self, retry_index: int) -> float:
        raw = min(self.__max_delay, self.__base_delay * (2**retry_index))
        if self.__jitter == 0.0:
            return raw
        spread = raw * self.__jitter
        return max(0.0, raw + random.uniform(-spread, spread))

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        last_response: ToolResponse | None = None
        for attempt in range(self.__max_attempts):
            try:
                response = await func(*args, **kw)
            except self.__retry_on_exceptions:
                if attempt == self.__max_attempts - 1:
                    raise
                await self.__sleep(self._delay_for(attempt))
                continue

            if not isinstance(response, ToolResponse) or response.ok or response.error is None or not response.error.retryable:
                return response

            last_response = response
            if attempt == self.__max_attempts - 1:
                return response
            await self.__sleep(self._delay_for(attempt))

        # Unreachable if max_attempts >= 1 (loop always returns/raises
        # on its last iteration), kept only to satisfy static analysis.
        assert last_response is not None
        return last_response
