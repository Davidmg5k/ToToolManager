import pytest
from datetime import datetime, timezone
from to_tool_manager.orchestrator.events import (
    OrchestratorEvent,
    OrchestratorEventHandler,
    OrchestratorEventType,
)


class TestOrchestratorEventType:
    def test_values(self):
        assert OrchestratorEventType.AGENT_ADDED == "agent_added"
        assert OrchestratorEventType.AGENT_REMOVED == "agent_removed"
        assert OrchestratorEventType.AGENT_INITIALIZED == "agent_initialized"
        assert OrchestratorEventType.ORCHESTRATOR_STARTED == "orchestrator_started"
        assert OrchestratorEventType.ORCHESTRATOR_STOPPED == "orchestrator_stopped"

    def test_all_types_are_strings(self):
        for event_type in OrchestratorEventType:
            assert isinstance(event_type.value, str)


class TestOrchestratorEvent:
    def test_creation(self):
        event = OrchestratorEvent(type=OrchestratorEventType.AGENT_ADDED)
        assert event.type == OrchestratorEventType.AGENT_ADDED
        assert event.data == {}

    def test_creation_with_data(self):
        data = {"agent_name": "test", "count": 1}
        event = OrchestratorEvent(type=OrchestratorEventType.AGENT_ADDED, data=data)
        assert event.data == data

    def test_timestamp_auto_set(self):
        before = datetime.now(timezone.utc)
        event = OrchestratorEvent(type=OrchestratorEventType.ORCHESTRATOR_STARTED)
        after = datetime.now(timezone.utc)
        assert before <= event.timestamp <= after

    def test_frozen(self):
        event = OrchestratorEvent(type=OrchestratorEventType.AGENT_ADDED)
        with pytest.raises(AttributeError):
            event.type = OrchestratorEventType.AGENT_REMOVED


class TestOrchestratorEventHandler:
    def test_valid_handler(self):
        class MyHandler:
            async def on_event(self, event: OrchestratorEvent) -> None:
                pass

        handler = MyHandler()
        assert isinstance(handler, OrchestratorEventHandler)

    def test_invalid_handler_no_on_event(self):
        class BadHandler:
            pass

        handler = BadHandler()
        assert not isinstance(handler, OrchestratorEventHandler)