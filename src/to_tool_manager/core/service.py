"""
`Service` describes how a single plain-Python class should be exposed.
It holds configuration only — discovery and execution logic live in
discovery.py / executor.py so this stays a simple, inspectable dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from to_tool_manager.core.discovery import Visibility
from to_tool_manager.core.types import ErrorMap

if TYPE_CHECKING:
    from to_tool_manager.security.middleware import Middleware

ErrorRule = Callable[[Exception], "tuple[str, bool] | None"]


@dataclass
class Service:
    name: str
    service: type

    description: str = ""
    """Group-level description for this service (what an adapter can use
    as per-toolset instructions, e.g. pydantic-ai's FunctionToolset(instructions=...))."""

    visibility: frozenset[Visibility] = field(default_factory=lambda: frozenset({"public"}))
    """Which method-visibility buckets to expose. Special/dunder methods
    are ALWAYS excluded and cannot be opted into, regardless of this setting."""

    include: frozenset[str] | None = None
    """If set, ONLY these method names are exposed (bypasses `visibility`)."""

    exclude: frozenset[str] | None = None
    """Method names to exclude even if they'd otherwise be eligible."""

    expose_properties: bool = False
    """Expose read-only @property members as zero-argument operations."""

    error_map: ErrorMap | Mapping[type[BaseException], Any] = field(default_factory=ErrorMap)
    """Exception classification rules. Accepts either:

    - An ``ErrorMap`` instance (preferred) — typed, composable builder::

        ErrorMap()
            .map(OrderNotFoundError, category="not_found")
            .when(lambda e: e.retry_count > 3, category="rate_limited", retryable=True)

    - A legacy ``dict`` (backward compatible) — auto-converted to ``ErrorMap``::

        {OrderNotFoundError: ("not_found", False)}

    Matching walks the exception's MRO (subclasses match a parent
    mapping) and takes precedence over the library's built-in defaults.
    Unmapped errors are classified as ``unclassified`` with
    ``handled=False``, signaling the LLM must NOT act on them."""

    error_rules: Sequence[ErrorRule] = field(default_factory=tuple)
    """Ordered list of `(exc) -> (category, retryable) | None` predicates,
    checked BEFORE `error_map`. Use this when classification can't be
    expressed by exception type alone — e.g. one rule covering several
    unrelated exception types via shared logic, or matching on
    attributes without writing a dedicated subclass per case. The first
    rule that returns non-None wins."""

    sanitize_system_errors: bool = True
    """If True, unmapped/unexpected exceptions are reported to the tool
    caller with a generic message instead of the raw exception text,
    to avoid leaking internals. Full details should be logged separately
    by the host application."""

    singleton: bool = True
    """If True (default), one instance of `service` is created lazily and
    reused for all tool calls. Set False if the underlying class is not
    safe to share (e.g. holds per-request state) — a fresh instance will
    be created for the manager's lifetime is still just one instance;
    for true per-call isolation, instantiate the Service per request."""

    middlewares: Sequence[Middleware] = field(default_factory=tuple)
    """Middlewares applied at the method level for this service.

    ``ToolMiddleware`` instances here filter which methods are exposed
    via ``include`` / ``exclude``.  Other middleware types can also be
    placed here for service-scoped interception."""

    disable_middlewares: Sequence[str] = field(default_factory=tuple)
    """Names of global (ToToolManager-level) middlewares to disable
    for this specific service.  Only affects middlewares registered at
    the manager level; module- or service-level middlewares cannot be
    disabled this way."""

    args: tuple = ()
    kwargs: dict = field(default_factory=dict)

    _instance: Any = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.include and self.exclude:
            overlap = self.include & self.exclude
            if overlap:
                raise ValueError(
                    f"Service '{self.name}': names {sorted(overlap)} appear in "
                    "both `include` and `exclude`."
                )
        if not isinstance(self.service, type):
            raise TypeError(
                f"Service '{self.name}': `service` must be a class, got "
                f"{type(self.service).__name__}."
            )

    def get_instance(self) -> Any:
        if self._instance is None or not self.singleton:
            instance = self.service(*self.args, **self.kwargs)
            if self.singleton:
                self._instance = instance
            return instance
        return self._instance