"""Tests for ConnectionManager."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from store.sqlite import SQLiteSessionStore
from store.models import Event
from agent.events import EventBus


@pytest_asyncio.fixture
async def store(tmp_path):
    s = SQLiteSessionStore(str(tmp_path / "test.db"))
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def bus(store):
    b = EventBus(store)
    yield b
    await b.shutdown()


@pytest_asyncio.fixture
def manager(bus):
    from server.websocket import ConnectionManager
    return ConnectionManager(bus)


def _mock_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_adds_connection(manager):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    assert "proj1" in manager._connections
    assert len(manager._connections["proj1"]) == 1


@pytest.mark.asyncio
async def test_disconnect_removes_connection(manager):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    await manager.disconnect(ws)
    conns = manager._connections.get("proj1", [])
    assert len(conns) == 0


@pytest.mark.asyncio
async def test_send_to_subscribed_uses_event_project_id(manager):
    """send_to_subscribed reads project_id from the event, not a param."""
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(project_id="proj1", run_id="r1", type="status", seq=1, data={"msg": "hi"})
    await manager.send_to_subscribed(event)  # NO project_id param

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "status"
    assert payload["seq"] == 1
    assert payload["model"] is None  # model field included even if None


@pytest.mark.asyncio
async def test_send_to_subscribed_includes_model(manager):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(project_id="proj1", run_id="r1", type="status", seq=1, model="o3")
    await manager.send_to_subscribed(event)
    payload = ws.send_json.call_args[0][0]
    assert payload["model"] == "o3"


@pytest.mark.asyncio
async def test_send_skips_unsubscribed_run(manager):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(project_id="proj1", run_id="r2", type="status", seq=1)
    await manager.send_to_subscribed(event)
    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_handle_subscribe(manager):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    await manager.handle_client_message(ws, {"action": "subscribe", "run_id": "r1"})
    state = manager._connections["proj1"][0]
    assert "r1" in state.subscribed_runs


@pytest.mark.asyncio
async def test_handle_reconnect_sends_snapshot_then_replay(manager, bus, store):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")

    # Pre-populate events
    e1 = Event(project_id="p1", run_id="r1", type="status", seq=1)
    e2 = Event(project_id="p1", run_id="r1", type="diff", seq=2)
    await store.append_event(e1)
    await store.append_event(e2)

    await manager.handle_client_message(ws, {"action": "reconnect", "run_id": "r1", "last_seq": 0})

    # First call = snapshot, then 2 replayed events = 3 total
    assert ws.send_json.call_count == 3
    first_msg = ws.send_json.call_args_list[0][0][0]
    assert first_msg["type"] == "snapshot"
    second_msg = ws.send_json.call_args_list[1][0][0]
    assert second_msg["type"] == "status"
    assert second_msg["seq"] == 1


@pytest.mark.asyncio
async def test_handle_approve_forwards_op_id(manager):
    calls = []
    async def on_approve(run_id, edit_id, op_id):
        calls.append((run_id, edit_id, op_id))
    manager.set_approve_callback(on_approve)

    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    await manager.handle_client_message(ws, {
        "action": "approve", "run_id": "r1", "edit_id": "e1", "op_id": "op_e1_approve"
    })
    assert calls == [("r1", "e1", "op_e1_approve")]


@pytest.mark.asyncio
async def test_broadcast_heartbeat(manager):
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    await manager.broadcast_heartbeat()
    ws.send_json.assert_called_once()
    assert ws.send_json.call_args[0][0]["type"] == "heartbeat"


@pytest.mark.asyncio
async def test_dead_connection_cleaned_up(manager):
    ws = _mock_ws()
    ws.send_json.side_effect = Exception("dead")
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(project_id="proj1", run_id="r1", type="error", seq=1)
    await manager.send_to_subscribed(event)
    assert len(manager._connections.get("proj1", [])) == 0
