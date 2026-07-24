"""
Adapter for hand-rolled function-calling loops (OpenAI/Anthropic-style
"tools" arrays with no agent framework at all). No external dependency —
this always works as long as `to_tool_manager` core does.
"""
from __future__ import annotations

import typing
from typing import Any, Sequence

from to_tool_manager.core.types import ToolError, ToolResponse, ToolSpec

_PY_TO_JSON_TYPE = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def _json_type_for(annotation: Any) -> dict[str, Any]:
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is list:
        item_schema = _json_type_for(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}
    if origin is dict:
        return {"type": "object"}
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _json_type_for(non_none[0])
        return {"anyOf": [_json_type_for(a) for a in non_none]}
    if annotation in _PY_TO_JSON_TYPE:
        return {"type": _PY_TO_JSON_TYPE[annotation]}
    return {"type": "string"}  # safe fallback for unrecognized/custom types


def to_openai_tool_schemas(specs: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """OpenAI/Anthropic-style `tools=[...]` definitions (JSON Schema)."""
    tools = []
    for spec in specs:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in spec.parameters:
            schema = _json_type_for(p.annotation)
            if p.description:
                schema["description"] = p.description
            properties[p.name] = schema
            if p.required:
                required.append(p.name)

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return tools


async def dispatch(name: str, arguments: dict[str, Any], specs: Sequence[ToolSpec]) -> ToolResponse:
    """Looks up `name` among `specs` and executes it with `arguments`."""
    for spec in specs:
        if spec.name == name:
            return await spec.call(**arguments)
    return ToolResponse(
        error=ToolError(
            category=frozenset("unknown_tool"),
            message=f"No tool named '{name}' is registered.",
            exception_type="LookupError",
            retryable=False,
        )
    )
