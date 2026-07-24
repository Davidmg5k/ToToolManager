"""
Adapter for ag_ui streaming of plan state.

Converts PlanEvents into ag_ui StateSnapshotEvent / StateDeltaEvent
for real-time UI updates. Only this module imports ag_ui.

Usage::

    from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

    planner = manager.with_planner()
    planner.add_handler(AGUIPlanHandler())
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from ag_ui.core import EventType, StateDeltaEvent, StateSnapshotEvent
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The ag_ui adapter requires the 'ag-ui-core' package. "
        "Install it with:\n"
        "    pip install ag-ui-core\n"
        "The core `to_tool_manager` package does not depend on it."
    ) from exc

from to_tool_manager.core.planner import (
    JSONPatchOp,
    PlanEvent,
    PlanEventType,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class AGUIPlanHandler:
    """Converts plan lifecycle events to ag_ui state events.

    Yields StateSnapshotEvent on plan creation and StateDeltaEvent
    on step updates, enabling real-time plan progress in ag_ui clients.
    """

    def __init__(self) -> None:
        self._last_snapshot: dict[str, Any] | None = None

    async def on_plan_event(self, event: PlanEvent) -> AsyncIterator[Any]:
        """Handle a plan event and yield ag_ui state events."""
        if event.type == PlanEventType.PLAN_CREATED:
            self._last_snapshot = event.data
            yield StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=event.data,
            )

        elif event.type == PlanEventType.STEP_UPDATED:
            step = event.data.get("step", {})
            step_id = step.get("id", "")
            status = step.get("status", "")

            patches = [
                JSONPatchOp(
                    op="replace",
                    path=f"/steps/{step_id}/status",
                    value=status,
                ).model_dump(),
            ]

            if "result" in step and step["result"] is not None:
                patches.append(
                    JSONPatchOp(
                        op="replace",
                        path=f"/steps/{step_id}/result",
                        value=step["result"],
                    ).model_dump(),
                )
            if "error" in step and step["error"] is not None:
                patches.append(
                    JSONPatchOp(
                        op="replace",
                        path=f"/steps/{step_id}/error",
                        value=step["error"],
                    ).model_dump(),
                )

            # Apply patches to local snapshot
            if self._last_snapshot is not None:
                self._apply_patches(self._last_snapshot, patches)

            yield StateDeltaEvent(
                type=EventType.STATE_DELTA,
                delta=patches,
            )

        elif event.type in (PlanEventType.PLAN_COMPLETED, PlanEventType.PLAN_FAILED):
            # Send full snapshot as completion
            if self._last_snapshot is not None:
                yield StateSnapshotEvent(
                    type=EventType.STATE_SNAPSHOT,
                    snapshot=self._last_snapshot,
                )

    @staticmethod
    def _apply_patches(snapshot: dict[str, Any], patches: list[dict[str, Any]]) -> None:
        """Apply JSON Patch operations to the snapshot in-place (simplified)."""
        for patch in patches:
            op = patch.get("op")
            path = patch.get("path", "")
            value = patch.get("value")

            if op == "replace" and path.startswith("/steps/"):
                parts = path.strip("/").split("/")
                if len(parts) >= 3 and parts[0] == "steps":
                    step_id = parts[1]
                    field_name = parts[2]
                    steps = snapshot.get("steps", [])
                    for step in steps:
                        if isinstance(step, dict) and step.get("id") == step_id:
                            step[field_name] = value
                            break
