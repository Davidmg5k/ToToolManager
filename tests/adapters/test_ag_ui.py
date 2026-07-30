import pytest

ag_ui = pytest.importorskip("ag_ui", reason="ag-ui-core not installed")

from to_tool_manager.core.planner import PlanEvent, PlanEventType


class TestAGUIPlanHandler:
    @pytest.mark.anyio
    async def test_plan_created_event(self):
        from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

        handler = AGUIPlanHandler()
        event = PlanEvent(
            type=PlanEventType.PLAN_CREATED,
            plan_id="test_plan",
            data={"steps": []},
        )
        events = []
        async for e in handler.on_plan_event(event):
            events.append(e)
        assert len(events) == 1
        assert events[0].type.value == "state_snapshot"

    @pytest.mark.anyio
    async def test_step_updated_event(self):
        from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

        handler = AGUIPlanHandler()
        handler._last_snapshot = {"steps": [{"id": "s1", "status": "pending"}]}
        event = PlanEvent(
            type=PlanEventType.STEP_UPDATED,
            plan_id="test_plan",
            data={"step": {"id": "s1", "status": "completed"}},
        )
        events = []
        async for e in handler.on_plan_event(event):
            events.append(e)
        assert len(events) == 1
        assert events[0].type.value == "state_delta"

    @pytest.mark.anyio
    async def test_plan_completed_event(self):
        from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

        handler = AGUIPlanHandler()
        handler._last_snapshot = {"steps": []}
        event = PlanEvent(
            type=PlanEventType.PLAN_COMPLETED,
            plan_id="test_plan",
            data={"steps": []},
        )
        events = []
        async for e in handler.on_plan_event(event):
            events.append(e)
        assert len(events) == 1
        assert events[0].type.value == "state_snapshot"

    @pytest.mark.anyio
    async def test_plan_failed_event(self):
        from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

        handler = AGUIPlanHandler()
        handler._last_snapshot = {"steps": []}
        event = PlanEvent(
            type=PlanEventType.PLAN_FAILED,
            plan_id="test_plan",
            data={"steps": []},
        )
        events = []
        async for e in handler.on_plan_event(event):
            events.append(e)
        assert len(events) == 1

    def test_apply_patches(self):
        from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

        snapshot = {"steps": [{"id": "s1", "status": "pending", "result": None}]}
        patches = [
            {"op": "replace", "path": "/steps/s1/status", "value": "completed"},
            {"op": "replace", "path": "/steps/s1/result", "value": {"done": True}},
        ]
        AGUIPlanHandler._apply_patches(snapshot, patches)
        assert snapshot["steps"][0]["status"] == "completed"
        assert snapshot["steps"][0]["result"] == {"done": True}

    def test_apply_patches_no_match(self):
        from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

        snapshot = {"steps": [{"id": "s1", "status": "pending"}]}
        patches = [{"op": "replace", "path": "/steps/s2/status", "value": "completed"}]
        AGUIPlanHandler._apply_patches(snapshot, patches)
        assert snapshot["steps"][0]["status"] == "pending"
