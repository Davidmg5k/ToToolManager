"""
Framework-agnostic argument coercion.

Turns raw values -- as received from an LLM tool call, i.e. JSON-decoded
dicts/lists/strings -- into the types a callable's signature expects.

Design note (why this exists as its own module): this is the one part of
`to_tool_manager` that has to reason about "any type the user's service
methods might declare", so it's kept isolated from `executor.py` (which
only cares about turning calls into safe `ToolResponse`s) and isolated
from `discovery.py` (which only introspects signatures, never resolves
values against them).

Strategy, in order:

1. `pydantic.TypeAdapter(annotation).validate_python(value)` -- the same
   mechanism FastAPI uses internally to coerce/validate path, query and
   body parameters. This already knows how to handle: primitives,
   `Optional`/`Union`, `Literal`, `Enum`, `datetime`/`date`/`UUID`/
   `Decimal`/`Path`, generic collections (`list[X]`, `dict[K, V]`,
   `tuple[...]`, `set[X]`, arbitrarily nested), dataclasses, `TypedDict`,
   `NamedTuple`, and any pydantic `BaseModel` -- all without us
   hand-rolling a branch per type. TypeAdapters are cached per-annotation
   (building one walks the whole type graph and is too slow to redo on
   every tool call). `arbitrary_types_allowed=True` is set so a type
   TypeAdapter doesn't otherwise understand is treated as opaque
   (isinstance-checked) instead of raising at *adapter construction*
   time -- it still won't be *constructed* from a dict this way, which
   is where step 2 comes in.

2. Plain-class + dict fallback. TypeAdapter's arbitrary-types mode does
   NOT construct arbitrary classes from a dict -- and neither does
   FastAPI: a plain `class Foo:` (no `BaseModel`, no `@dataclass`) is
   simply not a supported body-param type in FastAPI. Since
   `to_tool_manager` is explicitly meant to wrap plain, undecorated
   service classes, this is the one gap worth closing ourselves:
   `cls(**value)`, resolved recursively through this same module so
   nested plain classes inside a plain class also get coerced.

3. Passthrough. If nothing applies, the raw value is returned unchanged
   and the underlying call is left to raise its own, more specific
   `TypeError` -- `executor.make_safe_caller` turns that into a
   structured `ToolResponse` instead of crashing the process.

Failures inside step 2 that are structurally unrecoverable (a required
nested field is simply missing) raise `CoercionError`, which
`executor.py` catches explicitly and reports as a retryable
`validation_error` -- specific enough that an LLM can fix its own next
call. Anything else is best-effort and silent, exactly like the
previous coercion pass this replaces.
"""
from __future__ import annotations

import inspect
from functools import lru_cache
from typing import Any, Callable, get_type_hints

try:
    from pydantic import ConfigDict, TypeAdapter
    from pydantic import ValidationError as _PydanticValidationError

    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - pydantic is a de-facto hard dependency
    _HAS_PYDANTIC = False
    _PydanticValidationError = ()  # type: ignore[assignment]

_ARBITRARY_CONFIG = (
    ConfigDict(arbitrary_types_allowed=True)  # type: ignore[reportPossiblyUnboundVariable]
    if _HAS_PYDANTIC
    else None
)


class CoercionError(Exception):
    """A value could not be coerced to its annotated type.

    Distinct from a bare `TypeError`/`ValidationError` so callers (see
    `executor.make_safe_caller`) can classify it explicitly as a
    `validation_error` instead of falling back to `unclassified`.
    """

    def __init__(self, annotation: Any, value: Any, reason: str) -> None:
        self.annotation = annotation
        self.value = value
        self.reason = reason
        type_name = getattr(annotation, "__name__", str(annotation))
        super().__init__(f"Could not build '{type_name}' from the given value: {reason}")


@lru_cache(maxsize=None)
def _adapter_for(annotation: Any) -> "TypeAdapter[Any] | None":
    """Builds (and caches) a TypeAdapter for `annotation`.

    Two-step construction: types that already carry their own pydantic
    config (a `BaseModel`, a dataclass, a `TypedDict`) reject an explicit
    `config=` argument outright (`PydanticUserError`), so we try with
    `arbitrary_types_allowed=True` first -- which is what lets a genuinely
    opaque/custom type be isinstance-checked instead of rejected outright
    -- and fall back to no config at all for the types that forbid it.

    Returns None only if neither attempt works (e.g. an unresolved
    forward reference) -- callers fall through to the plain-class
    fallback or passthrough in that case.
    """
    if not _HAS_PYDANTIC:
        return None
    try:
        return TypeAdapter(annotation, config=_ARBITRARY_CONFIG)  # type: ignore[reportPossiblyUnboundVariable]
    except Exception:
        pass
    try:
        return TypeAdapter(annotation)  # type: ignore[reportPossiblyUnboundVariable]
    except Exception:
        return None


