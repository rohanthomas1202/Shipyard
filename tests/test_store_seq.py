"""Tests for seq and project_id fields on Event and related store methods."""
import pytest
import pytest_asyncio
from store.sqlite import SQLiteSessionStore
from store.models import Event


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test_seq.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_event_seq_defaults_to_zero():
    e = Event(project_id="proj1", run_id="r1", type="status")
    assert e.seq == 0


@pytest.mark.asyncio
async def test_event_has_project_id_field():
    e = Event(project_id="proj1", run_id="r1", type="status")
    assert e.project_id == "proj1"


@pytest.mark.asyncio
async def test_events_with_explicit_seq_persist_and_round_trip(store):
    e = Event(project_id="proj1", run_id="r1", type="status", seq=42, data={"x": 1})
    await store.append_event(e)
    events = await store.replay_events("r1", after_seq=0)
    assert len(events) == 1
    assert events[0].seq == 42
    assert events[0].project_id == "proj1"
    assert events[0].id == e.id
    assert events[0].data == {"x": 1}


@pytest.mark.asyncio
async def test_replay_events_after_seq_filters_correctly(store):
    e1 = Event(project_id="proj1", run_id="r1", type="status", seq=1)
    e2 = Event(project_id="proj1", run_id="r1", type="diff", seq=2)
    e3 = Event(project_id="proj1", run_id="r1", type="status", seq=3)
    await store.append_event(e1)
    await store.append_event(e2)
    await store.append_event(e3)
    events = await store.replay_events("r1", after_seq=1)
    assert len(events) == 2
    assert events[0].id == e2.id
    assert events[1].id == e3.id


@pytest.mark.asyncio
async def test_replay_events_after_seq_zero_returns_all(store):
    e1 = Event(project_id="proj1", run_id="r1", type="status", seq=1)
    e2 = Event(project_id="proj1", run_id="r1", type="diff", seq=2)
    await store.append_event(e1)
    await store.append_event(e2)
    events = await store.replay_events("r1", after_seq=0)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_replay_events_without_after_seq_returns_all(store):
    e1 = Event(project_id="proj1", run_id="r1", type="status", seq=1)
    e2 = Event(project_id="proj1", run_id="r1", type="diff", seq=2)
    await store.append_event(e1)
    await store.append_event(e2)
    events = await store.replay_events("r1")
    assert len(events) == 2


@pytest.mark.asyncio
async def test_replay_events_ordered_by_seq_ascending(store):
    e3 = Event(project_id="proj1", run_id="r1", type="status", seq=3)
    e1 = Event(project_id="proj1", run_id="r1", type="diff", seq=1)
    e2 = Event(project_id="proj1", run_id="r1", type="status", seq=2)
    await store.append_event(e3)
    await store.append_event(e1)
    await store.append_event(e2)
    events = await store.replay_events("r1")
    assert [ev.seq for ev in events] == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_max_seq_returns_zero_for_empty_run(store):
    result = await store.get_max_seq("nonexistent-run")
    assert result == 0


@pytest.mark.asyncio
async def test_get_max_seq_returns_highest_seq(store):
    e1 = Event(project_id="proj1", run_id="r1", type="status", seq=5)
    e2 = Event(project_id="proj1", run_id="r1", type="diff", seq=10)
    e3 = Event(project_id="proj1", run_id="r1", type="status", seq=3)
    await store.append_event(e1)
    await store.append_event(e2)
    await store.append_event(e3)
    result = await store.get_max_seq("r1")
    assert result == 10
