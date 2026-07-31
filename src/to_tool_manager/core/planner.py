"""
Cross-service planning module.

Adds a planning layer on top of ToToolManager that:
- Creates plans with steps referencing operations across multiple services
- Tracks step-level state (pending/in_progress/completed/failed/skipped)
- Validates execution order against an optional dependency graph
- Emits events for streaming state to UIs (ag_ui or custom handlers)
- Integrates cleanly with the existing batching and `when` clause system

The planner is optional — existing ToToolManager usage is unaffected.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

from to_tool_manager.core.conditions import _evaluate_when

if TYPE_CHECKING:
    from to_tool_manager.core.manager import ToToolManager
    from to_tool_manager.core.types import ToolSpec


# ---------------------------------------------------------------------------
# Enums & Models
# ---------------------------------------------------------------------------


class StepStatus(str, Enum):
    """Status of a single plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepOperation(BaseModel):
    """An operation to execute within a step, referencing a specific service."""

    service: str = Field(description="Name of the service (e.g. 'Order')")
    method: str = Field(description="Method name to call (e.g. 'create')")
    args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the method")
    id: str | None = Field(default=None, description="Optional id for referencing in when clauses")


class Step(BaseModel):
    """A single step in a plan, containing one or more operations."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8], description="Unique step identifier")
    description: str = Field(description="Human-readable description of the step")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Current status")
    operations: list[StepOperation] = Field(default_factory=list, description="Operations to execute")
    depends_on: list[str] = Field(default_factory=list, description="Ids of steps that must complete first")
    condition: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional gate on whether this step runs at all, same shape as an "
            "operation-level `when` clause: {'op': <step_id>, 'outcome': "
            "'success'|'error', 'category'?: <str|list>}. If unmet, the step "
            "is marked SKIPPED (not FAILED) and never executed. The "
            "referenced step id is automatically added to `depends_on` if "
            "not already present, so ordering is always safe."
        ),
    )
    result: Any = Field(default=None, description="Execution result (set after completion)")
    error: str | None = Field(default=None, description="Error message if failed")
    state_field: str | None = Field(
        default=None,
        description=(
            "Optional: name of a field on the Planner's `state_type` model "
            "that this step's result maps to. Purely additive — only "
            "meaningful if the Planner was built with `state_type` set; "
            "otherwise ignored. The step must call exactly one service; if "
            "that service's call resolved a single operation, the raw "
            "return value is used, otherwise the list of per-operation "
            "results is used as-is."
        ),
    )


def _step_state_value(step: Step) -> Any:
    """Extracts the value a completed step contributes to `state_field`
    (R5). Reuses the same auto-unwrap convention as `$from`: a step
    mapped to a state field must call exactly one service; if that
    service ran a single operation, the raw return value is used,
    otherwise the list of per-operation result entries is used as-is."""
    if not isinstance(step.result, dict) or len(step.result) != 1:
        n = len(step.result) if isinstance(step.result, dict) else 0
        raise ValueError(
            f"Step '{step.id}': state_field requires the step to call "
            f"exactly one service (it called {n})."
        )
    (service_name, service_result), = step.result.items()
    if not service_result.get("success"):
        raise ValueError(
            f"Step '{step.id}': service '{service_name}' did not succeed, "
            "can't map its result to state."
        )
    entries = service_result.get("result")
    if isinstance(entries, list) and len(entries) == 1:
        return entries[0].get("result")
    return entries


class Plan(BaseModel):
    """A plan containing multiple steps to execute across services."""

    id: str = Field(default_factory=lambda: uuid4().hex, description="Unique plan identifier")
    steps: list[Step] = Field(default_factory=list, description="Ordered list of steps")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cross-step references ($from)
# ---------------------------------------------------------------------------


class PlanRefError(ValueError):
    """Raised when a `$from` reference in a step's args cannot be resolved."""


_PATH_SEGMENT_RE = re.compile(r"^([^\[\]]+)((?:\[\d+\])*)$")


def _scan_from_refs(value: Any) -> list[tuple[str, str]]:
    """Recursively collects every `{"$from": step_id, "path": path}` marker
    found inside *value*, for structural (step-id-exists) validation at
    create_plan time — before anything has executed."""
    refs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if set(value.keys()) == {"$from", "path"}:
            refs.append((value["$from"], value["path"]))
        else:
            for v in value.values():
                refs.extend(_scan_from_refs(v))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_scan_from_refs(item))
    return refs


