"""
Shared formatting functions for tool descriptions.

Single source of truth for parameter formatting used across
manager.py and module.py. Prevents drift between the two
dispatch paths.
"""
from __future__ import annotations

import typing
from typing import Any

from to_tool_manager.core.types import ParamSpec, _is_complex_type, _complex_type_field_names, _type_display_name


def format_param(p: ParamSpec) -> str:
    """Format a parameter for display in tool descriptions.

    For complex types (dataclasses, Pydantic models, etc.), shows the
    expected JSON args structure so the LLM knows to wrap fields under
    the parameter name:

    - ``data: {"field1": type, "field2": type}`` (required complex)
    - ``data?: {"field1": type, "field2": type}`` (optional complex)

    For primitives:

    - ``name: str`` (required)
    - ``name?: str`` (optional)
    """
    marker = "" if p.required else "?"
    if _is_complex_type(p.annotation):
        field_str = _json_args_shape(p.annotation)
        if field_str:
            return f"{p.name}{marker}: {field_str}"
        return f"{p.name}{marker}: {_type_display_name(p.annotation)}"
    type_name = getattr(p.annotation, "__name__", str(p.annotation))
    if p.required:
        return f"{p.name}: {type_name}"
    return f"{p.name}?"


def _json_args_shape(annotation: Any) -> str:
    """Returns a JSON-like args shape for complex types, e.g.
    ``{"user_name": str, "email": str}``.

    Returns empty string for types that don't have inspectable fields
    (generic containers like ``list[str]``, opaque classes, etc.).
    """
    field_names = _complex_type_field_names(annotation)
    if not field_names:
        return ""

    try:
        hints = typing.get_type_hints(annotation)
    except Exception:
        hints = {}

    parts = []
    for name in field_names:
        field_type = hints.get(name)
        type_str = getattr(field_type, "__name__", str(field_type)) if field_type is not None else "Any"
        parts.append(f'"{name}": {type_str}')
    return "{" + ", ".join(parts) + "}"
