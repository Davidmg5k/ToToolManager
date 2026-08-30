"""
Shared formatting functions for tool descriptions.

Single source of truth for parameter formatting used across
manager.py and module.py. Prevents drift between the two
dispatch paths.
"""
from __future__ import annotations

from to_tool_manager.core.types import ParamSpec, _is_complex_type, describe_complex_type

def format_param(p: ParamSpec) -> str:
    """Format a parameter for display in tool descriptions.

    Produces output like:
    - "name: str" for required primitive params
    - "data?: MyType?" for optional complex params
    - "data: MyType{field1, field2}" for required complex params
    """
    type_name = getattr(p.annotation, "__name__", str(p.annotation))
    marker = "" if p.required else "?"
    if _is_complex_type(p.annotation):
        return f"{p.name}{marker}: {describe_complex_type(p.annotation)}"
    if p.required:
        return f"{p.name}: {type_name}"
    return f"{p.name}?"
