"""
Adapter for pydantic-ai.

Only this module imports pydantic-ai. The core package (`to_tool_manager`)
never does -- if pydantic-ai isn't installed, importing
`to_tool_manager` still works; only importing THIS module fails, with
a clear error.
"""
from __future__ import annotations

import functools
import json
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from inspect import Parameter, Signature
from typing import Any

from pydantic_ai import Agent, models

from to_tool_manager.skills import build_skills_toolset, ALWAYS_ON_SKILLS, CONDITIONAL_SKILLS

try:
    from pydantic_ai import ModelRetry
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The pydantic-ai adapter requires the 'pydantic-ai' (or "
        "'pydantic-ai-slim') package. Install it with:\n"
        "    pip install pydantic-ai\n"
        "The core `to_tool_manager` package does not depend on it."
    ) from exc

try:
    from subagents_pydantic_ai import SubAgentCapability, SubAgentConfig

    _HAS_SUBAGENTS = True
except ImportError:  # pragma: no cover
    _HAS_SUBAGENTS = False

try:
    from pydantic_ai.usage import UsageLimits
except ImportError:  # pragma: no cover
    UsageLimits = None  # type: ignore[assignment,misc]

from pydantic_ai.settings import ModelSettings
from pydantic_ai.template import TemplateStr
from pydantic_ai.agent.abstract import AgentRetries, AgentModelSettings, AgentMetadata
from pydantic_ai._instructions import AgentInstructions
from pydantic_ai._agent_graph import EndStrategy
from pydantic_ai.concurrency import AnyConcurrencyLimit

from pydantic_ai.result import StreamedRunResult, StreamedRunResultSync  # noqa: F401

from to_tool_manager.core.module import Module, _build_services_overview
from to_tool_manager.core.planner import Planner, request_looks_complex
from to_tool_manager.core.types import ToolSpec

# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------

def _format_categories(cats: frozenset[str]) -> str:
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
# Module -> real sub-agent (requires the optional subagents-pydantic-ai pkg)
# ---------------------------------------------------------------------------

_UNSET: Any = object()

_DEFAULT_SUBAGENT_REQUEST_LIMIT = 8
"""Default cap on model requests for a SINGLE delegated Module run (one
`task()` call), applied only when the caller doesn't pass
`subagent_usage_limits` explicitly. Generous enough for the common
"read a couple of things, maybe write one, then answer" pattern while
still turning a confused/looping sub-agent into a bounded-latency error
instead of an unbounded one. Purely a latency/cost safety net -- raise
or disable it (`subagent_usage_limits=None`) for Modules that
legitimately need long tool-calling chains."""


@dataclass
class SubAgentDeps:
    """Default `deps` used when a manager has one or more `Module`s and the
    caller didn't provide their own `deps_type` to `build_agent`.

    `subagents-pydantic-ai` requires `RunContext.deps` to satisfy
    `SubAgentDepsProtocol` (a `subagents` dict + a `clone_for_subagent`
    method) -- if `deps` is ever `None` at call time, its `task` tool
    crashes with `AttributeError: 'NoneType' object has no attribute
    'clone_for_subagent'`. This is exactly what happens with a bare
    `Agent(...)` from pydantic-ai: EVERY entrypoint (`run`, `run_sync`,
    `run_stream`, `iter`, `to_web`, `to_cli`, ...) defaults `deps=None`
    unless the caller passes one explicitly.

    Exported publicly so a caller with their OWN deps class can combine
    the two shapes (add a `subagents: dict[str, Any]` field and a
    `clone_for_subagent` method to their own dataclass) instead of using
    this default -- in that case, pass `deps_type=YourDeps` to
    `build_agent` and `to_tool_manager` won't touch it.
    """

    subagents: dict[str, Any] = field(default_factory=dict)

    def clone_for_subagent(self, max_depth: int = 0) -> "SubAgentDeps":
        return SubAgentDeps(subagents={} if max_depth <= 0 else self.subagents)


# Every Agent method that accepts a `deps` kwarg, split by where `deps`
# sits in the signature -- `run`/`run_sync`/`run_stream`/`iter`/`to_web`
# declare it keyword-only, so it can never arrive positionally; `to_cli`/
# `to_cli_sync` declare it as their very FIRST positional-or-keyword
# parameter, so an explicit positional call must be respected too.