def _navigate_segment(current: Any, segment: str, *, path: str, step_id: str) -> Any:
    """Applies one dotted path segment (optionally with `[N]` index
    suffixes) to *current*, navigating into the actual returned data —
    this is unrelated to picking *which operation* in a multi-op step
    (that's done by explicit `id`, never by index; see _resolve_ref)."""
    match = _PATH_SEGMENT_RE.match(segment)
    if not match:
        raise PlanRefError(f"$from path '{path}': malformed path segment '{segment}'.")
    key, brackets = match.group(1), match.group(2)

    if not isinstance(current, dict) or key not in current:
        raise PlanRefError(
            f"$from path '{path}': key '{key}' not found in step '{step_id}' result."
        )
    current = current[key]

    for idx_str in re.findall(r"\[(\d+)\]", brackets):
        idx = int(idx_str)
        if not isinstance(current, list) or idx >= len(current):
            raise PlanRefError(
                f"$from path '{path}': index [{idx}] out of range at '{key}' "
                f"in step '{step_id}' result."
            )
        current = current[idx]

    return current


def _resolve_ref(step_id: str, path: str, plan: Plan) -> Any:
    """Resolves a single `$from` reference against a completed step's
    result, as shaped by Planner._execute_step:
    ``{"<service>": {"success": bool, "result": [<op entry>, ...]} | {"success": False, "error": {...}}}``
    """
    ref_step = next((s for s in plan.steps if s.id == step_id), None)
    if ref_step is None:
        raise PlanRefError(f"$from references unknown step '{step_id}'.")
    if ref_step.status != StepStatus.COMPLETED:
        raise PlanRefError(
            f"$from references step '{step_id}' which has not completed "
            f"(status='{ref_step.status.value}')."
        )

    segments = path.split(".")
    if not segments or not segments[0]:
        raise PlanRefError(f"$from path '{path}': must start with a service name.")

    service_name, remaining = segments[0], segments[1:]
    if not isinstance(ref_step.result, dict) or service_name not in ref_step.result:
        available = sorted(ref_step.result) if isinstance(ref_step.result, dict) else []
        raise PlanRefError(
            f"$from path '{path}': step '{step_id}' has no result for service "
            f"'{service_name}'. Services called in that step: {available or 'none'}."
        )

    service_result = ref_step.result[service_name]
    if not service_result.get("success"):
        raise PlanRefError(
            f"$from path '{path}': service '{service_name}' in step '{step_id}' "
            "did not succeed, so its result can't be referenced."
        )

    entries = service_result.get("result")
    if not isinstance(entries, list):
        raise PlanRefError(
            f"$from path '{path}': unexpected result shape for service "
            f"'{service_name}' in step '{step_id}'."
        )

    if len(entries) == 1:
        # Single operation for this service in this step — auto-unwrap,
        # no `id` segment needed.
        entry = entries[0]
    else:
        if not remaining:
            raise PlanRefError(
                f"$from path '{path}': step '{step_id}' called {len(entries)} "
                f"operations on '{service_name}'; specify which one by its "
                f"explicit 'id', e.g. '{service_name}.<op_id>.result...'."
            )
        op_id, remaining = remaining[0], remaining[1:]
        entry = next((e for e in entries if e.get("id") == op_id), None)
        if entry is None:
            available_ids = [e.get("id") for e in entries if e.get("id")]
            raise PlanRefError(
                f"$from path '{path}': no operation with id '{op_id}' in step "
                f"'{step_id}'/'{service_name}'. Available ids: "
                f"{available_ids or 'none (give the ops an explicit id first)'}."
            )

    current: Any = entry
    for segment in remaining:
        current = _navigate_segment(current, segment, path=path, step_id=step_id)
    return current


def _resolve_refs(value: Any, plan: Plan) -> Any:
    """Recursively resolves every `$from` marker inside *value* (a
    StepOperation.args dict, typically) against already-completed steps
    in *plan*. Not Turing-complete: a single reference-lookup mechanism,
    no arithmetic or conditionals embedded in it (same criterion as `when`)."""
    if isinstance(value, dict):
        if set(value.keys()) == {"$from", "path"}:
            step_id, path = value["$from"], value["path"]
            if not isinstance(step_id, str) or not isinstance(path, str):
                raise PlanRefError("'$from' must be a step id (str) and 'path' a string.")
            return _resolve_ref(step_id, path, plan)
        return {k: _resolve_refs(v, plan) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, plan) for v in value]
    return value


# ---------------------------------------------------------------------------
# Dependency Graph
# ---------------------------------------------------------------------------


class ServiceDependency(BaseModel):
    """Declares that `source` service depends on `target` service."""

    source: str = Field(description="Service that depends on another")
    target: str = Field(description="Service depended upon")
    reason: str = Field(default="", description="Why this dependency exists")


class ServiceDependencyGraph(BaseModel):
    """Optional graph of inter-service dependencies.

    When provided, the planner validates that step execution order
    respects these constraints. When absent, the agent decides freely.
    """

    dependencies: list[ServiceDependency] = Field(default_factory=list)


