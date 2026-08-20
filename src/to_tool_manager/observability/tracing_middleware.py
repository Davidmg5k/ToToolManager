"""Distributed tracing middleware (Bloque 2 -- Observabilidad).

Opt-in only, same registration path as any other `Middleware` -- a
`ToToolManager`/`Service` built without it behaves identically to
before this module existed.

`opentelemetry` is NOT a direct dependency of this project (same
reasoning as `fastmcp`/`ag_ui`, see hallazgo 1.3): importing it is
deferred to `TracingMiddleware.__init__` itself, not to this module's
top level, so `import to_tool_manager.observability` (and the
top-level `import to_tool_manager`, which imports this class eagerly)
never requires `opentelemetry` to be installed -- only actually
CONSTRUCTING a `TracingMiddleware` does. Constructing one without
`opentelemetry` installed raises the same kind of friendly,
actionable `ImportError` the fastmcp adapter already uses.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from to_tool_manager.core.types import ToolResponse
from to_tool_manager.security.middleware import Middleware

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer


class TracingMiddleware(Middleware):
    """Wraps each dispatch_call batch in an OpenTelemetry span.

    Args:
        tracer: An existing OpenTelemetry `Tracer` (e.g. from your own
            `TracerProvider` setup). If omitted, uses
            `opentelemetry.trace.get_tracer("to_tool_manager")`, which
            works against whatever global `TracerProvider` your
            application has configured (or a no-op tracer if none was
            configured -- OpenTelemetry's own default, not something
            this middleware adds).
        service_name: Optional label attached to the span as the
            `to_tool_manager.service` attribute.
        span_name: Span name. Defaults to `"to_tool_manager.dispatch"`.

    Requires the `opentelemetry-api` package (not a dependency of this
    project -- install it yourself, e.g. `pip install opentelemetry-api`,
    or pull it in transitively via a package like
    `pydantic-ai-harness`/`logfire` that already depends on it).

    Example::

        service = Service(
            name="Orders",
            service=OrderService,
            middlewares=[TracingMiddleware(service_name="Orders")],
        )
    """

    __slots__ = ("__tracer", "__base_attributes", "__span_name")

    def __init__(
        self,
        tracer: "Tracer | None" = None,
        service_name: str | None = None,
        span_name: str = "to_tool_manager.dispatch",
    ) -> None:
        super().__init__()
        if tracer is not None:
            self.__tracer = tracer
        else:
            try:
                from opentelemetry import trace  # pyright: ignore[reportMissingImports]
            except ImportError as exc:
                raise ImportError(
                    "TracingMiddleware requires the 'opentelemetry-api' package. "
                    "Install it with:\n"
                    "    pip install opentelemetry-api\n"
                    "The core `to_tool_manager` package does not depend on it. "
                    "Alternatively, pass an existing Tracer via `tracer=...`."
                ) from exc
            self.__tracer = trace.get_tracer("to_tool_manager")
        self.__base_attributes: dict[str, str] = {"to_tool_manager.service": service_name} if service_name else {}
        self.__span_name = span_name

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        operations = kw.get("operations")
        op_count = len(operations) if isinstance(operations, list) else None

        with self.__tracer.start_as_current_span(self.__span_name) as span:
            for key, value in self.__base_attributes.items():
                span.set_attribute(key, value)
            if op_count is not None:
                span.set_attribute("to_tool_manager.operation_count", op_count)

            try:
                response = await func(*args, **kw)
            except Exception:
                # start_as_current_span() already records the exception
                # and sets the span status to ERROR when it propagates
                # out of this block -- no need to call
                # span.record_exception() ourselves too.
                span.set_attribute("to_tool_manager.outcome", "exception")
                raise

            outcome = "success" if isinstance(response, ToolResponse) and response.ok else "error"
            span.set_attribute("to_tool_manager.outcome", outcome)
            return response
