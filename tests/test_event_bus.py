"""Tests for EventBus — priority routing, seq, persistence, replay, snapshot."""
import asyncio
import pytest
import pytest_asyncio
from store.sqlite import SQLiteSessionStore
from store.models import Event
from agent.events import EventBus


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def bus(store):
    b = EventBus(store)
    yield b
    await b.shutdown()


# --- seq assignment ---

@pytest.mark.asyncio
async def test_emit_assigns_sequential_seq(bus):
    e1 = Event(project_id="p1", run_id="r1", type="status")
    e2 = Event(project_id="p1", run_id="r1", type="diff")
    await bus.emit(e1)
    await bus.emit(e2)
    assert e1.seq == 1
    assert e2.seq == 2


@pytest.mark.asyncio
async def test_emit_seq_independent_per_run(bus):
    e1 = Event(project_id="p1", run_id="r1", type="status")
    e2 = Event(project_id="p1", run_id="r2", type="status")
    await bus.emit(e1)
    await bus.emit(e2)
    assert e1.seq == 1
    assert e2.seq == 1


@pytest.mark.asyncio
async def test_emit_resumes_seq_from_store(store):
    e = Event(project_id="p1", run_id="r1", type="status", seq=10)
    await store.append_event(e)
    bus = EventBus(store)
    new_event = Event(project_id="p1", run_id="r1", type="diff")
    await bus.emit(new_event)
    assert new_event.seq == 11
    await bus.shutdown()


# --- P0: immediate send + persist ---

@pytest.mark.asyncio
async def test_p0_events_sent_immediately(bus):
    sent = []
    async def callback(event): sent.append(event)
    bus.set_send_callback(callback)
    for t in ["approval", "error", "stop", "review"]:
        await bus.emit(Event(project_id="p1", run_id="r1", type=t))
    assert len(sent) == 4


@pytest.mark.asyncio
async def test_p0_events_persisted(bus, store):
    await bus.emit(Event(project_id="p1", run_id="r1", type="error", data={"msg": "fail"}))
    events = await store.replay_events("r1")
    assert len(events) == 1


# --- P1: batched send ---

@pytest.mark.asyncio
async def test_p1_stream_events_batched(bus):
    sent = []
    async def callback(event): sent.append(event)
    bus.set_send_callback(callback)
    bus.start_batcher()
    await bus.emit(Event(project_id="p1", run_id="r1", type="stream", data={"token": "hi"}))
    assert len(sent) == 0
    await asyncio.sleep(0.1)
    assert len(sent) == 1
    await bus.shutdown()


@pytest.mark.asyncio
async def test_p1_stream_not_persisted(bus, store):
    bus.start_batcher()
    await bus.emit(Event(project_id="p1", run_id="r1", type="stream", data={"token": "x"}))
    events = await store.replay_events("r1")
    assert len(events) == 0
    await bus.shutdown()


@pytest.mark.asyncio
async def test_p1_diff_persisted(bus, store):
    bus.start_batcher()
    await bus.emit(Event(project_id="p1", run_id="r1", type="diff", data={"file": "a.py"}))
    events = await store.replay_events("r1")
    assert len(events) == 1
    await bus.shutdown()


# --- P2: persist, send at boundary ---

@pytest.mark.asyncio
async def test_p2_events_persisted(bus, store):
    await bus.emit(Event(project_id="p1", run_id="r1", type="status", data={"step": 1}))
    events = await store.replay_events("r1")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_p2_events_not_sent_immediately(bus):
    sent = []
    async def callback(event): sent.append(event)
    bus.set_send_callback(callback)
    await bus.emit(Event(project_id="p1", run_id="r1", type="status"))
    assert len(sent) == 0


@pytest.mark.asyncio
async def test_flush_node_boundary_sends_p2(bus):
    sent = []
    async def callback(event): sent.append(event)
    bus.set_send_callback(callback)
    await bus.emit(Event(project_id="p1", run_id="r1", type="status"))
    await bus.emit(Event(project_id="p1", run_id="r1", type="file"))
    assert len(sent) == 0
    await bus.flush_node_boundary("r1")
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_flush_node_boundary_per_run(bus):
    """P2 flush only flushes the specified run's queue."""
    sent = []
    async def callback(event): sent.append(event)
    bus.set_send_callback(callback)
    await bus.emit(Event(project_id="p1", run_id="r1", type="status"))
    await bus.emit(Event(project_id="p1", run_id="r2", type="status"))
    await bus.flush_node_boundary("r1")
    assert len(sent) == 1
    assert sent[0].run_id == "r1"


# --- replay ---

@pytest.mark.asyncio
async def test_replay(bus, store):
    await bus.emit(Event(project_id="p1", run_id="r1", type="error"))
    await bus.emit(Event(project_id="p1", run_id="r1", type="status"))
    events = await bus.replay("r1", after_seq=0)
    assert len(events) == 2
    assert events[0].seq == 1


@pytest.mark.asyncio
async def test_replay_after_seq(bus, store):
    await bus.emit(Event(project_id="p1", run_id="r1", type="error"))
    await bus.emit(Event(project_id="p1", run_id="r1", type="status"))
    await bus.emit(Event(project_id="p1", run_id="r1", type="diff"))
    events = await bus.replay("r1", after_seq=2)
    assert len(events) == 1
    assert events[0].seq == 3


# --- snapshot (async, store-backed) ---

@pytest.mark.asyncio
async def test_get_snapshot(bus, store):
    await bus.emit(Event(project_id="p1", run_id="r1", type="error"))
    await bus.emit(Event(project_id="p1", run_id="r1", type="status"))
    snap = await bus.get_snapshot("r1")
    assert snap["type"] == "snapshot"
    assert snap["run_id"] == "r1"
    assert snap["last_seq"] == 2


@pytest.mark.asyncio
async def test_get_snapshot_empty_run(bus):
    snap = await bus.get_snapshot("nonexistent")
    assert snap["type"] == "snapshot"
    assert snap["last_seq"] == 0
    assert snap["status"] == "unknown"


# --- no callback ---

@pytest.mark.asyncio
async def test_emit_without_callback(bus):
    await bus.emit(Event(project_id="p1", run_id="r1", type="error"))  # no crash
