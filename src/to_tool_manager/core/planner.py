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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

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
    result: Any = Field(default=None, description="Execution result (set after completion)")
    error: str | None = Field(default=None, description="Error message if failed")


class Plan(BaseModel):
    """A plan containing multiple steps to execute across services."""

    id: str = Field(default_factory=lambda: uuid4().hex, description="Unique plan identifier")
    steps: list[Step] = Field(default_factory=list, description="Ordered list of steps")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


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
        """Validate that step order respects service dependencies.

        Returns None if valid, or a list of error messages.
        """
        if self._graph is None:
            return None

        service_steps: dict[str, list[str]] = {}
        for step in steps:
            for op in step.operations:
                service_steps.setdefault(op.service, []).append(step.id)

        errors: list[str] = []
        for dep in self._graph.dependencies:
            target_ids = service_steps.get(dep.target, [])
            source_ids = service_steps.get(dep.source, [])
            if not target_ids or not source_ids:
                continue

            max_target = max(i for i, s in enumerate(steps) if s.id in target_ids)
            min_source = min(i for i, s in enumerate(steps) if s.id in source_ids)
            if min_source < max_target:
                errors.append(
                    f"Service '{dep.source}' depends on '{dep.target}', "
                    f"but steps are ordered incorrectly."
                )

        return errors if errors else None

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
    """

    def __init__(
        self,
        manager: ToToolManager,
        dependency_graph: ServiceDependencyGraph | None = None,
    ) -> None:
        self._manager = manager
        self._validator = DependencyValidator(dependency_graph)
        self._plans: dict[str, Plan] = {}
        self._handlers: list[PlanEventHandler] = []

    @property
    def manager(self) -> ToToolManager:
        """Access the underlying ToToolManager."""
        return self._manager

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
        """Create a new plan and validate step order."""
        plan = Plan(steps=steps)

        errors = self._validator.validate_order(steps)
        if errors:
            raise ValueError(f"Invalid plan order: {'; '.join(errors)}")

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

            tasks = [self._execute_step(plan.id, step) for step in next_steps]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(next_steps, results):
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

        ops_by_service: dict[str, list[dict[str, Any]]] = {}
        for op in step.operations:
            ops_by_service.setdefault(op.service, []).append(
                {
                    "method": op.method,
                    "args": op.args,
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
                    - operations: List of {service, method, args} objects
                    - depends_on: Optional list of step ids this depends on
            """
            plan_steps = [
                Step(
                    description=s["description"],
                    operations=[StepOperation(**op) for op in s.get("operations", [])],
                    depends_on=s.get("depends_on", []),
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
