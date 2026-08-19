"""Structured logging middleware (Bloque 2 -- Observabilidad).

Opt-in only: nothing in this module changes behavior unless a
`LoggingMiddleware` instance is explicitly registered, either globally
(`ToToolManager(services, middlewares=[LoggingMiddleware()])`) or per
service (`Service(..., middlewares=[LoggingMiddleware()])`), following
the exact same registration path as any other `Middleware`. A
`ToToolManager`/`Service` built without it behaves identically to
before this module existed.

Design choices, and why:

- Uses the stdlib `logging` module rather than introducing a new
  dependency (e.g. `structlog`) or inventing a bespoke log format. Any
  downstream log aggregator (JSON formatter, cloud logging handler,
  OpenTelemetry log bridge) can consume stdlib `LogRecord`s with
  `extra=` fields without this project committing to one specific
  logging stack.
- Fields are namespaced under `to_tool_manager.*` in `extra=` to avoid
  colliding with fields a consumer's own logging setup might already
  use (`service`, `duration_ms`, etc. are common names).
- Logs once per `dispatch_call` batch (one call to a Service's
  operations, which may itself contain several `{"method", "args"}`
  entries) -- not once per individual operation inside that batch --
  matching the granularity at which `Middleware.dispatch()` actually
  intercepts calls. Per-operation success/failure counts are still
  extracted from the batch result and included as fields.
- Never swallows exceptions: an exception from `func(...)` is logged at
  ERROR (with `exc_info`) and re-raised unchanged, matching the
  `Middleware` contract documented on the base class ("Middlewares are
  expected to raise exceptions for intentional blocking... propagate to
  the adapter/framework as-is").
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from to_tool_manager.core.types import ToolResponse
from to_tool_manager.security.middleware import Middleware

_default_logger = logging.getLogger("to_tool_manager.dispatch")


def _count_outcomes(response: ToolResponse) -> tuple[int, int]:
    """Returns (success_count, failure_count) for a dispatch_call result.

    Handles both shapes `ToolResponse` can take: a structural failure
    (`response.error` set, e.g. malformed `operations`) counts as a
    single failure; a normal batch result counts each per-operation
    entry in `response.content` by its own `"success"` key.
    """
    if not response.ok:
        return (0, 1)
    if isinstance(response.content, list):
        successes = sum(1 for entry in response.content if isinstance(entry, dict) and entry.get("success"))
        return (successes, len(response.content) - successes)
    return (1, 0)


class LoggingMiddleware(Middleware):
    """Logs one structured record per dispatch_call batch.

    Args:
        logger: Logger to use. Defaults to the module logger
            ``"to_tool_manager.dispatch"`` -- configure it (handlers,
            level, formatter) like any other stdlib logger from the
            consuming application; this middleware never calls
            `logging.basicConfig()` or otherwise mutates global logging
            state.
        level: Log level for successful batches (batches with at least
            one per-operation failure log at `logging.WARNING`
            regardless of this setting, so failures aren't silently
            downgraded to INFO/DEBUG). Defaults to `logging.INFO`.

    Example::

        service = Service(
            name="Orders",
            service=OrderService,
            middlewares=[LoggingMiddleware()],
        )
    """

    __slots__ = ("__logger", "__level")

    def __init__(self, logger: logging.Logger | None = None, level: int = logging.INFO) -> None:
        super().__init__()
        self.__logger = logger if logger is not None else _default_logger
        self.__level = level

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        operations = kw.get("operations")
        op_count = len(operations) if isinstance(operations, list) else None
        start = time.perf_counter()

        try:
            response = await func(*args, **kw)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self.__logger.error(
                "tool_dispatch_failed",
                extra={
                    "to_tool_manager.operation_count": op_count,
                    "to_tool_manager.duration_ms": round(duration_ms, 2),
                    "to_tool_manager.exception_type": type(exc).__name__,
                },
                exc_info=exc,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        success_count, failure_count = _count_outcomes(response)
        level = self.__level if failure_count == 0 else max(self.__level, logging.WARNING)
        self.__logger.log(
            level,
            "tool_dispatch_completed",
            extra={
                "to_tool_manager.operation_count": op_count,
                "to_tool_manager.success_count": success_count,
                "to_tool_manager.failure_count": failure_count,
                "to_tool_manager.duration_ms": round(duration_ms, 2),
            },
        )
        return response
