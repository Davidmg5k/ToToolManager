"""Metrics middleware (Bloque 2 -- Observabilidad).

Opt-in only, same registration path as any other `Middleware` -- a
`ToToolManager`/`Service` built without it behaves identically to
before this module existed. See `metrics.py` for the pluggable
`MetricsCollector` interface and the scope note on what's measurable
at this layer (no LLM token usage -- that's an Agent-level concept).
"""
from __future__ import annotations

import time
from typing import Any, Callable, Mapping

from to_tool_manager.core.types import ToolResponse
from to_tool_manager.observability.metrics import MetricsCollector
from to_tool_manager.security.middleware import Middleware


class MetricsMiddleware(Middleware):
    """Records duration and success/failure counters for each
    dispatch_call batch, via a pluggable `MetricsCollector`.

    Args:
        collector: Where metrics get recorded. Any `MetricsCollector`
            implementation (see `metrics.py`); the middleware itself
            doesn't assume a specific backend.
        service_name: Optional label attached to every metric emitted
            by this middleware instance (`tags={"service": ...}`) --
            since one middleware instance is typically bound to one
            `Service`, this makes metrics distinguishable per service
            without the middleware needing to inspect dispatch
            internals to figure out which service it's wrapping.
        metric_prefix: Prefix for both the duration metric
            (`f"{prefix}.duration_seconds"`) and the counter
            (`f"{prefix}.calls_total"`). Defaults to
            `"to_tool_manager.dispatch"`.

    Example::

        collector = InMemoryMetricsCollector()
        service = Service(
            name="Orders",
            service=OrderService,
            middlewares=[MetricsMiddleware(collector, service_name="Orders")],
        )
    """

    __slots__ = ("__collector", "__base_tags", "__duration_metric", "__calls_metric")

    def __init__(
        self,
        collector: MetricsCollector,
        service_name: str | None = None,
        metric_prefix: str = "to_tool_manager.dispatch",
    ) -> None:
        super().__init__()
        self.__collector = collector
        self.__base_tags: dict[str, str] = {"service": service_name} if service_name is not None else {}
        self.__duration_metric = f"{metric_prefix}.duration_seconds"
        self.__calls_metric = f"{metric_prefix}.calls_total"

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        start = time.perf_counter()
        try:
            response = await func(*args, **kw)
        except Exception:
            duration = time.perf_counter() - start
            self.__collector.record_duration(self.__duration_metric, duration, self._tags("exception"))
            self.__collector.increment(self.__calls_metric, self._tags("exception"))
            raise

        duration = time.perf_counter() - start
        outcome = "success" if isinstance(response, ToolResponse) and response.ok else "error"
        self.__collector.record_duration(self.__duration_metric, duration, self._tags(outcome))
        self.__collector.increment(self.__calls_metric, self._tags(outcome))
        return response

    def _tags(self, outcome: str) -> Mapping[str, str]:
        return {**self.__base_tags, "outcome": outcome}
