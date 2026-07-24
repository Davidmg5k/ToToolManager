"""
`Module` groups related Services under a single sub-agent boundary.

A Module is a self-contained unit of functionality: it has its own
services, its own system prompt, and is isolated from other Modules.
When registered in a ToToolManager, it produces ONE ToolSpec that
wraps the entire sub-agent — the parent agent calls the Module as a
single tool and the internal ToToolManager delegates to its services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Sequence

from to_tool_manager.core.types import (
    OperationSpec,
    ParamSpec,
    ToolError,
    ToolResponse,
    ToolSpec,
)

if TYPE_CHECKING:
    from to_tool_manager.core.service import Service
    from to_tool_manager.security.middleware import Middleware

_MODULE_OPERATIONS_CONTRACT = (
    'Each item: {{"method": <name>, "args": {{...}}}}. Call this module\'s '
    "tool ONCE with every operation you need from its services instead of "
    "calling it repeatedly.\n"
    "Example: {example}"
)


def _format_param(p: ParamSpec) -> str:
    type_name = getattr(p.annotation, "__name__", str(p.annotation))
    marker = "" if p.required else "?"
    return f"{p.name}{marker}: {type_name}"


def _example_placeholder(annotation: Any) -> Any:
    type_name = getattr(annotation, "__name__", "")
    return {"str": "...", "int": 0, "float": 0.0, "bool": True}.get(type_name, "...")


def _build_module_operations_contract(operations: Sequence[OperationSpec]) -> str:
    if not operations:
        return _MODULE_OPERATIONS_CONTRACT.format(
            example='{"operations": [{"method": "<name>", "args": {}}]}'
        )

    first = operations[0]
    first_args = {p.name: _example_placeholder(p.annotation) for p in first.parameters if p.required}
    example_ops: list[dict[str, Any]] = [{"id": "step1", "method": first.name, "args": first_args}]

    no_arg_op = next((op for op in operations[1:] if not any(p.required for p in op.parameters)), None)
    if no_arg_op is not None:
        example_ops.append(
            {
                "method": no_arg_op.name,
                "args": {},
                "when": {"op": "step1", "outcome": "error"},
            }
        )

    import json

    example = json.dumps({"operations": example_ops})
    return _MODULE_OPERATIONS_CONTRACT.format(example=example)


def _build_module_description(
    module_name: str,
    description: str,
    services_overview: str,
    operations: Sequence[OperationSpec],
) -> str:
    parts: list[str] = []
    if description and description.strip():
        parts.append(description.strip())

    if parts:
        header = "\n\n".join(parts)
    else:
        header = (
            f"Module '{module_name}' — a sub-agent managing "
            f"the following services:"
        )

    lines = [header, "", services_overview, "", "Available operations (use as the `method` value):"]
    for op in operations:
        params = ", ".join(_format_param(p) for p in op.parameters) or "no arguments"
        lines.append(f"- {op.name}({params}): {op.description}")
    lines.append("")
    lines.append(_build_module_operations_contract(operations))
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
        """
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
        """Access the internal ToToolManager (read-only)."""
        return self._get_sub_manager()

    def build_tool_spec(self, parent_middlewares: Sequence[Middleware] | None = None) -> ToolSpec:
        """Build a single ToolSpec that wraps this module as a sub-agent."""
        manager = self._get_sub_manager(parent_middlewares)

        all_operations: list[OperationSpec] = []
        for spec in manager.tool_specs:
            all_operations.extend(spec.operations)

        services_overview = _build_services_overview(self.services)

        async def dispatch_call(operations: Any = None, **_ignored) -> ToolResponse:
            if not isinstance(operations, list) or not operations:
                return ToolResponse(
                    error=ToolError(
                        category=frozenset("validation_error"),
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
                        "success": inner.get("success", False),
                    }
                    if entry["success"]:
                        entry["result"] = inner.get("result")
                    else:
                        entry["error"] = inner.get("error")
                else:
                    entry = {"method": method_name, "success": True, "result": response.content}
                results.append(entry)
                resolved_by_ref[position_ref] = entry
                if custom_ref:
                    resolved_by_ref[custom_ref] = entry

            return ToolResponse(content=results)

        return ToolSpec(
            name=self.name,
            description=_build_module_description(
                self.name, self.description, services_overview, all_operations
            ),
            parameters=(
                ParamSpec(
                    name="operations",
                    annotation=list[dict],
                    required=True,
                    description=_build_module_operations_contract(all_operations),
                ),
            ),
            call=dispatch_call,
            operations=tuple(all_operations),
            class_description=self.description or None,
            service_name=self.name,
            metadata={"type": "module", "services": [s.name for s in self.services]},
        )


def _evaluate_when(when: Any, resolved_by_ref: dict[str, dict[str, Any]]) -> str | None:
    if not isinstance(when, dict):
        return "malformed 'when' clause (must be an object); operation skipped."

    op_ref = when.get("op")
    outcome = when.get("outcome")
    if not isinstance(op_ref, str) or outcome not in ("success", "error"):
        return "malformed 'when' clause (need 'op': str and 'outcome': 'success'|'error'); operation skipped."

    referenced = resolved_by_ref.get(op_ref)
    if referenced is None:
        return f"referenced operation '{op_ref}' has not run (yet) or does not exist; operation skipped."
    if referenced.get("skipped"):
        return f"referenced operation '{op_ref}' was itself skipped; operation skipped."

    ref_success = bool(referenced.get("success"))
    outcome_match = (ref_success and outcome == "success") or (not ref_success and outcome == "error")
    if not outcome_match:
        actual = "success" if ref_success else "error"
        return f"condition not met ('{op_ref}' outcome was '{actual}', expected '{outcome}')."

    category = when.get("category")
    if category is not None:
        ref_error = referenced.get("error") or {}
        ref_cats = ref_error.get("category")
        if isinstance(ref_cats, str):
            ref_cats = {ref_cats}
        elif isinstance(ref_cats, (list, tuple, set, frozenset)):
            ref_cats = set(ref_cats)
        else:
            ref_cats = set()
        if isinstance(category, str):
            target_cats = {category}
        elif isinstance(category, (list, tuple, set, frozenset)):
            target_cats = set(category)
        else:
            target_cats = set()
        if not target_cats & ref_cats:
            return (
                f"condition not met (expected error category "
                f"'{category}', got '{ref_cats or None}')."
            )

    return None


async def _dispatch_to_services(manager: Any, method_name: str, op_args: dict) -> ToolResponse:
    """Find the service that owns the method and dispatch to it."""
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
            category=frozenset("unknown_operation"),
            message=f"Unknown operation '{method_name}'. Available: {', '.join(sorted(available))}.",
            exception_type="ValueError",
            retryable=False,
        )
    )
