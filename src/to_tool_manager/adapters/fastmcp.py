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

    from to_tool_manager.core.manager import ToToolManager
    from to_tool_manager.core.module import Module

# Canonical tool name a Module's ToolSpec is registered under on its own
# sub-server. Deliberately NOT `spec.name` (== module.name): after
# `mount(namespace=module.name)`, FastMCP prefixes the tool name with
# the namespace, so using `spec.name` here would produce a stuttering
# "OrderManagement_OrderManagement" instead of "OrderManagement_dispatch".
_MODULE_DISPATCH_TOOL_NAME = "dispatch"


def _serialize_content(content: Any) -> str:
    if isinstance(content, list) and content and isinstance(content[0], dict):
        headers = list(content[0].keys())
        lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in content:
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
        return "\n".join(lines)
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


# ---------------------------------------------------------------------------
# build_mcp_agent — Module-aware server (mirrors pydantic_ai.build_agent)
# ---------------------------------------------------------------------------


def _default_module_prompt_text(module: "Module") -> str:
    """Generic fallback prompt text for a Module with no explicit
    ``system_prompt``, built only from framework-agnostic Module data
    (mirrors the intent of `adapters.pydantic_ai._default_module_instructions`
    without importing pydantic-ai from this adapter).
    """
    from to_tool_manager.core.module import _build_services_overview

    header = (
        module.description.strip()
        if module.description and module.description.strip()
        else f"You are the '{module.name}' specialist agent."
    )
    return f"{header}\n\n{_build_services_overview(module.services)}"


def _register_module_prompt(sub_mcp: "FastMCP", module: "Module") -> None:
    """Exposes a Module's system prompt as an MCP Prompt on its own
    sub-server, named after the Module -- once mounted with
    ``namespace=module.name`` it's reachable as
    ``f"{module.name}_{module.name}"``, same namespacing rule FastMCP
    applies to every other object (tools, resources, templates).
    """
    prompt_text = module.system_prompt or _default_module_prompt_text(module)

    def _module_prompt() -> str:
        return prompt_text

    sub_mcp.prompt(
        _module_prompt,
        name=module.name,
        description=module.description or f"System prompt for the '{module.name}' module.",
    )


def _mount_module(mcp: "FastMCP", module: "Module", module_spec: ToolSpec, *, include_prompts: bool) -> None:
    """Builds an isolated sub-server for a single Module and mounts it
    on the parent under its own namespace (RF-2), optionally exposing
    its system prompt as an MCP Prompt (RF-3).
    """
    from fastmcp import FastMCP

    sub_mcp = FastMCP(module.name)
    sub_mcp.tool(
        _build_callable(module_spec),
        name=_MODULE_DISPATCH_TOOL_NAME,
        description=module_spec.description,
    )
    if include_prompts:
        _register_module_prompt(sub_mcp, module)

    mcp.mount(sub_mcp, namespace=module.name)


def build_mcp_agent(
    name: str,
    manager: "ToToolManager",
    *,
    include_prompts: bool = True,
) -> "FastMCP":
    """Create a FastMCP server wired to the manager's tools.

    Mirrors `adapters.pydantic_ai.build_agent`'s behavior for a
    framework that has no native "sub-agent" concept, using FastMCP's
    own isolation primitive instead:

    - Services -> flat tools on the parent server (RF-1), exactly like
      `build_mcp_server`.
    - Modules -> excluded from the parent and mounted as isolated
      sub-servers via `mount(namespace=module.name)` (RF-2), so their
      tools are namespaced (e.g. ``OrderManagement_dispatch``) instead
      of mixing into the parent's flat tool list.
    - Module system prompts -> registered as MCP Prompts on each
      sub-server when `include_prompts=True` (RF-3); if a Module has
      no explicit `system_prompt`, a generic one is generated from its
      description and services, same fallback used when a Module
      becomes a real pydantic-ai sub-agent.

    Does not modify `build_mcp_server`, `register_on_mcp`, or
    `_build_callable` -- this is a new, additive entry point (RF-5).

    Parameters
    ----------
    name:
        Name of the parent FastMCP server.
    manager:
        A ``ToToolManager`` instance providing ``tool_specs``,
        ``services`` and ``modules``.
    include_prompts:
        If ``True`` (default), each Module's system prompt is exposed
        as an MCP Prompt on its sub-server. If ``False``, only the
        Module's dispatch tool is mounted.
    """
    from fastmcp import FastMCP

    all_specs = manager.tool_specs
    service_specs = [s for s in all_specs if s.metadata.get("type") != "module"]
    module_specs_by_name = {s.service_name: s for s in all_specs if s.metadata.get("type") == "module"}

    mcp = FastMCP(name)
    register_on_mcp(mcp, service_specs)

    for module_name, module in manager.modules.items():
        module_spec = module_specs_by_name.get(module_name)
        if module_spec is None:  # pragma: no cover — defensive; manager guarantees 1:1
            continue
        _mount_module(mcp, module, module_spec, include_prompts=include_prompts)

    return mcp