def _is_plain_class(annotation: Any) -> bool:
    """True for an ordinary class that TypeAdapter would only ever
    isinstance-check (never construct from a dict): not a dataclass,
    not a NamedTuple, not something pydantic already builds from
    mappings on its own.
    """
    if not inspect.isclass(annotation):
        return False
    if hasattr(annotation, "__dataclass_fields__"):
        return False
    if hasattr(annotation, "_fields") and hasattr(annotation, "_field_defaults"):
        return False  # NamedTuple
    model_validate = getattr(annotation, "model_validate", None)
    if callable(model_validate):
        return False  # pydantic BaseModel (v2) -- TypeAdapter already handles it
    return True


def _build_plain_object(cls: type, data: dict[str, Any]) -> Any:
    """Constructs a plain (non-pydantic, non-dataclass) class from a dict,
    resolving each constructor argument recursively through `coerce_value`
    so nested plain classes are handled too.
    """
    try:
        sig = inspect.signature(cls)
    except (ValueError, TypeError) as exc:
        raise CoercionError(cls, data, f"no inspectable constructor: {exc}") from exc

    try:
        hints = get_type_hints(cls.__init__)
    except Exception:
        hints = {}

    kwargs: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name == "self" or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if name not in data:
            if param.default is inspect.Parameter.empty:
                raise CoercionError(cls, data, f"missing required field '{name}'")
            continue
        annotation = hints.get(name, param.annotation)
        kwargs[name] = coerce_value(annotation, data[name])

    try:
        return cls(**kwargs)
    except CoercionError:
        raise
    except Exception as exc:
        raise CoercionError(cls, data, str(exc)) from exc


def coerce_value(annotation: Any, value: Any) -> Any:
    """Best-effort, type-agnostic coercion of a single value to `annotation`.

    See module docstring for the full resolution order. Raises
    `CoercionError` only for the plain-class fallback path when a
    required nested field is genuinely missing or construction itself
    fails -- every other case degrades to passthrough.
    """
    if annotation is None or annotation is inspect.Parameter.empty:
        return value
    if value is None:
        return None

    plain_class_applies = _is_plain_class(annotation) and isinstance(value, dict)

    adapter = _adapter_for(annotation)
    if adapter is not None:
        try:
            return adapter.validate_python(value)
        except _PydanticValidationError as exc:
            if plain_class_applies:
                pass  # expected: TypeAdapter only isinstance-checks opaque types
            else:
                # A real structural mismatch against a type TypeAdapter DOES
                # know how to build (BaseModel, dataclass, TypedDict, Enum,
                # Union, ...) -- e.g. a missing required field. Reporting
                # this explicitly is what makes the failure mode consistent
                # between "plain class" and "known structured type", instead
                # of silently handing the raw value to the wrapped method.
                raise CoercionError(annotation, value, str(exc)) from exc
        except Exception:
            if not plain_class_applies:
                return value  # defensive: coercion must never itself crash a tool call

    if plain_class_applies:
        return _build_plain_object(annotation, value)

    return value


def coerce_kwargs(func: Callable[..., Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Coerces every argument in `kwargs` to match `func`'s resolved
    annotations (via `get_type_hints`, so forward references and
    `from __future__ import annotations` both work).

    Propagates `CoercionError` for the one case worth reporting back to
    the caller as an actionable validation error; every other coercion
    failure is swallowed and the original raw value is kept, so the
    underlying call still happens and can raise its own, more specific
    error if genuinely incompatible.
    """
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return kwargs

    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    for name, param in sig.parameters.items():
        if name == "self" or name not in kwargs:
            continue
        annotation = hints.get(name, param.annotation)
        if annotation is inspect.Parameter.empty:
            continue
        try:
            kwargs[name] = coerce_value(annotation, kwargs[name])
        except CoercionError:
            raise
        except Exception:
            pass  # best-effort; the call itself will surface real mismatches

    return kwargs
