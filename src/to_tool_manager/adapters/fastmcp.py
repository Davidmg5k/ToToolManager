"""
Adapter for FastMCP.

Only this module imports fastmcp. The core package never does.
"""
from __future__ import annotations

import json
from inspect import Parameter, Signature
from typing import TYPE_CHECKING, Any, Sequence

try:
    import fastmcp  # noqa: F401
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The fastmcp adapter requires the 'fastmcp' package. Install it with:\n"
        "    pip install fastmcp\n"
        "The core `to_tool_manager` package does not depend on it."
    ) from exc

from to_tool_manager.core.types import ToolSpec

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _serialize_content(content: Any) -> str:
    if isinstance(content, (list, dict)):
        return json.dumps(content, default=str)
    return str(content)


def _format_categories(cats: frozenset[str]) -> str:
    """Normalizes a category frozenset into a display string for the LLM."""
    if not cats:
        return ""
    if len(cats) == 1:
        return next(iter(cats))
    return ", ".join(sorted(cats))


def _build_callable(spec: ToolSpec):
    sig_params = [
        Parameter(
            p.name,
            Parameter.POSITIONAL_OR_KEYWORD,
            annotation=p.annotation,
            default=p.default if p.has_default else Parameter.empty,
        )
        for p in spec.parameters
    ]

    async def tool_func(**kwargs) -> str:
        response = await spec.call(**kwargs)
        error = response.error
        if error is None:
            return _serialize_content(response.content)
        # MCP has no built-in "please retry" signal like ModelRetry, so we
        # surface the category explicitly in the text — the calling model
        # decides whether/how to retry based on that.
        cats = _format_categories(error.category)
        if error.handled:
            prefix = f" ({cats})" if cats else ""
            return f"Error{prefix}: {error.message}"
        # Unanticipated error — explicit instruction to the MCP caller.
        prefix = f" ({cats})" if cats else ""
        return (
            f"Error{prefix}: {error.message}. "
            "Report this to the user but do NOT attempt to fix, retry, "
            "or take any action."
        )

    tool_func.__name__ = spec.name
    tool_func.__qualname__ = spec.name
    tool_func.__signature__ = Signature(sig_params)  # type: ignore[attr-defined]
    tool_func.__annotations__ = {p.name: p.annotation for p in spec.parameters}
    tool_func.__annotations__["return"] = str
    return tool_func


def register_on_mcp(mcp: "FastMCP", specs: Sequence[ToolSpec]) -> None:
    """Registers every ToolSpec as a tool on an existing FastMCP server."""
    for spec in specs:
        mcp.tool(
            _build_callable(spec),
            name=spec.name,
            description=spec.description,
        )


def build_mcp_server(name: str, specs: Sequence[ToolSpec]) -> "FastMCP":
    """Convenience: creates a new FastMCP server with all specs registered."""
    from fastmcp import FastMCP

    mcp = FastMCP(name)
    register_on_mcp(mcp, specs)
    return mcp