class DependencyValidator:
    """Validates plan execution order against a dependency graph."""

    def __init__(self, graph: ServiceDependencyGraph | None = None) -> None:
        self._graph = graph

    def validate_order(self, steps: list[Step]) -> list[str] | None:
        """Validate (and, when a graph is set, auto-derive) step order.

        - If a dependency graph is present: for every declared
          `ServiceDependency(source, target)`, every step touching
          `source` gets `target`'s steps auto-added to its `depends_on`
          (if not already there). This is additive/idempotent — steps
          that already declare the right `depends_on` explicitly are
          untouched, steps that contradict it (see below) get caught by
          the cycle check.
        - Always (graph or not): the resulting `depends_on` graph is
          checked for cycles. A cycle from an explicit `depends_on` that
          contradicts an auto-derived edge is reported the same way as
          any other cycle — before this, a circular `depends_on` would
          pass validation silently and hang execute_plan's dependency
          loop forever, since nothing would ever get added to `completed`.

        Returns None if valid, or a list of error messages.
        """
        errors: list[str] = []

        if self._graph is not None:
            service_steps: dict[str, list[str]] = {}
            for step in steps:
                for op in step.operations:
                    service_steps.setdefault(op.service, []).append(step.id)
            step_by_id = {s.id: s for s in steps}

            for dep in self._graph.dependencies:
                for source_id in service_steps.get(dep.source, []):
                    for target_id in service_steps.get(dep.target, []):
                        if source_id == target_id:
                            continue
                        source_step = step_by_id[source_id]
                        if target_id not in source_step.depends_on:
                            source_step.depends_on.append(target_id)

        cycle = self._find_cycle(steps)
        if cycle:
            errors.append(
                "Circular dependency detected among steps: "
                + " -> ".join(cycle)
                + ". If a service dependency graph is set, check whether an "
                "explicit `depends_on` contradicts it."
            )

        return errors if errors else None

    @staticmethod
    def _find_cycle(steps: list[Step]) -> list[str] | None:
        """DFS-based cycle detection over `Step.depends_on`. Returns the
        cycle as a list of step ids if one exists, else None. Dangling
        `depends_on` ids (referencing a step not in this plan) are
        skipped here — that's a separate, earlier check in create_plan."""
        depends_on_by_id = {s.id: s.depends_on for s in steps}
        UNVISITED, IN_PROGRESS, DONE = 0, 1, 2
        state: dict[str, int] = {s.id: UNVISITED for s in steps}
        path: list[str] = []

        def visit(node: str) -> list[str] | None:
            state[node] = IN_PROGRESS
            path.append(node)
            for dep_id in depends_on_by_id.get(node, []):
                if dep_id not in state:
                    continue  # dangling ref, validated elsewhere
                if state[dep_id] == IN_PROGRESS:
                    cycle_start = path.index(dep_id)
                    return path[cycle_start:] + [dep_id]
                if state[dep_id] == UNVISITED:
                    found = visit(dep_id)
                    if found:
                        return found
            path.pop()
            state[node] = DONE
            return None

        for step in steps:
            if state[step.id] == UNVISITED:
                found = visit(step.id)
                if found:
                    return found
        return None

    def get_next_executable(
        self, steps: list[Step], completed: set[str]
    ) -> list[Step]:
        """Return steps whose dependencies are all satisfied."""
        executable: list[Step] = []
        for step in steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(dep in completed for dep in step.depends_on):
                executable.append(step)
        return executable


# ---------------------------------------------------------------------------
# Streaming Events
# ---------------------------------------------------------------------------


class PlanEventType(str, Enum):
    """Types of plan lifecycle events."""

    PLAN_CREATED = "plan_created"
    STEP_UPDATED = "step_updated"
    PLAN_COMPLETED = "plan_completed"
    PLAN_FAILED = "plan_failed"


class PlanEvent(BaseModel):
    """An event emitted during plan lifecycle for streaming to UIs."""

    type: PlanEventType
    plan_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)


class PlanEventHandler(Protocol):
    """Protocol for handlers that consume plan events.

    Supports two patterns:
    - Simple: ``async def on_plan_event(self, event) -> None``
    - Streaming: ``async def on_plan_event(self, event) -> AsyncIterator[Any]``
      (yields ag_ui state events or other payloads)
    """

    async def on_plan_event(self, event: PlanEvent) -> Any: ...


