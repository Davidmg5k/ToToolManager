"""
Adapter for pydantic-ai.

Only this module imports pydantic-ai. The core package (`to_tool_manager`)
never does — if pydantic-ai isn't installed, importing
`to_tool_manager` still works; only importing THIS module fails, with
a clear error.
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from inspect import Parameter, Signature
from typing import Any

from pydantic_ai import Agent, models

from to_tool_manager.skills import build_skills_toolset

try:
    from pydantic_ai import ModelRetry
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The pydantic-ai adapter requires the 'pydantic-ai' (or "
        "'pydantic-ai-slim') package. Install it with:\n"
        "    pip install pydantic-ai\n"
        "The core `to_tool_manager` package does not depend on it."
    ) from exc

from pydantic_ai.settings import ModelSettings

# Re-export streaming types so consumers don't import pydantic-ai directly.
from pydantic_ai.result import StreamedRunResult, StreamedRunResultSync  # noqa: F401

from to_tool_manager.core.types import ToolSpec


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------

def _format_categories(cats: frozenset[str]) -> str:
    """Normalizes a category frozenset into a display string for the LLM.

    - Empty → ``""``
    - Single → ``"not_found"``
    - Multiple → ``"not_found, missing"``
    """
    if not cats:
        return ""
    if len(cats) == 1:
        return next(iter(cats))
    return ", ".join(sorted(cats))


def _format_error(spec: ToolSpec, error) -> str:
    """Format a ToolError for the LLM.

    - ``handled=True``  — programmer-mapped error; full context.
    - ``handled=False`` — unanticipated error; report only, no action.
    """
    cats = _format_categories(error.category)
    prefix = f"[{cats}] " if cats else ""
    return f"{prefix}{error.message}"


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tool builder
# ---------------------------------------------------------------------------

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
        formatted = _format_error(spec, error)
        if error.retryable:
            # Lets the model see the error and try again with corrected
            # arguments in the same run, instead of just narrating a
            # failure in plain text.
            raise ModelRetry(formatted)
        return formatted

    tool_func.__name__ = spec.name
    tool_func.__qualname__ = spec.name
    tool_func.__doc__ = spec.description
    tool_func.__signature__ = Signature(sig_params)  # type: ignore[attr-defined]
    tool_func.__annotations__ = {p.name: p.annotation for p in spec.parameters}
    tool_func.__annotations__["return"] = str
    return tool_func


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def to_pydantic_ai_tools(specs: Sequence[ToolSpec]) -> list:
    """Returns a list of plain async functions suitable for
    `Agent(tools=[...])` or `FunctionToolset(tools=[...])`."""
    return [_build_callable(spec) for spec in specs]


def to_function_toolset(specs: Sequence[ToolSpec], *, instructions: str | None = None):
    """
    Builds a single `pydantic_ai.FunctionToolset` from the given specs.
    Useful when you want one toolset per Service with its own
    `instructions`, so it can be composed/swapped independently.
    """
    from pydantic_ai import FunctionToolset

    toolset = FunctionToolset(instructions=instructions) if instructions else FunctionToolset()
    for spec in specs:
        toolset.add_function(_build_callable(spec), name=spec.name, description=spec.description)
    return toolset


# ---------------------------------------------------------------------------
# build_agent — full Agent constructor signature
# ---------------------------------------------------------------------------

def build_agent(
    model: models.KnownModelName,
    manager: Any,
    *,
    output_type: Any = str,
    system_prompt: str | Sequence[str] | None = None,
    instructions: str | None = None,
    name: str | None = None,
    description: str | None = None,
    model_settings: ModelSettings | None = None,
    retries: int | None = None,
    deps_type: type | None = None,
    tool_timeout: float | None = None,
    max_concurrency: int | None = None,
    end_strategy: str | None = None,
    defer_model_check: bool = False,
    capabilities: list | None = None,
) -> Agent:
    """Create a pydantic-ai Agent wired to the manager's tools.

    This exposes the full Agent constructor signature so every option
    is explicitly visible and type-checkable — no hidden ``**kwargs``
    that could silently break internals.

    Parameters
    ----------
    model:
        The LLM model (string like ``"groq:llama-3.1-8b-instant"`` or
        a ``pydantic_ai.models.Model`` instance).
    manager:
        A ``ToToolManager`` instance providing ``tool_specs``.
    output_type:
        Pydantic BaseModel / dataclass / TypedDict / ``str`` for
        structured output. Passed directly to Agent.
    system_prompt:
        Static system prompt(s). If ``None``, auto-generated from
        registered services.
    instructions:
        Dynamic instructions (str or callable). If ``None``,
        auto-generated from the framework defaults.
    name:
        Agent name for logging and tracing.
    description:
        Human-readable description attached to OTel spans.
    model_settings:
        Static model settings (temperature, max_tokens, etc.).
        Merged with ``parallel_tool_calls=True`` by default.
    retries:
        Per-category retry budget. ``None`` uses Agent defaults.
    deps_type:
        Dependency injection type for static typing.
    tool_timeout:
        Default timeout in seconds for tool execution.
    max_concurrency:
        Limit on concurrent agent runs.
    end_strategy:
        How to handle tool calls alongside final result.
    defer_model_check:
        Defer model evaluation until first run.
    capabilities:
        Agent capabilities (e.g. ``SkillsCapability()``).
    """
    from to_tool_manager.core.prompts import build_instructions, build_system_prompt

    tools = to_pydantic_ai_tools(manager.tool_specs)

    default_settings: ModelSettings = ModelSettings(parallel_tool_calls=True)
    merged_settings: ModelSettings = {**default_settings, **(model_settings or {})}  # type: ignore[typeddict-item]

    agent_kwargs: dict[str, Any] = {}
    if name is not None:
        agent_kwargs["name"] = name
    if description is not None:
        agent_kwargs["description"] = description
    if retries is not None:
        agent_kwargs["retries"] = retries
    if deps_type is not None:
        agent_kwargs["deps_type"] = deps_type
    if tool_timeout is not None:
        agent_kwargs["tool_timeout"] = tool_timeout
    if max_concurrency is not None:
        agent_kwargs["max_concurrency"] = max_concurrency
    if end_strategy is not None:
        agent_kwargs["end_strategy"] = end_strategy
    if defer_model_check:
        agent_kwargs["defer_model_check"] = defer_model_check
    if capabilities is not None:
        agent_kwargs["capabilities"] = capabilities

    all_services_and_modules = list(manager.services.values()) + list(manager.modules.values())
    skills_toolset = build_skills_toolset()

    return Agent(
        model,
        system_prompt=system_prompt if system_prompt is not None else build_system_prompt(all_services_and_modules),
        instructions=instructions or build_instructions(),
        tools=tools,
        output_type=output_type,
        model_settings=merged_settings,
        toolsets=[skills_toolset],
        **agent_kwargs,
    )


# ---------------------------------------------------------------------------
# Streaming / iteration wrappers
# ---------------------------------------------------------------------------

@asynccontextmanager
async def iter_agent(
    agent: Agent,
    prompt: str | None = None,
    *,
    deps: Any = None,
    model_settings: ModelSettings | None = None,
    usage_limits: Any = None,
) -> AsyncGenerator[Any]:
    """Iterate graph nodes of an agent run — for observability or control.

    Usage::

        async with iter_agent(agent, "do something") as run:
            async for node in run:
                print(type(node).__name__)
    """
    kwargs: dict[str, Any] = {}
    if prompt is not None:
        kwargs["user_prompt"] = prompt
    if deps is not None:
        kwargs["deps"] = deps
    if model_settings is not None:
        kwargs["model_settings"] = model_settings
    if usage_limits is not None:
        kwargs["usage_limits"] = usage_limits

    async with agent.iter(**kwargs) as run:
        yield run


@asynccontextmanager
async def run_streaming(
    agent: Agent,
    prompt: str | None = None,
    *,
    deps: Any = None,
    model_settings: ModelSettings | None = None,
    usage_limits: Any = None,
) -> AsyncGenerator[StreamedRunResult]:
    """Stream output from an agent run — for real-time UIs.

    Usage::

        async with run_streaming(agent, "generate report") as stream:
            async for text in stream.stream_text():
                print(text, end="", flush=True)
    """
    kwargs: dict[str, Any] = {}
    if prompt is not None:
        kwargs["user_prompt"] = prompt
    if deps is not None:
        kwargs["deps"] = deps
    if model_settings is not None:
        kwargs["model_settings"] = model_settings
    if usage_limits is not None:
        kwargs["usage_limits"] = usage_limits

    async with agent.run_stream(**kwargs) as stream:
        yield stream
