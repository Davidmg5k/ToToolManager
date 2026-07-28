"""
Turns a bound method into a safe async callable that always returns a
ToolResponse instead of raising â€” so an agent loop (of any framework)
never crashes on a domain error.

Error classification is explicit and configurable via `ErrorMap`
(composable builder) or a legacy dict-style `error_map`:

1. `ErrorMap` (preferred): typed, composable builder with type-based
   and predicate-based rules. Supports `map()`, `map_entry()`,
   `map_callable()`, and `when()` for flexible classification.

2. Legacy dict `error_map`: same behavior as before, kept for
   backward compatibility. A raw dict is auto-converted to `ErrorMap`
   internally.

The core does NOT define domain-specific categories. If the caller
doesn't map an exception, it falls through to ``"unclassified"`` with
``handled=False`` â€” the LLM must report but NOT act.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping, Sequence

from to_tool_manager.core.coercion import CoercionError, coerce_kwargs
from to_tool_manager.core.types import (
    ErrorClassification,
    ErrorEntry,
    ErrorMap,
    ToolError,
    ToolResponse,
    _normalize_category,
)

FALLBACK_CATEGORY = "unclassified"

ErrorRule = Callable[[Exception], "tuple[str, bool] | None"]


def _resolve(value: Any, exc: Exception) -> tuple[frozenset[str], bool]:
    """Normalizes an error_map value (str, tuple, or callable) into
    (category as frozenset, retryable), calling it with the exception
    instance if it's a callable classifier."""
    if callable(value) and not isinstance(value, tuple):
        value = value(exc)
    if isinstance(value, tuple):
        return _normalize_category(value[0]), value[1]
    return _normalize_category(value), False  # bare category string -> not retryable


def _to_error_map(error_map: Mapping[type[BaseException], Any] | ErrorMap | None) -> ErrorMap:
    """Coerces any error_map variant into an ErrorMap instance."""
    if isinstance(error_map, ErrorMap):
        return error_map
    if isinstance(error_map, Mapping):
        return ErrorMap.from_dict(error_map)
    return ErrorMap()


def _classify(
    exc: Exception,
    error_map: Mapping[type[BaseException], Any] | ErrorMap,
    error_rules: Sequence[ErrorRule] = (),
) -> tuple[frozenset[str], bool, bool]:
    """
    Classify an exception into (category, retryable, handled).

    Resolution order:
    1. `error_rules` predicates (custom logic) â€” first non-None wins.
    2. `ErrorMap` type-based + predicate rules (via MRO walk).
    3. Fallback: ``"unclassified"``, non-retryable, ``handled=False``.

    The core does NOT provide built-in exception-to-category mappings.
    The caller defines all categories via ``error_map``.
    """
    # 1. Predicate rules
    for rule in error_rules:
        result = rule(exc)
        if result is not None:
            return _normalize_category(result[0]), result[1], True

    em = _to_error_map(error_map)

    # 2. ErrorMap (type-based + predicates)
    result = em.classify(exc)
    if result is not None:
        return result

    # 3. Fallback â€” unanticipated error
    return frozenset({FALLBACK_CATEGORY}), False, False


def make_safe_caller(
    func: Callable[..., Any],
    *,
    error_map: Mapping[type[BaseException], Any] | ErrorMap | None = None,
    error_rules: Sequence[ErrorRule] = (),
    sanitize_system_errors: bool = True,
) -> Callable[..., "Any"]:
    """
    Wraps `func` (sync or async, bound method) so calling it always
    returns a ToolResponse, never raises for domain-level exceptions.

    Programming errors that indicate a bug in the tool wiring itself
    (e.g. TypeError from a wrong argument name mismatch at the Python
    call boundary) are still caught and reported as unclassified rather
    than propagating, per the "AI should never get stuck" requirement --
    but they are NOT retried automatically since a bad call rarely fixes
    itself without different arguments (retryable flag reflects this).
    """
    em = _to_error_map(error_map)
    is_coroutine = inspect.iscoroutinefunction(func)

    async def caller(**kwargs) -> ToolResponse:
        try:
            kwargs = coerce_kwargs(func, kwargs)
        except CoercionError as exc:
            # Structurally unrecoverable coercion failure (e.g. a nested
            # object is missing a required field) -- reported as a
            # retryable validation error rather than falling through to
            # the generic/unclassified path below, so the LLM gets a
            # specific, actionable message about which argument is wrong.
            return ToolResponse(
                error=ToolError(
                    category=frozenset({"validation_error"}),
                    message=str(exc),
                    exception_type="CoercionError",
                    retryable=True,
                    handled=True,
                )
            )
        try:
            result = await func(**kwargs) if is_coroutine else func(**kwargs)
            return ToolResponse(content=result)
        except Exception as exc:  # noqa: BLE001 - intentional broad catch at the boundary
            category, retryable, handled = _classify(exc, em, error_rules)
            return ToolResponse(
                error=ToolError.from_exception(
                    exc,
                    category=category,
                    retryable=retryable,
                    handled=handled,
                )
            )

    return caller