class JSONPatchOp(BaseModel):
    """JSON Patch operation (RFC 6902) for incremental state updates."""

    op: Literal["add", "remove", "replace"]
    path: str
    value: Any = None


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class Planner:
    """Cross-service planner that wraps a ToToolManager.

    Creates plans with steps that reference operations across services,
    validates execution order, and emits events for streaming.

    Usage::

        planner = manager.with_planner(dependency_graph=graph)
        plan = await planner.create_plan([
            Step(description="Create user", operations=[
                StepOperation(service="User", method="create_user", args={"user_name": "David"})
            ]),
        ])
        result = await planner.execute_plan(plan.id)

    Or, built with the fluent `PlanBuilder` (R6, sugar over the same
    `Step`/`StepOperation` model — no separate execution engine)::

        steps = (
            PlanBuilder()
            .step("Create user").op("User", "create_user", {"name": "David"})
            .step("Create order").op("Order", "create", {"user_id": {"$from": "step0", "path": "User.result.id"}})
            .depends_on("step0")
            .build()
        )
        plan = await planner.create_plan(steps)

    `state_type` (R5) is optional and purely additive: without it,
    everything behaves exactly as before. With it, steps can set
    `state_field` to say which field of that model their result maps to,
    and `get_state(plan_id)` returns a validated instance built from
    whichever steps completed — a typed, ergonomic snapshot for code that
    consumes the finished plan. It doesn't change how steps read each
    other's data *during* execution — that's still `$from` (R1).
    """

    def __init__(
        self,
        manager: ToToolManager,
        dependency_graph: ServiceDependencyGraph | None = None,
        state_type: type[BaseModel] | None = None,
    ) -> None:
        self._manager = manager
        self._validator = DependencyValidator(dependency_graph)
        self._plans: dict[str, Plan] = {}
        self._handlers: list[PlanEventHandler] = []
        self._state_type = state_type

    @property
    def manager(self) -> ToToolManager:
        """Access the underlying ToToolManager."""
        return self._manager

    @staticmethod
    def builder() -> "PlanBuilder":
        """Shorthand for `PlanBuilder()` (R6)."""
        return PlanBuilder()

    def get_state(self, plan_id: str) -> BaseModel:
        """Build a validated `state_type` instance from this plan's
        completed steps (R5). Raises if this planner has no `state_type`
        configured, or if `state_type` validation fails (e.g. a required
        field's step hasn't completed yet)."""
        if self._state_type is None:
            raise ValueError(
                "This planner has no state_type configured — pass "
                "state_type=... to with_planner()/Planner() to use get_state()."
            )
        plan = self._plans[plan_id]
        values: dict[str, Any] = {}
        for step in plan.steps:
            if not step.state_field or step.status != StepStatus.COMPLETED:
                continue
            values[step.state_field] = _step_state_value(step)
        return self._state_type(**values)

    def add_handler(self, handler: PlanEventHandler) -> None:
        """Register an event handler for plan lifecycle events."""
        self._handlers.append(handler)

    async def _emit(self, event: PlanEvent) -> None:
        for handler in self._handlers:
            method = handler.on_plan_event
            # Check if the handler is an async generator (streaming pattern)
            # vs a regular async method (simple pattern)
            if inspect.isasyncgenfunction(method):
                async for _ in method(event):
                    pass
            else:
                await method(event)

    async def create_plan(self, steps: list[Step]) -> Plan:
        """Create a new plan: validate references, derive dependencies,
        validate order, and validate against the manager's tool specs —
        all before anything executes.

        - A step's `condition.op` (if set) is auto-added to its
          `depends_on` so execution order is always safe (R2).
        - Every `$from` reference is checked against known step ids
          upfront — a typo'd or forward step id fails at create_plan,
          not mid-execution (R1).
        - Every explicit `depends_on` id must reference a real step.
        - If a `ServiceDependencyGraph` was passed to `with_planner`,
          `depends_on` is auto-derived from it for steps that weren't
          explicit; the resulting graph (explicit + derived) is checked
          for cycles (R3).
        - `service`/`method` on every operation are validated against
          `manager.tool_specs` (R4) — a typo surfaces here, not as a
          generic exception buried inside execute_plan's asyncio.gather.
        """
        step_ids = {s.id for s in steps}

        for step in steps:
            if step.condition is not None:
                op_ref = step.condition.get("op") if isinstance(step.condition, dict) else None
                if not isinstance(op_ref, str):
                    raise ValueError(
                        f"Step '{step.id}': condition must be an object with a string 'op'."
                    )
                if op_ref not in step_ids:
                    raise ValueError(
                        f"Step '{step.id}': condition references unknown step '{op_ref}'."
                    )
                if op_ref not in step.depends_on:
                    step.depends_on.append(op_ref)

        for step in steps:
            for op in step.operations:
                for ref_step_id, _path in _scan_from_refs(op.args):
                    if not isinstance(ref_step_id, str) or ref_step_id not in step_ids:
                        raise ValueError(
                            f"Step '{step.id}': operation on '{op.service}' has a "
                            f"'$from' reference to unknown step '{ref_step_id}'."
                        )
                    if ref_step_id not in step.depends_on:
                        step.depends_on.append(ref_step_id)

        for step in steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise ValueError(
                        f"Step '{step.id}': depends_on references unknown step '{dep_id}'."
                    )

        if self._state_type is not None:
            valid_fields = set(self._state_type.model_fields)
            for step in steps:
                if step.state_field is not None and step.state_field not in valid_fields:
                    raise ValueError(
                        f"Step '{step.id}': state_field '{step.state_field}' is not a "
                        f"field of {self._state_type.__name__}. Valid fields: "
                        f"{', '.join(sorted(valid_fields)) or 'none'}."
                    )

        errors = self._validator.validate_order(steps)
        if errors:
            raise ValueError(f"Invalid plan order: {'; '.join(errors)}")

        # R4 — validate service/method exist upfront, with the info
        # manager.tool_specs already exposes, instead of letting a typo
        # surface only inside asyncio.gather as a generic exception once
        # execute_plan is already running.
        for step in steps:
            for op in step.operations:
                try:
                    tool_spec = self._find_tool_spec(op.service)
                except ValueError as exc:
                    raise ValueError(f"Step '{step.id}': {exc}") from exc
                method_names = {o.name for o in tool_spec.operations}
                if op.method not in method_names:
                    raise ValueError(
                        f"Step '{step.id}': method '{op.method}' not found on "
                        f"service '{op.service}'. Available methods: "
                        f"{', '.join(sorted(method_names)) or 'none'}."
                    )

        plan = Plan(steps=steps)
        self._plans[plan.id] = plan

        await self._emit(
            PlanEvent(
                type=PlanEventType.PLAN_CREATED,
                plan_id=plan.id,
                data={"steps": [s.model_dump() for s in steps]},
            )
        )

        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        """Retrieve a plan by id."""
        return self._plans.get(plan_id)

    async def update_step(
        self,
        plan_id: str,
        step_id: str,
        *,
        status: StepStatus | None = None,
        result: Any = None,
        error: str | None = None,
    ) -> Step | None:
        """Manually update a step's status/result."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return None

        for step in plan.steps:
            if step.id == step_id:
                if status is not None:
                    step.status = status
                if result is not None:
                    step.result = result
                if error is not None:
                    step.error = error

                await self._emit(
                    PlanEvent(
                        type=PlanEventType.STEP_UPDATED,
                        plan_id=plan_id,
                        data={"step": step.model_dump()},
                    )
                )
                return step

        return None

    async def execute_plan(self, plan_id: str) -> Plan:
        """Execute all pending steps in dependency order.

        Independent steps run in parallel. Dependent steps wait for
        their dependencies to complete first.
        """
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan '{plan_id}' not found")

        completed_ids: set[str] = {
            s.id
            for s in plan.steps
            if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
        }

        while True:
            next_steps = self._validator.get_next_executable(plan.steps, completed_ids)
            if not next_steps:
                break

            # Gate each candidate step on its `condition` (R2) before it
            # ever reaches execution. The referenced step is guaranteed to
            # already be completed/skipped/failed here because create_plan
            # auto-added it to depends_on.
            runnable_steps: list[Step] = []
            outcomes = self._step_outcomes(plan)
            for step in next_steps:
                if step.condition is not None:
                    reason = _evaluate_when(step.condition, outcomes)
                    if reason is not None:
                        step.status = StepStatus.SKIPPED
                        step.result = {"skipped": True, "reason": reason}
                        await self._emit(
                            PlanEvent(
                                type=PlanEventType.STEP_UPDATED,
                                plan_id=plan.id,
                                data={"step": step.model_dump()},
                            )
                        )
                        completed_ids.add(step.id)
                        continue
                runnable_steps.append(step)

            if not runnable_steps:
                # Some steps were skipped above; loop again — that may
                # unblock further steps even if nothing executed this round.
                continue

            tasks = [self._execute_step(plan.id, step) for step in runnable_steps]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(runnable_steps, results):
                if isinstance(result, Exception):
                    step.status = StepStatus.FAILED
                    step.error = str(result)
                completed_ids.add(step.id)

        all_done = all(
            s.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in plan.steps
        )
        if all_done:
            any_failed = any(s.status == StepStatus.FAILED for s in plan.steps)
            await self._emit(
                PlanEvent(
                    type=(
                        PlanEventType.PLAN_FAILED
                        if any_failed
                        else PlanEventType.PLAN_COMPLETED
                    ),
                    plan_id=plan.id,
                    data={"steps": [s.model_dump() for s in plan.steps]},
                )
            )

        return plan

    @staticmethod
    def _step_outcomes(plan: Plan) -> dict[str, dict[str, Any]]:
        """Builds a `resolved_by_ref`-shaped dict from step statuses/results,
        so `Step.condition` can be evaluated by the exact same
        `_evaluate_when` used for operation-level `when` clauses."""
        outcomes: dict[str, dict[str, Any]] = {}
        for s in plan.steps:
            if s.status == StepStatus.SKIPPED:
                outcomes[s.id] = {"success": False, "skipped": True}
            elif s.status in (StepStatus.COMPLETED, StepStatus.FAILED):
                categories: set[str] = set()
                if isinstance(s.result, dict):
                    for svc_result in s.result.values():
                        if isinstance(svc_result, dict) and svc_result.get("success") is False:
                            cats = (svc_result.get("error") or {}).get("category")
                            if isinstance(cats, str):
                                categories.add(cats)
                            elif isinstance(cats, (list, tuple, set, frozenset)):
                                categories.update(cats)
                outcomes[s.id] = {
                    "success": s.status == StepStatus.COMPLETED,
                    "error": {"category": sorted(categories) if categories else None, "message": s.error},
                }
            # PENDING/IN_PROGRESS steps are intentionally omitted — a
            # condition referencing one is unreachable because create_plan
            # already forced it into depends_on.
        return outcomes

    async def _execute_step(self, plan_id: str, step: Step) -> Any:
        """Execute a single step by batching operations per service."""
        step.status = StepStatus.IN_PROGRESS

        await self._emit(
            PlanEvent(
                type=PlanEventType.STEP_UPDATED,
                plan_id=plan_id,
                data={"step": step.model_dump()},
            )
        )

        plan = self._plans[plan_id]

        ops_by_service: dict[str, list[dict[str, Any]]] = {}
        for op in step.operations:
            # $from resolution happens here, before ops_by_service is built,
            # so the rest of _execute_step (and ToToolManager/ToolSpec below
            # it) never finds out a reference was involved. A PlanRefError
            # here propagates like any other exception raised inside this
            # coroutine — caught by execute_plan's asyncio.gather and turned
            # into a FAILED step with the error message, same as today.
            resolved_args = _resolve_refs(op.args, plan)
            ops_by_service.setdefault(op.service, []).append(
                {
                    "method": op.method,
                    "args": resolved_args,
                    **({"id": op.id} if op.id else {}),
                }
            )

        results: dict[str, Any] = {}
        for service_name, operations in ops_by_service.items():
            tool_spec = self._find_tool_spec(service_name)
            response = await tool_spec.call(operations=operations)
            if response.error is not None:
                results[service_name] = {
                    "success": False,
                    "error": {
                        "category": sorted(response.error.category)
                        if response.error.category
                        else None,
                        "message": response.error.message,
                    },
                }
            else:
                results[service_name] = {"success": True, "result": response.content}

        step.status = StepStatus.COMPLETED
        step.result = results

        await self._emit(
            PlanEvent(
                type=PlanEventType.STEP_UPDATED,
                plan_id=plan_id,
                data={"step": step.model_dump()},
            )
        )

        return results

    def _find_tool_spec(self, service_name: str) -> ToolSpec:
        for spec in self._manager.tool_specs:
            if spec.name == service_name or spec.service_name == service_name:
                return spec
        available = [spec.name for spec in self._manager.tool_specs]
        raise ValueError(
            f"Service '{service_name}' not found. Available: {', '.join(sorted(available))}."
        )

    # -------------------------------------------------------------------
    # Agent-facing tools
    # -------------------------------------------------------------------

    def build_tools(self) -> list[dict[str, Any]]:
        """Build tool functions for the agent to call.

        Returns a list of dicts with 'func', 'name', and 'description'
        keys, suitable for passing to an adapter.
        """
        return [
            {
                "func": self._create_plan_tool(),
                "name": "create_plan",
                "description": (
                    "Create an execution plan with multiple steps. Each step "
                    "contains operations across services. Returns the plan id."
                ),
            },
            {
                "func": self._execute_plan_tool(),
                "name": "execute_plan",
                "description": (
                    "Execute a previously created plan. Runs steps in "
                    "dependency order, batching independent steps in parallel."
                ),
            },
            {
                "func": self._update_step_tool(),
                "name": "update_plan_step",
                "description": (
                    "Update the status or result of a specific step in a plan."
                ),
            },
            {
                "func": self._get_plan_tool(),
                "name": "get_plan",
                "description": "Retrieve the current state of a plan.",
            },
        ]

    def _create_plan_tool(self) -> Any:
        planner = self

        async def create_plan(
            steps: list[dict[str, Any]],
        ) -> str:
            """Create a plan with multiple steps.

            Args:
                steps: List of step objects, each with:
                    - description: What the step does
                    - operations: List of {service, method, args, id?} objects.
                      An arg value can be {"$from": <step_id>, "path": "..."}
                      to use another step's result instead of a literal —
                      e.g. {"user_id": {"$from": "step1", "path": "User.result.id"}}.
                      If that step called more than one operation on the same
                      service, add the op's explicit "id" to the path:
                      "User.<op_id>.result.id".
                    - depends_on: Optional list of step ids this depends on
                    - condition: Optional {"op": <step_id>, "outcome":
                      "success"|"error", "category"?: <str|list>} — if unmet,
                      this step is skipped (not run) instead of failing the plan.
            """
            plan_steps = [
                Step(
                    description=s["description"],
                    operations=[StepOperation(**op) for op in s.get("operations", [])],
                    depends_on=s.get("depends_on", []),
                    condition=s.get("condition"),
                )
                for s in steps
            ]
            plan = await planner.create_plan(plan_steps)
            return json.dumps(
                {"plan_id": plan.id, "steps": [s.model_dump() for s in plan.steps]},
                default=str,
            )

        return create_plan

    def _execute_plan_tool(self) -> Any:
        planner = self

        async def execute_plan(plan_id: str) -> str:
            """Execute a plan by id.

            Args:
                plan_id: The id of the plan to execute.
            """
            plan = await planner.execute_plan(plan_id)
            return json.dumps(plan.model_dump(), default=str)

        return execute_plan

    def _update_step_tool(self) -> Any:
        planner = self

        async def update_plan_step(
            plan_id: str,
            step_id: str,
            status: str | None = None,
            result: Any = None,
            error: str | None = None,
        ) -> str:
            """Update a step in a plan.

            Args:
                plan_id: The plan id.
                step_id: The step id to update.
                status: New status (pending, in_progress, completed, failed, skipped).
                result: Result data to attach to the step.
                error: Error message if the step failed.
            """
            step_status = StepStatus(status) if status else None
            step = await planner.update_step(
                plan_id, step_id, status=step_status, result=result, error=error
            )
            if step is None:
                return json.dumps({"error": f"Plan '{plan_id}' or step '{step_id}' not found"})
            return json.dumps(step.model_dump(), default=str)

        return update_plan_step

    def _get_plan_tool(self) -> Any:
        planner = self

        async def get_plan(plan_id: str) -> str:
            """Get the current state of a plan.

            Args:
                plan_id: The plan id to retrieve.
            """
            plan = planner.get_plan(plan_id)
            if plan is None:
                return json.dumps({"error": f"Plan '{plan_id}' not found"})
            return json.dumps(plan.model_dump(), default=str)

        return get_plan


# ---------------------------------------------------------------------------
# PlanBuilder (R6) — fluent sugar over Step/StepOperation, no new engine
# ---------------------------------------------------------------------------


class PlanBuilder:
    """Fluent builder for plans defined in code (as opposed to by an LLM).

    Compiles to a plain `list[Step]` — the same model `create_plan`
    already validates and `execute_plan` already runs. This is sugar,
    not a parallel execution engine: covers the same use case as
    `StateGraph.add_node/add_edge/.compile()` from the earlier design,
    without duplicating `execute_plan`.

    Usage::

        steps = (
            PlanBuilder()
            .step("Create user", id="s_user")
                .op("User", "create_user", {"name": "David"})
            .step("Create order", id="s_order")
                .op("Order", "create", {
                    "user_id": {"$from": "s_user", "path": "User.result.id"},
                    "item": "Widget",
                })
                .depends_on("s_user")
            .step("Notify on failure")
                .op("Order", "notify_failure", {})
                .when({"op": "s_order", "outcome": "error"})
            .build()
        )
        plan = await planner.create_plan(steps)

    Or, skip the extra `create_plan` call with `.create(planner)`::

        plan = await PlanBuilder().step(...).op(...).create(planner)
    """

    def __init__(self) -> None:
        self._steps: list[Step] = []

    def step(
        self,
        description: str,
        *,
        id: str | None = None,
        state_field: str | None = None,
    ) -> "PlanBuilder":
        """Starts a new step. Chain `.op(...)`, `.depends_on(...)`, and
        `.when(...)` right after to configure it — they always apply to
        the most recently added step."""
        step = Step(
            id=id or uuid4().hex[:8],
            description=description,
            state_field=state_field,
        )
        self._steps.append(step)
        return self

    def op(
        self,
        service: str,
        method: str,
        args: dict[str, Any] | None = None,
        *,
        id: str | None = None,
    ) -> "PlanBuilder":
        """Adds an operation to the step most recently added via `.step(...)`."""
        if not self._steps:
            raise ValueError("PlanBuilder: call .step(...) before .op(...).")
        self._steps[-1].operations.append(
            StepOperation(service=service, method=method, args=args or {}, id=id)
        )
        return self

    def depends_on(self, *step_ids: str) -> "PlanBuilder":
        """Adds dependencies to the step most recently added via `.step(...)`."""
        if not self._steps:
            raise ValueError("PlanBuilder: call .step(...) before .depends_on(...).")
        current = self._steps[-1]
        for sid in step_ids:
            if sid not in current.depends_on:
                current.depends_on.append(sid)
        return self

    def when(self, condition: dict[str, Any]) -> "PlanBuilder":
        """Sets `condition` on the step most recently added via `.step(...)`."""
        if not self._steps:
            raise ValueError("PlanBuilder: call .step(...) before .when(...).")
        self._steps[-1].condition = condition
        return self

    def build(self) -> list[Step]:
        """Returns the compiled steps. Pass straight to `planner.create_plan(...)`.

        Deliberately returns `list[Step]`, not a `Plan` — assigning the
        plan id and running R1-R4 validation both live in
        `Planner.create_plan`, and duplicating that here would be exactly
        the "two systems that don't talk to each other" problem this
        whole effort exists to avoid.
        """
        return list(self._steps)

    async def create(self, planner: "Planner") -> Plan:
        """Convenience: `await planner.create_plan(self.build())`. This is
        the actual analog of `StateGraph.compile()` — all the real logic
        stays in `Planner.create_plan`, nothing new happens here."""
        return await planner.create_plan(self.build())


# ---------------------------------------------------------------------------
# R8 — complexity heuristic for planning_mode="gated"
# ---------------------------------------------------------------------------

_MULTI_STEP_CONNECTORS = (
    # Spanish
    "y luego", "y despues", "y tambien", "y ademas", "despues de",
    "una vez que", "si falla", "si no", "en caso de", "antes de",
    # English
    "and then", "after that", "once done", "also", "as well as",
    "if it fails", "in case", "before that",
)


def _normalize_for_heuristic(text: str) -> str:
    """Lowercase + strip accents, so 'después'/'despues' and similar
    variants match the same connector regardless of how the request
    typed them."""
    text = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def request_looks_complex(
    prompt: str,
    service_names: Sequence[str],
    *,
    word_threshold: int = 25,
) -> bool:
    """Zero-inference-cost heuristic for `planning_mode="gated"` (R8).

    Decides, from the request text ALONE (no model call — this must stay
    free, it runs on every turn), whether it's worth exposing
    `create_plan`/`execute_plan` as real tools for this turn, or whether a
    lightweight prompt reminder is enough instead. Never forces
    plan-then-execute regardless of the query — that's the antipattern
    this heuristic exists to avoid (same one already ruled out for
    sub-agents).

    Signals (needs >= 2 to call a request "complex" — a single incidental
    match isn't enough on its own, to keep false positives low):
    - Two or more distinct registered services/modules mentioned by name.
      Best-effort only: if the request is in a language where service
      class names don't appear literally (e.g. "orden" vs. "Order"),
      this signal just doesn't fire — the other two can still.
    - A long and/or structured request: >= word_threshold words, OR a
      numbered/bulleted list, OR 3+ sentences.
    - A multi-step connector phrase ("y luego", "and then", "si falla", ...).

    Returns True ("complex") or False ("simple"). Pure function, no I/O,
    no side effects — safe to call on every turn.
    """
    if not prompt or not prompt.strip():
        return False

    normalized = _normalize_for_heuristic(prompt)
    score = 0

    mentioned = {name for name in service_names if _normalize_for_heuristic(name) in normalized}
    if len(mentioned) >= 2:
        score += 1

    words = normalized.split()
    has_list_markers = bool(re.search(r"(^|\n)\s*(-|\*|\d+[.)])\s", prompt))
    sentence_count = len([s for s in re.split(r"[.;\n]", prompt) if s.strip()])
    if len(words) >= word_threshold or has_list_markers or sentence_count >= 3:
        score += 1

    if any(connector in normalized for connector in _MULTI_STEP_CONNECTORS):
        score += 1
    connector_matches = sum(1 for connector in _MULTI_STEP_CONNECTORS if connector in normalized)
    if connector_matches >= 2:
        # two distinct sequencing/conditional cues (e.g. "y después" AND "si
        # falla") describe a multi-step, branching request on their own,
        # even in an otherwise short message.
        score += 1

    return score >= 2
