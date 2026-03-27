"""Integration test: verify event_bus and project_id are passed in graph config."""
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
async def event_bus(store):
    b = EventBus(store)
    sent_events = []
    async def capture(event):
        sent_events.append(event)
    b.set_send_callback(capture)
    b.start_batcher()
    b.sent_events = sent_events
    yield b
    await b.shutdown()


@pytest.mark.asyncio
async def test_event_bus_receives_run_lifecycle(store, event_bus):
    """Verify that emitting a run_started event works end-to-end."""
    event = Event(
        project_id="test-proj",
        run_id="test-run",
        type="run_started",
        node="system",
        data={"instruction": "add a button"},
    )
    await event_bus.emit(event)
    assert event.seq == 1
    # run_started is now P0, so it should be sent immediately via callback
    assert len(event_bus.sent_events) == 1
    assert event_bus.sent_events[0].type == "run_started"
