"""
Framework-agnostic data contracts.

Nothing in this module (or anywhere under `core/`) imports pydantic-ai,
fastmcp, langchain, or any other agent framework. This is the "currency"
that every adapter consumes and produces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping

if TYPE_CHECKING:
    from collections.abc import Sequence

# Sentinel used when a parameter has no default value.
_MISSING = object()


def _normalize_category(cat: str | Sequence[str] | None) -> frozenset[str]:
    """Normalizes a category value into a frozenset for internal use.

    Accepts:
    - ``None`` → empty frozenset (no category)
    - ``"not_found"`` → ``frozenset({"not_found"})``
    - ``["not_found", "missing"]`` → ``frozenset({"not_found", "missing"})``
    """
    if cat is None:
        return frozenset()
    if isinstance(cat, str):
        return frozenset({cat})
    return frozenset(cat)


@dataclass(frozen=True, slots=True)
class ErrorClassification:
    """
    Explicit result of classifying a caught exception, for `error_map` /
    `error_rules` in `Service`. Preferred over the loose `str` /
    `(str, bool)` shortcuts when you want IDE/type-checker support or
    need to override the message shown to the LLM instead of using
    `str(exc)` verbatim (e.g. to avoid leaking internal wording, or to
    phrase it in a way that's more actionable for the model).

    `error_map`/`error_rules` still accept a bare `str` (category only)
    or a `(str, bool)` tuple as shortcuts — both are normalized to this
    internally. Use `ErrorClassification` directly when you want the
    `message` override or just prefer the explicit, documented type.
    """

    category: str | Sequence[str] | None = None
    retryable: bool = False
    message: str | None = None
    """If set, replaces the exception's own str() as the message shown
    to the LLM. Leave None to use str(exc) as before."""


@dataclass(frozen=True, slots=True)
class ErrorEntry:
    """Typed classification rule for a specific exception type.

    Use with `ErrorMap.map()` or `ErrorMap.map_entry()` to define how
    an exception should be classified when caught by the tool executor.

    ``category`` is stored as ``frozenset[str]`` internally for
    efficient matching. The API accepts ``str | Sequence[str] | None``
    and normalizes automatically.
    """

    category: frozenset[str]
    retryable: bool = False
    message: str | None = None
    """If set, replaces str(exc) as the message shown to the LLM.
    Leave None to use the exception's own message."""

    def __post_init__(self) -> None:
        if not isinstance(self.category, frozenset):
            object.__setattr__(self, "category", _normalize_category(self.category))


# Type accepted as a value in the legacy dict-style error_map.
_ErrorMapValue = str | tuple[str, bool] | ErrorClassification | ErrorEntry | Callable[..., Any]


class ErrorMap:
    """Typed, composable builder for exception classification.

    Replaces the raw `dict[type, Any]` that `Service.error_map` used to
    accept. Supports two matching strategies:

    1. **Type-based** (`map` / `map_entry` / `map_callable`): matches by
       exception type, walking the MRO so subclasses inherit a parent mapping.
    2. **Predicate-based** (`when`): matches by arbitrary condition, checked
       BEFORE type-based rules.

    Example::

        error_map = (
            ErrorMap()
            .map(OrderNotFoundError, category="not_found")
            .map(OrderAlreadyExistsError, category="already_exists", retryable=False)
            .map_callable(HTTPError, lambda e: ("not_found", False) if e.status_code == 404 else None)
            .when(lambda e: hasattr(e, 'timeout'), category="timeout", retryable=True)
        )
    """

    __slots__ = ("_type_map", "_predicates")

    def __init__(self) -> None:
        self._type_map: dict[type[BaseException], ErrorEntry | Callable[..., Any]] = {}
        self._predicates: list[tuple[Callable[[Exception], bool], str, bool, str | None]] = []

    def map(
        self,
        exc_type: type[BaseException],
        /,
        category: str | Sequence[str] | None = None,
        *,
        retryable: bool = False,
        message: str | None = None,
    ) -> ErrorMap:
        """Register a type-based classification rule.

        ``category`` accepts a string, a sequence of strings, or None.
        It is normalized to ``frozenset[str]`` internally.
        """
        self._type_map[exc_type] = ErrorEntry(
            category=_normalize_category(category), retryable=retryable, message=message
        )
        return self

    def map_entry(self, exc_type: type[BaseException], /, entry: ErrorEntry) -> ErrorMap:
        """Register a type-based rule from an explicit ErrorEntry."""
        self._type_map[exc_type] = entry
        return self

    def map_callable(
        self,
        exc_type: type[BaseException],
        /,
        classifier: Callable[[Exception], str | tuple[str, bool] | ErrorEntry | None],
    ) -> ErrorMap:
        """Register a callable classifier for an exception type.

        The callable receives the exception instance and should return:
        - ``("category", retryable)`` tuple
        - an ``ErrorEntry``
        - a bare ``"category"`` string
        - ``None`` to skip (fall through to next rule)
        """
        self._type_map[exc_type] = classifier
        return self

    def when(
        self,
        predicate: Callable[[Exception], bool],
        /,
        category: str | Sequence[str] | None = None,
        *,
        retryable: bool = False,
        message: str | None = None,
    ) -> ErrorMap:
        """Register a predicate-based rule (checked BEFORE type-based).

        ``category`` accepts a string, a sequence of strings, or None.
        It is normalized to ``frozenset[str]`` internally.
        """
        self._predicates.append((predicate, _normalize_category(category), retryable, message))
        return self

    def classify(self, exc: Exception) -> tuple[frozenset[str], bool, bool] | None:
        """Classify an exception.

        Returns ``(category, retryable, handled)`` or ``None`` if no rule matched.
        ``category`` is always a ``frozenset[str]`` (empty if no category was set).
        ``handled`` is always ``True`` when a rule matched — it signals that the
        programmer explicitly anticipated this error.
        """
        # 1. Predicate rules (checked first)
        for pred, cat, retry, _msg in self._predicates:
            if pred(exc):
                return cat, retry, True

        # 2. Type-based MRO walk
        for exc_type in type(exc).__mro__:
            entry = self._type_map.get(exc_type)
            if entry is None:
                continue
            if callable(entry) and not isinstance(entry, ErrorEntry):
                result = entry(exc)
                if result is None:
                    continue
                if isinstance(result, ErrorEntry):
                    return result.category, result.retryable, True
                if isinstance(result, tuple):
                    return _normalize_category(result[0]), result[1], True
                # Bare category string
                return _normalize_category(result), False, True
            # ErrorEntry instance
            return entry.category, entry.retryable, True

        return None

    @classmethod
    def from_dict(cls, mapping: Mapping[type[BaseException], Any]) -> ErrorMap:
        """Create an ErrorMap from the legacy dict-style error_map.

        Accepts the same values that ``Service.error_map`` used to accept:
        bare strings, ``(category, retryable)`` tuples, callables, or
        ``ErrorEntry``/``ErrorClassification`` instances.
        """
        instance = cls()
        for exc_type, value in mapping.items():
            if isinstance(value, ErrorEntry):
                instance._type_map[exc_type] = value
            elif isinstance(value, ErrorClassification):
                instance._type_map[exc_type] = ErrorEntry(
                    category=_normalize_category(value.category),
                    retryable=value.retryable,
                    message=value.message,
                )
            elif callable(value) and not isinstance(value, tuple):
                instance._type_map[exc_type] = value
            elif isinstance(value, tuple):
                instance._type_map[exc_type] = ErrorEntry(
                    category=_normalize_category(value[0]),
                    retryable=value[1] if len(value) > 1 else False,
                )
            elif isinstance(value, str):
                instance._type_map[exc_type] = ErrorEntry(category=_normalize_category(value))
        return instance

    def __bool__(self) -> bool:
        return bool(self._type_map or self._predicates)


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """Describes a single parameter of a discovered method."""

    name: str
    annotation: Any
    required: bool
    default: Any = _MISSING
    description: str | None = None

    @property
    def has_default(self) -> bool:
        return self.default is not _MISSING


@dataclass(frozen=True, slots=True)
class ToolError:
    """Structured, framework-agnostic representation of a failed call.

    ``category`` is a ``frozenset[str]`` — empty if no category was
    assigned, or one or more category strings. The API accepts
    ``str | Sequence[str] | None`` and normalizes automatically.

    ``handled`` indicates whether the programmer explicitly anticipated
    this error via ``error_map`` / ``error_rules``:

    - ``True`` — the error was mapped; the LLM may retry or act on it.
    - ``False`` — unanticipated error; the LLM must report but NOT act.
    """

    category: frozenset[str]
    message: str
    exception_type: str
    retryable: bool = False
    handled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.category, frozenset):
            object.__setattr__(self, "category", _normalize_category(self.category))

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        category: str | Sequence[str] | None = None,
        retryable: bool = False,
        handled: bool = True,
        message: str | None = None,
    ) -> ToolError:
        """Build a ToolError directly from a caught exception.

        Extracts ``exception_type`` from the exception automatically.

        ``category`` accepts a string, a sequence of strings, or None.
        It is normalized to ``frozenset[str]`` internally.

        When ``handled=False``, the message is sanitized by default
        (the raw ``str(exc)`` is hidden from the LLM to avoid leaking
        internals). Pass an explicit ``message`` to override this.
        """
        if not handled and message is None:
            exc_name = type(exc).__name__
            display_message = (
                f"An unexpected error occurred ({exc_name}). "
                "Report this to the user but do NOT attempt to fix, "
                "retry, or take any action."
            )
        else:
            display_message = message or str(exc)

        return cls(
            category=_normalize_category(category),
            message=display_message,
            exception_type=type(exc).__name__,
            retryable=retryable,
            handled=handled,
        )


@dataclass(frozen=True, slots=True)
class ToolResponse:
    """Result of executing a tool call."""

    content: Any = None
    error: ToolError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """
    Describes one callable operation (a method or exposed property) that
    lives inside a service-level tool. Purely descriptive — used to
    generate the tool's documentation and to validate/route calls.
    """

    name: str
    description: str
    parameters: tuple[ParamSpec, ...]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """
    ONE tool per Service — this is the core design: a whole service
    becomes a single tool, not one tool per method. The tool accepts a
    list of `{"method": ..., "args": {...}}` operations and executes
    all of them in a single call, so an LLM can e.g. create a user AND
    list all users in ONE tool call instead of two.

    `call` is always an async callable — `call(operations=[...])` —
    that never raises; failures for individual operations are reported
    per-item in the returned ToolResponse.content, so one bad operation
    doesn't block the rest of the batch.
    """

    name: str
    description: str
    parameters: tuple[ParamSpec, ...]
    call: Callable[..., Awaitable[ToolResponse]]
    operations: tuple[OperationSpec, ...] = ()
    class_description: str | None = None
    service_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)