_KEYWORD_ONLY_DEPS_METHODS = (
    "run", "run_sync", "run_stream", "run_stream_events",
    "run_stream_sync", "iter", "to_web",
)
_LEADING_POSITIONAL_DEPS_METHODS = ("to_cli", "to_cli_sync")


def _with_default_deps_keyword(method: Any) -> Any:
    """Wraps a method whose `deps` parameter is keyword-only: inject the
    instance's default deps only if the caller didn't pass `deps=...`
    at all (it can't have been passed positionally for these methods).
    """

    @functools.wraps(method)
    def wrapper(self: "_AutoDepsAgent", *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("deps") is None and self._to_tool_manager_default_deps is not None:
            kwargs["deps"] = self._to_tool_manager_default_deps
        return method(self, *args, **kwargs)
    return wrapper


def _with_default_deps_leading_positional(method: Any) -> Any:
    """Wraps a method whose `deps` parameter is the first positional
    argument (`to_cli`/`to_cli_sync`): only inject when the caller
    supplied neither a positional `deps` nor `deps=...`.
    """

    @functools.wraps(method)
    def wrapper(self: "_AutoDepsAgent", *args: Any, **kwargs: Any) -> Any:
        if not args and kwargs.get("deps") is None and self._to_tool_manager_default_deps is not None:
            kwargs["deps"] = self._to_tool_manager_default_deps
        return method(self, *args, **kwargs)
    return wrapper


class _AutoDepsAgent(Agent):
    """An `Agent` subclass that transparently supplies a default `deps`
    instance to every deps-accepting entrypoint when the caller didn't
    pass one -- so `agent.to_web()`, `agent.run(...)`, `agent.to_cli()`,
    etc. all work out of the box the moment a `Module` is registered,
    without the caller needing to know anything about
    `subagents-pydantic-ai`'s deps protocol. Behaves as a completely
    ordinary `Agent` in every other respect (same `__slots__`-free
    subclassing pydantic-ai itself allows); `build_agent` only returns
    this instead of a plain `Agent` when there's at least one `Module`
    AND the caller didn't ask for a custom `deps_type`.
    """
    _to_tool_manager_default_deps: Any = None

    for _name in _KEYWORD_ONLY_DEPS_METHODS:
        locals()[_name] = _with_default_deps_keyword(getattr(Agent, _name))
    for _name in _LEADING_POSITIONAL_DEPS_METHODS:
        locals()[_name] = _with_default_deps_leading_positional(getattr(Agent, _name))
    del _name


_EFFICIENCY_APPENDIX = """

## Execution efficiency
You have exactly one dispatch tool for your own services, accepting a
list of `operations`. Before answering, identify every operation you
need for this task and send them all in ONE call to that tool (batched,
with `id`/`when` to sequence dependent ones) instead of calling it once
per operation -- each extra call is a full extra turn for you, on top
of the turn your parent agent already spent delegating to you."""


def _get_conditional_skills_content() -> str:
    """Returns the content of conditional skills as a single string."""
    parts = []
    for skill in CONDITIONAL_SKILLS:
        parts.append(skill.content)
    return "\n\n".join(parts)


def _default_module_instructions(module: Module) -> str:
    """Builds a sensible default system prompt for a Module's sub-agent
    when neither `system_prompt` nor `instructions` was set explicitly --
    reuses the same services overview used for the legacy dispatch-tool
    description, so the two code paths stay consistent with each other.
    """
    header = (
        module.description.strip()
        if module.description and module.description.strip()
        else f"You are the '{module.name}' specialist agent."
    )
    base = f"{header}\n\n{_build_services_overview(module.services)}"
    if module.include_efficiency_appendix:
        base += _EFFICIENCY_APPENDIX
    return base


def _build_subagent_config(module: Module, *, default_model: Any) -> "SubAgentConfig":
    """Turns a `Module` into a `SubAgentConfig`: its services become that
    sub-agent's OWN toolset (via the same `to_function_toolset` used for
    a plain Service toolset), completely isolated from the parent
    agent's tools -- the parent only ever sees the sub-agent by name and
    description, never its internal operations.
    """
    module_specs = module.sub_manager.tool_specs
    toolset = to_function_toolset(module_specs)

    base_instructions = module.system_prompt or module.instructions or _default_module_instructions(module)
    if module.include_efficiency_appendix:
        if module.system_prompt or module.instructions:
            base_instructions += _EFFICIENCY_APPENDIX

    config: dict[str, Any] = {
        "name": module.name,
        "description": module.description.strip() if module.description else (
            f"Delegates to the '{module.name}' module "
            f"({', '.join(s.name for s in module.services)})."
        ),
        "instructions": base_instructions,
        "toolsets": [toolset],
        "preferred_mode": module.subagent_mode,
    }
    if module.model is not None:
        config["model"] = module.model
    return SubAgentConfig(**config)  # type: ignore[typeddict-item]


def _build_subagent_capability(
    manager: Any,
    *,
    default_model: Any,
    include_general_purpose: bool,
    usage_limits: Any,
) -> "SubAgentCapability | None":
    """Builds ONE `SubAgentCapability` covering every `Module` registered
    on `manager`, or None if there are no Modules at all -- so `build_agent`
    never adds an empty/no-op capability to the parent Agent.
    """
    modules = list(manager.modules.values())
    if not modules:
        return None
    if not _HAS_SUBAGENTS:
        names = ", ".join(m.name for m in modules)
        raise ImportError(
            f"This manager has Module(s) registered ({names}), which the "
            "pydantic-ai adapter turns into real sub-agents -- this "
            "requires the optional 'subagents-pydantic-ai' package. "
            "Install it with:\n"
            "    pip install subagents-pydantic-ai\n"
        )
    configs = [_build_subagent_config(m, default_model=default_model) for m in modules]
    return SubAgentCapability(
        subagents=configs,
        default_model=default_model,
        include_general_purpose=include_general_purpose,
        usage_limits=usage_limits,
    )


def to_pydantic_ai_tools(specs: Sequence[ToolSpec]) -> list:
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
# R9 — Planner integration (planning_mode)
# ---------------------------------------------------------------------------

_PLANNING_REMINDER_ANNEX = """

## Multi-step requests
If this request needs more than one tool call across different services,
or later steps depend on earlier results, batch what you can into single
calls per service (see the `operations`/`id`/`when` pattern above) and
think through the dependencies before calling anything -- don't call
services one at a time and figure out the order as you go."""


def _resolve_prompt_text(prompt: Any) -> str:
    """`RunContext.prompt` is `str | Sequence[UserContent] | None` — the
    R8 heuristic only looks at text, so non-string parts (images, etc.)
    are simply skipped rather than causing an error."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, (list, tuple)):
        return " ".join(p for p in prompt if isinstance(p, str))
    return ""


def _build_planner_tools(planner: Planner, manager: Any, mode: str) -> list[Any]:
    """Turns `planner.build_tools()` into pydantic-ai `Tool`s.

    - mode == "manual": tools are always present, ungated — the LLM
      decides freely whether to use them, like any other tool.
    - mode == "gated": each tool gets a `prepare` hook running the R8
      heuristic against `ctx.prompt` for THAT turn — zero inference cost,
      no model call. Tools are excluded from that turn's tool list
      entirely when the heuristic says "simple", not just discouraged in
      the prompt.
    - anything else (in particular "off"): no planner tools at all.
    """
    from pydantic_ai.tools import Tool

    if mode not in ("manual", "gated"):
        return []

    raw_tools = planner.build_tools()
    service_names = list(manager.services) + list(manager.modules)

    if mode == "manual":
        return [Tool(t["func"], name=t["name"], description=t["description"]) for t in raw_tools]

    async def _prepare(ctx: Any, tool_def: Any) -> Any:
        text = _resolve_prompt_text(ctx.prompt)
        return tool_def if request_looks_complex(text, service_names) else None

    return [
        Tool(t["func"], name=t["name"], description=t["description"], prepare=_prepare)
        for t in raw_tools
    ]


def _make_gated_instructions(base: str, service_names: Sequence[str]):
    """Wraps a static instructions string into a dynamic one (R8): appends
    the lightweight planning reminder only on turns where the heuristic
    says "simple" (i.e. exactly the turns where the planner tools
    themselves are hidden by `_build_planner_tools`'s `prepare` hook) —
    so the model always has either the real tools or the reminder, never
    neither and never both."""
    async def _instructions(ctx: Any) -> str:
        text = _resolve_prompt_text(ctx.prompt)
        if request_looks_complex(text, service_names):
            return base
        return base + _PLANNING_REMINDER_ANNEX
    return _instructions


def _make_gated_system_prompt(
    base_prompt: str,
    manager: Any,
):
    """Creates a dynamic system prompt that includes conditional skills
    only when the request looks complex."""
    service_names = list(manager.services) + list(manager.modules)
    conditional_content = _get_conditional_skills_content()

    async def _system_prompt(ctx: Any) -> str:
        text = _resolve_prompt_text(ctx.prompt)
        if request_looks_complex(text, service_names):
            return base_prompt + "\n\n" + conditional_content
        return base_prompt

    return _system_prompt



# ---------------------------------------------------------------------------
# build_agent — full Agent constructor signature
# ---------------------------------------------------------------------------


def build_agent(
    model: models.Model | models.KnownModelName | str,
    manager: Any,
    *,
    output_type: Any = str,
    system_prompt: str | Sequence[str] | None = None,
    instructions: AgentInstructions = None,
    name: str | None = None,
    description: TemplateStr | str | None = None,
    model_settings: AgentModelSettings | None = None,
    retries: int | AgentRetries | None = None,
    deps_type: type | None = None,
    validation_context: Any | None = None,
    tool_timeout: float | None = None,
    max_concurrency: AnyConcurrencyLimit = None,
    end_strategy: EndStrategy = "graceful",
    defer_model_check: bool = False,
    metadata: AgentMetadata | None = None,
    capabilities: list | None = None,
    include_general_purpose_subagent: bool = False,
    subagent_usage_limits: Any = _UNSET,
    planner: Planner | None = None,
    planning_mode: str = "manual",
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
        Agent capabilities (e.g. ``SkillsCapability()``). Any registered
        ``Module`` is automatically turned into its own sub-agent and
        appended here as part of a single ``SubAgentCapability`` -- no
        manual wiring needed, this list is only for EXTRA capabilities.
    include_general_purpose_subagent:
        Passed straight through to ``SubAgentCapability``. If ``True``,
        adds a generic fallback sub-agent alongside the ones derived
        from registered Modules. Defaults to ``False`` because
        to_tool_manager's model is explicit, named Modules -- not an
        open-ended delegate.
    subagent_usage_limits:
        ``pydantic_ai.usage.UsageLimits`` (or a per-task factory) applied
        to every delegated Module run. If omitted entirely, defaults to
        ``UsageLimits(request_limit=8)`` as a latency/cost safety net so
        a confused sub-agent can't loop indefinitely. Pass ``None``
        explicitly to run Module delegations with no cap, or your own
        ``UsageLimits``/factory to override the default. Ignored when
        the manager has no ``Module``s.
    planner:
        Optional ``Planner`` (from ``manager.with_planner(...)``). If
        omitted, this function behaves exactly as before Fase 4 —
        nothing about planning changes. If provided, its
        ``create_plan``/``execute_plan``/``get_plan``/``update_plan_step``
        tools are wired into this agent according to ``planning_mode``.
    planning_mode:
        ``"off"``: ``planner`` is ignored entirely, even if passed — no
        planner tools, no prompt changes. ``"manual"`` (default): if
        ``planner`` is set, its tools are added unconditionally, every
        turn — the model decides on its own whether to use them, like
        any other tool. No ``planner`` set + default mode is identical
        to calling this function before Fase 4 existed. ``"gated"``: a
        zero-inference-cost heuristic (R8, see
        ``core.planner.request_looks_complex``) decides PER TURN, from
        the request text alone: simple → planner tools are hidden and a
        short prompt reminder about batching/dependencies is appended
        instead; possibly complex → the planner tools are exposed for
        that turn and the reminder is omitted (the tools' own
        descriptions are guidance enough). Never forces a
        plan-then-execute step on every turn regardless of the query —
        that's the antipattern this mode exists to avoid.
    """
    from to_tool_manager.core.prompts import build_instructions, build_system_prompt

    # Service -> plain tool on the parent agent. Module -> real sub-agent
    # (built below into a SubAgentCapability, via `manager.modules`
    # directly -- see `_build_subagent_capability`). Using
    # `manager.service_specs` here (Services only) instead of the full
    # `manager.tool_specs` avoids building every Module's batched
    # ToolSpec (dispatch closure, description, recursive sub-manager
    # visit) just to immediately discard it -- that spec was never used
    # on this path in the first place (D5).
    service_specs = manager.service_specs
    tools = to_pydantic_ai_tools(service_specs)

    # R9 — Planner integration. No `planner` passed => this block is a
    # no-op and behaves exactly as it did before Fase 4.
    
    planner_tools: list[Any] = []
    resolved_instructions: Any = instructions if instructions is not None else build_instructions()
    if planner is not None and planning_mode != "off":
        planner_tools = _build_planner_tools(planner, manager, planning_mode)
        if planning_mode == "gated" and isinstance(resolved_instructions, str):
            service_names = list(manager.services) + list(manager.modules)
            resolved_instructions = _make_gated_instructions(resolved_instructions, service_names)
    tools = tools + planner_tools

    default_settings: ModelSettings = ModelSettings(parallel_tool_calls=True)
    merged_settings: ModelSettings = {**default_settings, **(model_settings or {})}  # type: ignore[typeddict-item]

    agent_kwargs: dict[str, Any] = {}
    if name is not None:
        agent_kwargs["name"] = name
    if description is not None:
        agent_kwargs["description"] = description
    if retries is not None:
        agent_kwargs["retries"] = retries
    if validation_context is not None:
        agent_kwargs["validation_context"] = validation_context
    if tool_timeout is not None:
        agent_kwargs["tool_timeout"] = tool_timeout
    if max_concurrency is not None:
        agent_kwargs["max_concurrency"] = max_concurrency
    if end_strategy != "graceful":
        agent_kwargs["end_strategy"] = end_strategy
    if defer_model_check:
        agent_kwargs["defer_model_check"] = defer_model_check
    if metadata is not None:
        agent_kwargs["metadata"] = metadata

    resolved_capabilities: list[Any] = list(capabilities or [])
    if subagent_usage_limits is not _UNSET:
        resolved_usage_limits = subagent_usage_limits
    elif UsageLimits is not None:
        resolved_usage_limits = UsageLimits(request_limit=_DEFAULT_SUBAGENT_REQUEST_LIMIT)
    else:  # pragma: no cover
        resolved_usage_limits = None
    subagent_capability = _build_subagent_capability(
        manager,
        default_model=model,
        include_general_purpose=include_general_purpose_subagent,
        usage_limits=resolved_usage_limits,
    )
    if subagent_capability is not None:
        resolved_capabilities.append(subagent_capability)

     # If there's at least one Module and the caller didn't bring their own
    # deps_type, subagents-pydantic-ai still requires RunContext.deps to
    # satisfy SubAgentDepsProtocol at call time -- otherwise its `task`
    # tool crashes with `AttributeError: 'NoneType' object has no
    # attribute 'clone_for_subagent'` the moment it's invoked, on EVERY
    # entrypoint that doesn't get an explicit `deps=...` (run, run_sync,
    # to_web, to_cli, ...). We close that gap for the common case here:
    # a default SubAgentDeps() is both declared as deps_type AND
    # auto-injected at call time via _AutoDepsAgent, so it works the same
    # everywhere without the caller needing to know this protocol exists.
    
    agent_cls: type[Agent] = Agent
    if deps_type is not None:
        agent_kwargs["deps_type"] = deps_type
    elif subagent_capability is not None:
        agent_kwargs["deps_type"] = SubAgentDeps
        agent_cls = _AutoDepsAgent

    all_services_and_modules = list(manager.services.values()) + list(manager.modules.values())
    skills_toolset = build_skills_toolset(skills=ALWAYS_ON_SKILLS)

    base_system_prompt = system_prompt if system_prompt is not None else build_system_prompt(all_services_and_modules)

    resolved_system_prompt: Any = _make_gated_system_prompt(base_system_prompt, manager)

    # NOTE: `Agent.__init__`'s `system_prompt` parameter only accepts a
    # `str | Sequence[str]` -- passing a callable directly raises
    # `TypeError: 'function' object is not iterable` (pydantic-ai>=2.10.0,
    # resolves today to 2.21.0), on EVERY call to build_agent(), since
    # `_make_gated_system_prompt` always returns a callable. Dynamic system
    # prompts must instead be registered post-construction via the
    # `agent.system_prompt(fn)` decorator/method.
    agent = agent_cls(
        model,
        instructions=resolved_instructions,
        tools=tools,
        output_type=output_type,
        model_settings=merged_settings,
        toolsets=[skills_toolset],
        capabilities=resolved_capabilities or None,
        **agent_kwargs,
    )
    agent.system_prompt(resolved_system_prompt)
    if agent_cls is _AutoDepsAgent:
        agent._to_tool_manager_default_deps = SubAgentDeps()
    return agent


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
