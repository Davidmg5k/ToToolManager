"""
`Module` groups related Services under a single sub-agent boundary.

A Module is a self-contained unit of functionality: it has its own
services, its own system prompt, and is isolated from other Modules.

What "sub-agent" means depends on the adapter:

- **pydantic-ai adapter** (`adapters.pydantic_ai.build_agent`): a Module
  becomes a REAL sub-agent -- a `SubAgentConfig` registered on a single
  `SubAgentCapability`, with this Module's services as that sub-agent's
  own toolset. The parent LLM delegates a task to it in natural
  language; the sub-agent's own LLM run decides which of its services'
  operations to call. This requires the optional `subagents-pydantic-ai`
  package.
- **Every other adapter** (raw, fastmcp, ag_ui): there's no framework
  concept of an LLM sub-agent, so a Module instead produces ONE
  ToolSpec that wraps its services behind a single batched-operations
  dispatch call (`build_tool_spec`) -- the calling LLM picks the
  `{"method": ..., "args": {...}}` operations directly, same as a
  Service tool, just grouped under one name.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Sequence

from to_tool_manager.core.conditions import _evaluate_when
from to_tool_manager.core.types import (
    OperationSpec,
    ParamSpec,
    ToolError,
    ToolResponse,
    ToolSpec,
    _is_complex_type,
    describe_complex_type,
)

if TYPE_CHECKING:
    from to_tool_manager.core.service import Service
    from to_tool_manager.security.middleware import Middleware

_MODULE_OPERATIONS_CONTRACT_REF = (
    "See operations contract above. "
    "Each item: {{\"method\": <name>, \"args\": {{...}}}}. "
    "Optional \"id\" and \"when\" for sequencing."
)


def _format_param(p: ParamSpec) -> str:
    type_name = getattr(p.annotation, "__name__", str(p.annotation))
    marker = "" if p.required else "?"
    if _is_complex_type(p.annotation):
        return f"{p.name}{marker}: {describe_complex_type(p.annotation)}"
    if p.required:
        return f"{p.name}: {type_name}"
    return f"{p.name}?"


def _build_module_operations_contract(operations: Sequence[OperationSpec]) -> str:
    return _MODULE_OPERATIONS_CONTRACT_REF


def _build_module_description(
    module_name: str,
    description: str,
    services_overview: str,
    operations: Sequence[OperationSpec],
    *,
    contract: str,
) -> str:
    parts: list[str] = []
    if description and description.strip():
        parts.append(description.strip())

    if parts:
        header = "\n\n".join(parts)
    else:
        header = (
            f"Module '{module_name}' - a sub-agent managing "
            f"the following services:"
        )

    lines = [header, "", services_overview, "", "Available operations (use as the `method` value):"]
    for op in operations:
        params = ", ".join(_format_param(p) for p in op.parameters) or "no arguments"
        lines.append(f"- {op.name}({params}): {op.description}")
    lines.append("")
    lines.append(contract)
    return "\n".join(lines)


def _build_services_overview(services: Sequence[Any]) -> str:
    lines = []
    for service in services:
        desc = service.description.strip() if service.description else f"Service for {service.name}."
        lines.append(f"- **{service.name}**: {desc}")
    return "\n".join(lines) if lines else "- (no services)"


@dataclass
class Module:
    """Groups related Services under a single sub-agent boundary.

    A Module is isolated: it only sees its own services, has its own
    system prompt, and produces a single ToolSpec when registered in a
    ToToolManager.

    Example::

        Module(
            name="OrderManagement",
            description="Manages order and user operations",
            system_prompt="You are an order management specialist...",
            services=[
                Service(name="Order", service=Order, ...),
                Service(name="User", service=User, ...),
            ]
        )
    """

    name: str
    services: Sequence[Service]

    description: str = ""
    """Group-level description for this module."""

    system_prompt: str | None = None
    """Independent system prompt for this module. If None, a default
    prompt is generated from the services description."""

    instructions: str | None = None
    """Dynamic instructions for this module."""

    model: str | None = None
    """Optional model override for this module when it's registered as a
    real sub-agent by the pydantic-ai adapter (`adapters.pydantic_ai.
    build_agent`). If None, the parent agent's model is used. Ignored by
    every other adapter (raw, fastmcp, ag_ui), since only pydantic-ai has
    a concept of a sub-agent running its own model."""

    subagent_mode: Literal["sync", "async", "auto"] = "sync"
    """Preferred execution mode passed to `subagents-pydantic-ai` as this
    Module's `SubAgentConfig["preferred_mode"]` (pydantic-ai adapter
    only; ignored elsewhere). Config-level `preferred_mode` takes
    priority over the delegating LLM's own "auto" mode guess (see
    `decide_execution_mode`'s priority order), so this is what actually
    decides sync vs. async -- not a hint.

    Defaults to `"sync"`: a Module here is an explicit, named,
    request/response unit (see the class docstring), not an
    open-ended background worker. `"async"` makes the PARENT model
    call `task()` then, on a LATER turn, `wait_tasks()`/`check_task()`
    to get the result -- an extra full model round trip that's rarely
    worth it for the "ask a Module something, get an answer back"
    pattern this library is built around. Set to `"async"` (long,
    independently-runnable Module work the parent can multitask
    around) or `"auto"` (let the delegating LLM decide per-call) only
    if that trade-off is actually wanted for a specific Module."""

    include_efficiency_appendix: bool = True
    """If True (default), a short operational appendix -- "batch every
    operation you need from your own services into ONE dispatch call
    instead of calling it repeatedly" -- is appended to this Module's
    sub-agent instructions (pydantic-ai adapter only). Without it nothing
    tells the sub-agent's OWN model this, so it tends to call its
    dispatch tool once per operation instead of once per turn, adding
    extra internal round trips on top of the parent<->sub-agent hop
    that already exists. Set False if `system_prompt`/`instructions`
    already covers this or the appendix isn't wanted for some Module."""

    middlewares: Sequence[Middleware] = field(default_factory=tuple)
    """Middlewares applied at the tool level for this module.

    These middlewares are passed to the internal sub-manager as
    global middlewares and affect all services inside this module.
    They execute *after* ToToolManager-level middlewares."""

    disable_middlewares: Sequence[str] = field(default_factory=tuple)
    """Names of global (ToToolManager-level) middlewares to disable
    for all services inside this module.  Only affects middlewares
    registered at the manager level."""

    _sub_manager: Any = field(default=None, init=False, repr=False, compare=False)
    _sub_manager_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False, compare=False)
    _specs: list[ToolSpec] | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.services:
            raise ValueError(
                f"Module '{self.name}': must contain at least one Service."
            )

    def _get_sub_manager(self, parent_middlewares: Sequence[Middleware] | None = None) -> Any:
        """Lazily create the internal ToToolManager.

        ``parent_middlewares`` are the middlewares from the parent
        ``ToToolManager``.  They are merged *before* the module's own
        middlewares so that each service inside this module can
        disable them via ``disable_middlewares``.

        Thread-safe double-checked locking (same pattern as
        `Service.get_instance`): concurrent callers racing on the first
        call are guaranteed to observe exactly one constructed
        `ToToolManager`, never more. The lock is per-`Module`.
        """
        sub_manager = self._sub_manager
        if sub_manager is not None:
            return sub_manager

        with self._sub_manager_lock:
            if self._sub_manager is None:
                from to_tool_manager.core.manager import ToToolManager

                merged: list[Middleware] = list(parent_middlewares or ())
                merged.extend(self.middlewares or ())
                self._sub_manager = ToToolManager(
                    self.services,
                    middlewares=merged or None,
                )
            return self._sub_manager

    @property
    def sub_manager(self) -> Any:
        return self._get_sub_manager()

    def build_tool_spec(self, parent_middlewares: Sequence[Middleware] | None = None) -> ToolSpec:
        manager = self._get_sub_manager(parent_middlewares)

        all_operations: list[OperationSpec] = []
        for spec in manager.tool_specs:
            all_operations.extend(spec.operations)

        services_overview = _build_services_overview(self.services)
        contract = _build_module_operations_contract(all_operations)

        async def dispatch_call(operations: Any = None, **_ignored) -> ToolResponse:
            if not isinstance(operations, list) or not operations:
                return ToolResponse(
                    error=ToolError(
                        category=frozenset({"validation_error"}),
                        message=(
                            "`operations` must be a non-empty list of "
                            '{"method": ..., "args": {...}} objects.'
                        ),
                        exception_type="ValueError",
                        retryable=True,
                    )
                )

            results: list[dict[str, Any]] = []
            resolved_by_ref: dict[str, dict[str, Any]] = {}

            for index, raw_op in enumerate(operations):
                position_ref = f"op{index}"

                if not isinstance(raw_op, dict):
                    entry = {
                        "method": None,
                        "success": False,
                        "error": {
                            "category": "validation_error",
                            "message": "Each operation must be an object with 'method' and 'args'.",
                        },
                    }
                    results.append(entry)
                    resolved_by_ref[position_ref] = entry
                    continue

                method_name = raw_op.get("method")
                op_args = raw_op.get("args", {}) or {}
                custom_ref = raw_op.get("id")
                custom_ref = custom_ref if isinstance(custom_ref, str) else None
                when = raw_op.get("when")

                if not isinstance(op_args, dict):
                    entry = {
                        "method": method_name,
                        "success": False,
                        "error": {"category": "validation_error", "message": "'args' must be an object."},
                    }
                    results.append(entry)
                    resolved_by_ref[position_ref] = entry
                    if custom_ref:
                        resolved_by_ref[custom_ref] = entry
                    continue

                if when is not None:
                    skip_entry = _evaluate_when(when, resolved_by_ref)
                    if skip_entry is not None:
                        entry = {"method": method_name, "skipped": True, "reason": skip_entry}
                        results.append(entry)
                        resolved_by_ref[position_ref] = {**entry, "success": False}
                        if custom_ref:
                            resolved_by_ref[custom_ref] = resolved_by_ref[position_ref]
                        continue

                response = await _dispatch_to_services(
                    manager, method_name, op_args
                )

                if response.error is not None:
                    cats = response.error.category
                    entry = {
                        "method": method_name,
                        "id": custom_ref,
                        "success": False,
                        "error": {
                            "category": sorted(cats) if cats else None,
                            "message": response.error.message,
                        },
                    }
                elif isinstance(response.content, list) and len(response.content) == 1:
                    inner = response.content[0]
                    entry = {
                        "method": method_name,
                        "id": custom_ref,
                        "success": inner.get("success", False),
                    }
                    if entry["success"]:
                        entry["result"] = inner.get("result")
                    else:
                        entry["error"] = inner.get("error")
                else:
                    entry = {"method": method_name, "id": custom_ref, "success": True, "result": response.content}
                results.append(entry)
                resolved_by_ref[position_ref] = entry
                if custom_ref:
                    resolved_by_ref[custom_ref] = entry

            return ToolResponse(content=results)

        return ToolSpec(
            name=self.name,
            description=_build_module_description(
                self.name, self.description, services_overview, all_operations, contract=contract
            ),
            parameters=(
                ParamSpec(
                    name="operations",
                    annotation=list[dict],
                    required=True,
                    description=contract,
                ),
            ),
            call=dispatch_call,
            operations=tuple(all_operations),
            class_description=self.description or None,
            service_name=self.name,
            metadata={"type": "module", "services": [s.name for s in self.services]},
        )


async def _dispatch_to_services(manager: Any, method_name: str | None, op_args: dict) -> ToolResponse:
    for spec in manager.tool_specs:
        for op in spec.operations:
            if op.name == method_name:
                return await spec.call(operations=[{"method": method_name, "args": op_args}])

    available = []
    for spec in manager.tool_specs:
        for op in spec.operations:
            available.append(op.name)

    return ToolResponse(
        error=ToolError(
            category=frozenset({"unknown_operation"}),
            message=f"Unknown operation '{method_name}'. Available: {', '.join(sorted(available))}.",
            exception_type="ValueError",
            retryable=False,
        )
    )
