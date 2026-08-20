"""Circuit breaker middleware (Bloque 3 -- Resiliencia).

Opt-in only, same registration path as any other `Middleware` -- a
`ToToolManager`/`Service` built without it behaves identically to
before this module existed.

Unlike `TimeoutMiddleware`/`RetryMiddleware` (stateless per call), a
circuit breaker is inherently stateful across calls -- it has to
remember how many recent calls failed and when it last tripped. That
state lives on the `CircuitBreakerMiddleware` INSTANCE, so:

- One instance shared across a `Service`'s calls (the normal case,
  passing the same instance to `middlewares=[...]`) tracks failures for
  that service as a whole -- the intended, standard circuit-breaker
  usage.
- A fresh instance per call (e.g. constructed inside a per-request
  factory) would never accumulate failures and never trip -- not a bug,
  just not how a circuit breaker is meant to be wired. Register it the
  same way `Service.singleton=True` classes are meant to be shared: at
  the granularity the failures should be counted at.

Thread-safety mirrors `Service.get_instance()`'s own approach
(`core/service.py`): a plain `threading.Lock` around the (very short,
no I/O) state-transition arithmetic, rather than an `asyncio.Lock` --
so this behaves correctly whether the middleware instance is shared
across concurrent async tasks on one event loop, or across multiple
threads each potentially running their own event loop, matching the
same multi-tenant-safety bar already established elsewhere in this
project (see `tests/security/test_multi_tenant_isolation.py`).
"""
from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Callable

from to_tool_manager.core.types import ToolError, ToolResponse
from to_tool_manager.security.middleware import Middleware


class CircuitState(Enum):
    CLOSED = "closed"
    """Normal operation: every call passes through."""

    OPEN = "open"
    """Tripped: calls are rejected immediately, without reaching
    whatever this middleware wraps, until `reset_timeout` elapses."""

    HALF_OPEN = "half_open"
    """Probing: exactly one call is let through to test recovery. Its
    outcome decides whether the circuit goes back to CLOSED (success)
    or OPEN (failure)."""


class CircuitBreakerMiddleware(Middleware):
    """Trips after `failure_threshold` consecutive failures, rejecting
    further calls for `reset_timeout` seconds before probing recovery
    with a single call.

    A "failure" is either a raised exception or a `ToolResponse` with
    `ok=False` -- broader than `RetryMiddleware`'s `retryable`-only
    definition, since a circuit breaker's job is protecting a
    struggling downstream dependency from further load regardless of
    whether any individual failure looked retryable.

    Args:
        failure_threshold: Consecutive failures (CLOSED state) needed
            to trip to OPEN. Must be >= 1.
        reset_timeout: Seconds to stay OPEN before allowing one probe
            call through (HALF_OPEN). Must be positive.

    Example::

        breaker = CircuitBreakerMiddleware(failure_threshold=5, reset_timeout=30.0)
        service = Service(name="Orders", service=OrderService, middlewares=[breaker])
    """

    __slots__ = (
        "__failure_threshold",
        "__reset_timeout",
        "__lock",
        "__state",
        "__consecutive_failures",
        "__opened_at",
        "__clock",
    )

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        _clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        if failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {failure_threshold!r}")
        if reset_timeout <= 0:
            raise ValueError(f"reset_timeout must be positive, got {reset_timeout!r}")
        self.__failure_threshold = failure_threshold
        self.__reset_timeout = reset_timeout
        self.__lock = threading.Lock()
        self.__state = CircuitState.CLOSED
        self.__consecutive_failures = 0
        self.__opened_at: float | None = None
        self.__clock = _clock  # injectable for tests, so real time.sleep isn't needed to verify transitions

    @property
    def state(self) -> CircuitState:
        with self.__lock:
            return self.__resolve_state_locked()

    def __resolve_state_locked(self) -> CircuitState:
        """Must be called with `__lock` held. Lazily transitions
        OPEN -> HALF_OPEN once `reset_timeout` has elapsed -- there's no
        background timer; the transition is just evaluated on next
        access/call."""
        if self.__state is CircuitState.OPEN:
            assert self.__opened_at is not None
            if self.__clock() - self.__opened_at >= self.__reset_timeout:
                self.__state = CircuitState.HALF_OPEN
        return self.__state

    def __record_success_locked(self) -> None:
        self.__state = CircuitState.CLOSED
        self.__consecutive_failures = 0
        self.__opened_at = None

    def __record_failure_locked(self) -> None:
        self.__consecutive_failures += 1
        if self.__state is CircuitState.HALF_OPEN or self.__consecutive_failures >= self.__failure_threshold:
            self.__state = CircuitState.OPEN
            self.__opened_at = self.__clock()

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        with self.__lock:
            current_state = self.__resolve_state_locked()
            if current_state is CircuitState.OPEN:
                return ToolResponse(
                    error=ToolError(
                        category=frozenset({"circuit_open"}),
                        message=(
                            f"Circuit breaker is open after {self.__consecutive_failures} "
                            "consecutive failures; rejecting calls until it resets."
                        ),
                        exception_type="CircuitBreakerOpenError",
                        retryable=True,
                    )
                )

        try:
            response = await func(*args, **kw)
        except Exception:
            with self.__lock:
                self.__record_failure_locked()
            raise

        with self.__lock:
            if isinstance(response, ToolResponse) and not response.ok:
                self.__record_failure_locked()
            else:
                self.__record_success_locked()
        return response
