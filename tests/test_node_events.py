"""Tests for node event emission helpers."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from store.models import Event
from agent.node_events import emit_status, emit_node_event, flush_node


@pytest.fixture
def mock_config():
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()
    event_bus.flush_node_boundary = AsyncMock()
    return {
        "configurable": {
            "event_bus": event_bus,
            "project_id": "proj-1",
            "run_id": "run-1",
        }
    }


@pytest.mark.asyncio
async def test_emit_status_sends_status_event(mock_config):
    await emit_status(mock_config, "planner", "Planning edits...")
    event_bus = mock_config["configurable"]["event_bus"]
    event_bus.emit.assert_called_once()
    event: Event = event_bus.emit.call_args[0][0]
    assert event.type == "status"
    assert event.node == "planner"
    assert event.data == {"message": "Planning edits..."}
    assert event.project_id == "proj-1"
    assert event.run_id == "run-1"


@pytest.mark.asyncio
async def test_emit_node_event_sends_custom_event(mock_config):
    await emit_node_event(mock_config, "editor", "diff", {"file_path": "app.py", "diff": "+hello"})
    event_bus = mock_config["configurable"]["event_bus"]
    event_bus.emit.assert_called_once()
    event: Event = event_bus.emit.call_args[0][0]
    assert event.type == "diff"
    assert event.node == "editor"
    assert event.data == {"file_path": "app.py", "diff": "+hello"}


@pytest.mark.asyncio
async def test_flush_node_calls_flush(mock_config):
    await flush_node(mock_config)
    event_bus = mock_config["configurable"]["event_bus"]
    event_bus.flush_node_boundary.assert_called_once_with("run-1")


@pytest.mark.asyncio
async def test_emit_status_noop_when_no_event_bus():
    config = {"configurable": {"run_id": "r1"}}
    # Should not raise
    await emit_status(config, "planner", "test")


@pytest.mark.asyncio
async def test_flush_node_noop_when_no_event_bus():
    config = {"configurable": {"run_id": "r1"}}
    await flush_node(config)
