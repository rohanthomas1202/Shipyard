"""Integration tests for the full WebSocket event bus pipeline."""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run, Event
from agent.events import EventBus
from server.websocket import ConnectionManager


@pytest_asyncio.fixture
async def stack(tmp_path):
    store = SQLiteSessionStore(str(tmp_path / "integration.db"))
    await store.initialize()
    project = Project(id="proj1", name="Integration", path="/tmp/int")
    await store.create_project(project)

    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)

    async def send_callback(event):
        await conn_manager.send_to_subscribed(event)
    event_bus.set_send_callback(send_callback)
    event_bus.start_batcher()

    yield store, event_bus, conn_manager
    await event_bus.shutdown()
    await store.close()


def _mock_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# 1. P0 event reaches client immediately
@pytest.mark.asyncio
async def test_p0_event_reaches_client(stack):
    store, event_bus, conn_manager = stack
    ws = _mock_ws()
    state = await conn_manager.connect(ws, "proj1")
    state.subscribed_runs.add("run1")

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="error", data={"msg": "fail"}))

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "error"
    assert payload["run_id"] == "run1"


# 2. P1 stream event reaches client after flush interval
@pytest.mark.asyncio
async def test_p1_stream_event_reaches_client_after_flush(stack):
    store, event_bus, conn_manager = stack
    ws = _mock_ws()
    state = await conn_manager.connect(ws, "proj1")
    state.subscribed_runs.add("run1")

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="stream", data={"token": "hello"}))

    # Not sent immediately
    ws.send_json.assert_not_called()

    # Arrives after batcher flush interval (50ms default + buffer)
    await asyncio.sleep(0.1)
    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "stream"


# 3. P1 stream event not persisted to store
@pytest.mark.asyncio
async def test_p1_stream_not_persisted(stack):
    store, event_bus, conn_manager = stack

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="stream", data={"token": "x"}))

    events = await store.replay_events("run1")
    assert len(events) == 0


# 4. P2 event sent only on node boundary flush
@pytest.mark.asyncio
async def test_p2_event_sent_on_boundary(stack):
    store, event_bus, conn_manager = stack
    ws = _mock_ws()
    state = await conn_manager.connect(ws, "proj1")
    state.subscribed_runs.add("run1")

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="status", data={"step": 1}))

    # Not sent yet
    ws.send_json.assert_not_called()

    await event_bus.flush_node_boundary("run1")

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "status"


# 5. P2 event persisted to store
@pytest.mark.asyncio
async def test_p2_event_persisted(stack):
    store, event_bus, conn_manager = stack

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="status", data={"step": 2}))

    events = await store.replay_events("run1")
    assert len(events) == 1
    assert events[0].type == "status"


# 6. Reconnect replays persisted events after last_seq
@pytest.mark.asyncio
async def test_reconnect_replays_persisted_events(stack):
    store, event_bus, conn_manager = stack

    # Emit 3 durable events (P0/P2)
    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="error"))   # seq=1
    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="status"))  # seq=2
    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="status"))  # seq=3

    # New client reconnects with last_seq=1
    ws2 = _mock_ws()
    await conn_manager.connect(ws2, "proj1")
    await conn_manager.handle_client_message(ws2, {"action": "reconnect", "run_id": "run1", "last_seq": 1})

    # First call is the snapshot; subsequent calls are replayed events (seq 2 and 3)
    call_args_list = ws2.send_json.call_args_list
    replayed_types = [call[0][0]["type"] for call in call_args_list[1:]]
    assert len(replayed_types) == 2


# 7. Reconnect gets snapshot first
@pytest.mark.asyncio
async def test_reconnect_gets_snapshot_first(stack):
    store, event_bus, conn_manager = stack

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="error"))
    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="status"))

    ws2 = _mock_ws()
    await conn_manager.connect(ws2, "proj1")
    await conn_manager.handle_client_message(ws2, {"action": "reconnect", "run_id": "run1", "last_seq": 0})

    first_payload = ws2.send_json.call_args_list[0][0][0]
    assert first_payload["type"] == "snapshot"


# 8. Seq numbers are monotonically increasing across different event types
@pytest.mark.asyncio
async def test_seq_monotonic_across_types(stack):
    store, event_bus, conn_manager = stack
    types = ["error", "stream", "status", "diff", "file"]
    events = [Event(project_id="proj1", run_id="run1", type=t) for t in types]

    for e in events:
        await event_bus.emit(e)

    seqs = [e.seq for e in events]
    assert seqs == [1, 2, 3, 4, 5]


# 9. Multiple runs have independent seq counters
@pytest.mark.asyncio
async def test_multiple_runs_independent_seq(stack):
    store, event_bus, conn_manager = stack

    e1 = Event(project_id="proj1", run_id="r1", type="status")
    e2 = Event(project_id="proj1", run_id="r2", type="status")

    await event_bus.emit(e1)
    await event_bus.emit(e2)

    assert e1.seq == 1
    assert e2.seq == 1


# 10. Dead connection is cleaned up after failed send
@pytest.mark.asyncio
async def test_dead_connection_cleaned_up(stack):
    store, event_bus, conn_manager = stack
    ws = _mock_ws()
    ws.send_json.side_effect = RuntimeError("connection closed")

    state = await conn_manager.connect(ws, "proj1")
    state.subscribed_runs.add("run1")

    assert len(conn_manager._connections.get("proj1", [])) == 1

    await event_bus.emit(Event(project_id="proj1", run_id="run1", type="error"))

    # Connection should be removed after send failure
    assert len(conn_manager._connections.get("proj1", [])) == 0


# 11. Heartbeat reaches all connected clients
@pytest.mark.asyncio
async def test_heartbeat_reaches_all_clients(stack):
    store, event_bus, conn_manager = stack
    ws1 = _mock_ws()
    ws2 = _mock_ws()

    await conn_manager.connect(ws1, "proj1")
    await conn_manager.connect(ws2, "proj1")

    await conn_manager.broadcast_heartbeat()

    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()

    hb1 = ws1.send_json.call_args[0][0]
    hb2 = ws2.send_json.call_args[0][0]
    assert hb1["type"] == "heartbeat"
    assert hb2["type"] == "heartbeat"
