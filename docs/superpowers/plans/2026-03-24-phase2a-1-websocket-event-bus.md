# Sub-phase 2a-1: WebSocket Event Bus — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time WebSocket event streaming with priority channels, token batching, and reconnect replay.

**Architecture:** EventBus emits events from agent nodes, routes by priority (P0 instant, P1 batched, P2 aggregated), persists durable events to SQLite, and streams to WebSocket clients via ConnectionManager. TokenBatcher buffers P1 events and flushes every 50ms.

**Tech Stack:** FastAPI WebSocket, asyncio, aiosqlite

**Spec:** `docs/superpowers/specs/2026-03-24-phase2a-backend-features-design.md` (Sub-phase 2a-1)

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## Task 1: Store Prerequisites — seq field, schema migration, replay_events update

### 1.1 Write Tests

**File:** `tests/test_store_seq.py`

```python
"""Tests for seq field on Event and updated replay_events with after_seq."""
import pytest
import pytest_asyncio
from store.sqlite import SQLiteSessionStore
from store.models import Event


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_event_model_has_seq_field():
    """Event model should have a seq field defaulting to 0."""
    e = Event(run_id="r1", type="status")
    assert hasattr(e, "seq")
    assert e.seq == 0


@pytest.mark.asyncio
async def test_event_seq_persists_to_db(store):
    """Events with explicit seq values should round-trip through SQLite."""
    e = Event(run_id="r1", type="status", seq=5)
    await store.append_event(e)
    events = await store.replay_events("r1")
    assert len(events) == 1
    assert events[0].seq == 5


@pytest.mark.asyncio
async def test_replay_events_after_seq(store):
    """replay_events(run_id, after_seq=N) returns only events with seq > N."""
    e1 = Event(run_id="r1", type="status", seq=1)
    e2 = Event(run_id="r1", type="diff", seq=2)
    e3 = Event(run_id="r1", type="error", seq=3)
    await store.append_event(e1)
    await store.append_event(e2)
    await store.append_event(e3)

    events = await store.replay_events("r1", after_seq=1)
    assert len(events) == 2
    assert events[0].seq == 2
    assert events[1].seq == 3


@pytest.mark.asyncio
async def test_replay_events_after_seq_zero_returns_all(store):
    """after_seq=0 should return all events (seq starts at 1 in practice)."""
    e1 = Event(run_id="r1", type="status", seq=1)
    e2 = Event(run_id="r1", type="diff", seq=2)
    await store.append_event(e1)
    await store.append_event(e2)

    events = await store.replay_events("r1", after_seq=0)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_replay_events_no_after_seq_returns_all(store):
    """Calling replay_events without after_seq returns all events."""
    e1 = Event(run_id="r1", type="status", seq=1)
    e2 = Event(run_id="r1", type="diff", seq=2)
    await store.append_event(e1)
    await store.append_event(e2)

    events = await store.replay_events("r1")
    assert len(events) == 2


@pytest.mark.asyncio
async def test_replay_events_ordered_by_seq(store):
    """Events should be returned ordered by seq ascending."""
    # Insert out of order
    e3 = Event(run_id="r1", type="error", seq=3)
    e1 = Event(run_id="r1", type="status", seq=1)
    e2 = Event(run_id="r1", type="diff", seq=2)
    await store.append_event(e3)
    await store.append_event(e1)
    await store.append_event(e2)

    events = await store.replay_events("r1")
    assert [e.seq for e in events] == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_max_seq_for_new_run(store):
    """get_max_seq returns 0 for a run with no events."""
    result = await store.get_max_seq("nonexistent_run")
    assert result == 0


@pytest.mark.asyncio
async def test_get_max_seq_returns_highest(store):
    """get_max_seq returns the highest seq for a given run_id."""
    e1 = Event(run_id="r1", type="status", seq=1)
    e2 = Event(run_id="r1", type="diff", seq=5)
    e3 = Event(run_id="r1", type="error", seq=3)
    await store.append_event(e1)
    await store.append_event(e2)
    await store.append_event(e3)

    result = await store.get_max_seq("r1")
    assert result == 5
```

### 1.2 Run Tests (expect failures)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_store_seq.py -v 2>&1 | head -60
```

### 1.3 Implement

**File:** `store/models.py` — Add `seq` field to Event

Replace the Event class (lines 45-52):

```python
class Event(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    type: str
    seq: int = 0
    node: str | None = None
    model: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
```

**File:** `store/protocol.py` — Update replay_events signature and add get_max_seq

Replace line 19:

```python
    async def replay_events(self, run_id: str, after_seq: int = 0) -> list[Event]: ...
    async def get_max_seq(self, run_id: str) -> int: ...
```

**File:** `store/sqlite.py` — Migrate schema, update append_event, replay_events, add get_max_seq

Replace the events table block in `_SCHEMA` (lines 24-29):

```python
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL, seq INTEGER DEFAULT 0,
    node TEXT, model TEXT, data TEXT,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_replay ON events(run_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events(run_id, seq);
```

Replace the `append_event` method (lines 182-191):

```python
    async def append_event(self, event: Event) -> None:
        await self._db.execute(
            """INSERT INTO events (id, run_id, type, seq, node, model, data, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id, event.run_id, event.type, event.seq,
                event.node, event.model,
                json.dumps(event.data), event.timestamp,
            ),
        )
        await self._db.commit()
```

Replace the `replay_events` method (lines 193-213):

```python
    async def replay_events(self, run_id: str, after_seq: int = 0) -> list[Event]:
        async with self._db.execute(
            "SELECT * FROM events WHERE run_id = ? AND seq > ? ORDER BY seq ASC",
            (run_id, after_seq),
        ) as cursor:
            rows = await cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row)
            data["data"] = json.loads(data["data"]) if data["data"] else {}
            result.append(Event(**data))
        return result
```

Add `get_max_seq` method right after `replay_events`:

```python
    async def get_max_seq(self, run_id: str) -> int:
        async with self._db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM events WHERE run_id = ?",
            (run_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0]
```

### 1.4 Update Existing Tests

**File:** `tests/test_store.py` — Fix `test_replay_events_after_cursor` which uses old `after_id` parameter

Replace the test (lines 73-81):

```python
@pytest.mark.asyncio
async def test_replay_events_after_cursor(store):
    e1 = Event(run_id="r1", type="status", seq=1, data={"a": 1})
    e2 = Event(run_id="r1", type="diff", seq=2, data={"b": 2})
    await store.append_event(e1)
    await store.append_event(e2)
    events = await store.replay_events("r1", after_seq=1)
    assert len(events) == 1
    assert events[0].id == e2.id
```

### 1.5 Run Tests (expect pass)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_store_seq.py tests/test_store.py -v 2>&1 | tail -30
```

### 1.6 Commit

```bash
cd /Users/rohanthomas/Shipyard && git add store/models.py store/protocol.py store/sqlite.py tests/test_store_seq.py tests/test_store.py && git commit -m "feat: add seq field to Event model, update replay_events to use after_seq"
```

---

## Task 2: TokenBatcher — Standalone async batching class

### 2.1 Write Tests

**File:** `tests/test_token_batcher.py`

```python
"""Tests for TokenBatcher — buffers events and flushes on interval."""
import asyncio
import pytest
from agent.events import TokenBatcher


@pytest.mark.asyncio
async def test_batcher_flushes_after_interval():
    """Batcher should flush buffered items after flush_interval."""
    flushed = []

    async def on_flush(items):
        flushed.extend(items)

    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)

    batcher.add("token1")
    batcher.add("token2")
    assert len(flushed) == 0  # Not flushed yet

    await asyncio.sleep(0.1)  # Wait for flush
    assert flushed == ["token1", "token2"]

    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_empty_buffer_no_flush():
    """Batcher should not call on_flush when buffer is empty."""
    flush_count = 0

    async def on_flush(items):
        nonlocal flush_count
        flush_count += 1

    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)

    await asyncio.sleep(0.15)  # Wait for multiple flush cycles
    assert flush_count == 0  # Never called because buffer is empty

    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_multiple_flushes():
    """Batcher should flush multiple batches over time."""
    batches = []

    async def on_flush(items):
        batches.append(list(items))

    batcher = TokenBatcher(flush_interval=0.05)
    batcher.start(on_flush)

    batcher.add("a")
    await asyncio.sleep(0.08)
    batcher.add("b")
    await asyncio.sleep(0.08)

    assert len(batches) >= 2
    assert batches[0] == ["a"]
    assert batches[1] == ["b"]

    await batcher.stop()


@pytest.mark.asyncio
async def test_batcher_stop_flushes_remaining():
    """Stopping the batcher should flush any remaining items."""
    flushed = []

    async def on_flush(items):
        flushed.extend(items)

    batcher = TokenBatcher(flush_interval=1.0)  # Long interval
    batcher.start(on_flush)

    batcher.add("final_item")
    await batcher.stop()  # Should flush remaining

    assert "final_item" in flushed


@pytest.mark.asyncio
async def test_batcher_stop_idempotent():
    """Calling stop multiple times should not raise."""
    batcher = TokenBatcher(flush_interval=0.05)

    async def on_flush(items):
        pass

    batcher.start(on_flush)
    await batcher.stop()
    await batcher.stop()  # Should not raise


@pytest.mark.asyncio
async def test_batcher_not_started():
    """Adding items before start should buffer without error."""
    batcher = TokenBatcher(flush_interval=0.05)
    batcher.add("item")  # Should not raise
    assert len(batcher._buffer) == 1
```

### 2.2 Run Tests (expect failures — module not found)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_token_batcher.py -v 2>&1 | head -30
```

### 2.3 Implement

**File:** `agent/events.py` — Create with TokenBatcher first (EventBus added in Task 3)

```python
"""Event bus and token batcher for real-time streaming."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable


class TokenBatcher:
    """Buffers items and flushes them at a fixed interval.

    Usage:
        batcher = TokenBatcher(flush_interval=0.05)
        batcher.start(on_flush_callback)
        batcher.add(event)
        ...
        await batcher.stop()
    """

    def __init__(self, flush_interval: float = 0.05):
        self.flush_interval = flush_interval
        self._buffer: list[Any] = []
        self._task: asyncio.Task | None = None
        self._on_flush: Callable[[list[Any]], Awaitable[None]] | None = None
        self._running = False

    def start(self, on_flush: Callable[[list[Any]], Awaitable[None]]) -> None:
        """Start the background flush loop."""
        self._on_flush = on_flush
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())

    def add(self, item: Any) -> None:
        """Add an item to the buffer."""
        self._buffer.append(item)

    async def stop(self) -> None:
        """Stop the flush loop and flush remaining items."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # Flush remaining items
        if self._buffer and self._on_flush is not None:
            items = list(self._buffer)
            self._buffer.clear()
            await self._on_flush(items)

    async def _flush_loop(self) -> None:
        """Background loop that flushes buffer at fixed intervals."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            if self._buffer and self._on_flush is not None:
                items = list(self._buffer)
                self._buffer.clear()
                await self._on_flush(items)
```

### 2.4 Run Tests (expect pass)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_token_batcher.py -v 2>&1 | tail -20
```

### 2.5 Commit

```bash
cd /Users/rohanthomas/Shipyard && git add agent/events.py tests/test_token_batcher.py && git commit -m "feat: add TokenBatcher with background flush loop"
```

---

## Task 3: EventBus — Priority routing, seq assignment, persistence, replay, snapshot

### 3.1 Write Tests

**File:** `tests/test_event_bus.py`

```python
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
    """Each emitted event gets a monotonically increasing seq per run."""
    e1 = Event(run_id="r1", type="status", data={"msg": "a"})
    e2 = Event(run_id="r1", type="diff", data={"msg": "b"})
    await bus.emit(e1)
    await bus.emit(e2)
    assert e1.seq == 1
    assert e2.seq == 2


@pytest.mark.asyncio
async def test_emit_seq_independent_per_run(bus):
    """Different run_ids have independent seq counters."""
    e1 = Event(run_id="r1", type="status")
    e2 = Event(run_id="r2", type="status")
    await bus.emit(e1)
    await bus.emit(e2)
    assert e1.seq == 1
    assert e2.seq == 1


@pytest.mark.asyncio
async def test_emit_resumes_seq_from_store(store):
    """On init, EventBus should pick up seq from existing events in store."""
    # Pre-populate store with an event at seq=10
    e = Event(run_id="r1", type="status", seq=10)
    await store.append_event(e)

    bus = EventBus(store)
    new_event = Event(run_id="r1", type="diff")
    await bus.emit(new_event)
    assert new_event.seq == 11
    await bus.shutdown()


# --- P0 events: immediate send ---

@pytest.mark.asyncio
async def test_p0_events_sent_immediately(bus):
    """P0 events (approval, error, stop, review) are sent via callback immediately."""
    sent = []

    async def callback(event):
        sent.append(event)

    bus.set_send_callback(callback)

    for event_type in ["approval", "error", "stop", "review"]:
        e = Event(run_id="r1", type=event_type)
        await bus.emit(e)

    assert len(sent) == 4
    assert {e.type for e in sent} == {"approval", "error", "stop", "review"}


@pytest.mark.asyncio
async def test_p0_events_persisted(bus, store):
    """P0 events should be persisted to the store."""
    e = Event(run_id="r1", type="error", data={"msg": "fail"})
    await bus.emit(e)

    events = await store.replay_events("r1")
    assert len(events) == 1
    assert events[0].type == "error"


# --- P1 events: batched send ---

@pytest.mark.asyncio
async def test_p1_stream_events_sent_via_batcher(bus):
    """P1 stream events should be buffered and flushed by the batcher."""
    sent = []

    async def callback(event):
        sent.append(event)

    bus.set_send_callback(callback)
    bus.start_batcher()

    e = Event(run_id="r1", type="stream", data={"token": "hello"})
    await bus.emit(e)

    # Not sent immediately
    assert len(sent) == 0

    # Wait for batcher flush
    await asyncio.sleep(0.1)
    assert len(sent) == 1
    assert sent[0].type == "stream"

    await bus.shutdown()


@pytest.mark.asyncio
async def test_p1_stream_events_not_persisted(bus, store):
    """stream events should NOT be persisted to the store."""
    bus.start_batcher()

    e = Event(run_id="r1", type="stream", data={"token": "x"})
    await bus.emit(e)

    events = await store.replay_events("r1")
    assert len(events) == 0

    await bus.shutdown()


@pytest.mark.asyncio
async def test_p1_diff_events_persisted(bus, store):
    """P1 non-stream events (diff, git) should be persisted."""
    bus.start_batcher()

    e = Event(run_id="r1", type="diff", data={"file": "a.py"})
    await bus.emit(e)

    events = await store.replay_events("r1")
    assert len(events) == 1
    assert events[0].type == "diff"

    await bus.shutdown()


@pytest.mark.asyncio
async def test_p1_git_events_batched(bus):
    """P1 git events should be buffered in the batcher."""
    sent = []

    async def callback(event):
        sent.append(event)

    bus.set_send_callback(callback)
    bus.start_batcher()

    e = Event(run_id="r1", type="git", data={"action": "commit"})
    await bus.emit(e)
    assert len(sent) == 0

    await asyncio.sleep(0.1)
    assert len(sent) == 1

    await bus.shutdown()


# --- P2 events: persist, send at boundary ---

@pytest.mark.asyncio
async def test_p2_events_persisted(bus, store):
    """P2 events (status, file, exec) should be persisted."""
    e = Event(run_id="r1", type="status", data={"step": 1})
    await bus.emit(e)

    events = await store.replay_events("r1")
    assert len(events) == 1


@pytest.mark.asyncio
async def test_p2_events_queued_for_boundary(bus):
    """P2 events should not be sent immediately — they queue for flush_node_boundary."""
    sent = []

    async def callback(event):
        sent.append(event)

    bus.set_send_callback(callback)

    e = Event(run_id="r1", type="status", data={"step": 1})
    await bus.emit(e)

    # Not sent yet
    assert len(sent) == 0


@pytest.mark.asyncio
async def test_flush_node_boundary_sends_p2(bus):
    """flush_node_boundary should send all queued P2 events."""
    sent = []

    async def callback(event):
        sent.append(event)

    bus.set_send_callback(callback)

    e1 = Event(run_id="r1", type="status", data={"step": 1})
    e2 = Event(run_id="r1", type="file", data={"path": "a.py"})
    await bus.emit(e1)
    await bus.emit(e2)

    assert len(sent) == 0
    await bus.flush_node_boundary()
    assert len(sent) == 2


# --- replay ---

@pytest.mark.asyncio
async def test_replay_returns_persisted_events(bus, store):
    """replay should return all persisted events after a given seq."""
    e1 = Event(run_id="r1", type="error", data={"a": 1})
    e2 = Event(run_id="r1", type="status", data={"b": 2})
    await bus.emit(e1)
    await bus.emit(e2)

    events = await bus.replay("r1", after_seq=0)
    assert len(events) == 2
    assert events[0].seq == 1
    assert events[1].seq == 2


@pytest.mark.asyncio
async def test_replay_respects_after_seq(bus, store):
    """replay with after_seq should only return events after that seq."""
    e1 = Event(run_id="r1", type="error")
    e2 = Event(run_id="r1", type="status")
    e3 = Event(run_id="r1", type="diff")
    await bus.emit(e1)
    await bus.emit(e2)
    await bus.emit(e3)

    events = await bus.replay("r1", after_seq=2)
    assert len(events) == 1
    assert events[0].seq == 3


# --- snapshot ---

@pytest.mark.asyncio
async def test_get_snapshot(bus):
    """get_snapshot should return run status, plan, and current step."""
    state = {
        "status": "running",
        "plan": ["step1", "step2"],
        "current_step": 1,
        "instruction": "do stuff",
    }
    snap = bus.get_snapshot("r1", state)
    assert snap["run_id"] == "r1"
    assert snap["status"] == "running"
    assert snap["plan"] == ["step1", "step2"]
    assert snap["current_step"] == 1


@pytest.mark.asyncio
async def test_get_snapshot_includes_last_seq(bus, store):
    """Snapshot should include the last seq for reconnect."""
    e1 = Event(run_id="r1", type="status")
    e2 = Event(run_id="r1", type="diff")
    await bus.emit(e1)
    await bus.emit(e2)

    state = {"status": "running", "plan": [], "current_step": 0}
    snap = bus.get_snapshot("r1", state)
    assert snap["last_seq"] == 2


# --- no callback set ---

@pytest.mark.asyncio
async def test_emit_without_callback_does_not_raise(bus):
    """Emitting events without a send_callback should not raise."""
    e = Event(run_id="r1", type="error", data={"msg": "boom"})
    await bus.emit(e)  # Should not raise
```

### 3.2 Run Tests (expect failures)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_event_bus.py -v 2>&1 | head -60
```

### 3.3 Implement

**File:** `agent/events.py` — Add EventBus class below TokenBatcher

Append to the existing file after the TokenBatcher class:

```python
from store.models import Event

# Priority classification
_P0_TYPES = frozenset({"approval", "error", "stop", "review"})
_P1_TYPES = frozenset({"stream", "diff", "git"})
# Everything else is P2: status, file, exec, etc.

# stream events are ephemeral — never persisted
_NO_PERSIST_TYPES = frozenset({"stream"})


class EventBus:
    """Central event bus with priority-based routing.

    P0 (approval, error, stop, review): send immediately, persist.
    P1 (stream, diff, git): buffer in batcher, persist non-stream events.
    P2 (status, file, exec, ...): persist and send at node boundaries.
    """

    def __init__(self, store: Any):
        self.store = store
        self._send_callback: Callable[[Event], Awaitable[None]] | None = None
        self._batcher = TokenBatcher(flush_interval=0.05)
        self._seq_counters: dict[str, int] = {}  # run_id -> next seq
        self._p2_queue: list[Event] = []

    def set_send_callback(
        self, callback: Callable[[Event], Awaitable[None]]
    ) -> None:
        """Set the callback used to send events to connected clients."""
        self._send_callback = callback

    def start_batcher(self) -> None:
        """Start the background token batcher flush loop."""
        self._batcher.start(self._flush_batch)

    async def _flush_batch(self, items: list[Event]) -> None:
        """Callback invoked by TokenBatcher on flush."""
        if self._send_callback is not None:
            for event in items:
                await self._send_callback(event)

    async def emit(self, event: Event) -> None:
        """Emit an event: assign seq, persist (if durable), route by priority."""
        # Assign monotonic seq
        run_id = event.run_id
        if run_id not in self._seq_counters:
            # Initialize from store
            max_seq = await self.store.get_max_seq(run_id)
            self._seq_counters[run_id] = max_seq + 1

        event.seq = self._seq_counters[run_id]
        self._seq_counters[run_id] += 1

        # Persist (unless ephemeral)
        should_persist = event.type not in _NO_PERSIST_TYPES
        if should_persist:
            await self.store.append_event(event)

        # Route by priority
        if event.type in _P0_TYPES:
            # P0: send immediately
            if self._send_callback is not None:
                await self._send_callback(event)
        elif event.type in _P1_TYPES:
            # P1: buffer in batcher
            self._batcher.add(event)
        else:
            # P2: queue for node boundary
            self._p2_queue.append(event)

    async def flush_node_boundary(self) -> None:
        """Send all queued P2 events. Called at node transitions."""
        if self._send_callback is not None:
            for event in self._p2_queue:
                await self._send_callback(event)
        self._p2_queue.clear()

    async def replay(self, run_id: str, after_seq: int = 0) -> list[Event]:
        """Replay persisted events for a run after a given seq."""
        return await self.store.replay_events(run_id, after_seq=after_seq)

    def get_snapshot(self, run_id: str, state: dict) -> dict:
        """Build a snapshot dict for reconnecting clients."""
        last_seq = self._seq_counters.get(run_id, 1) - 1
        if last_seq < 0:
            last_seq = 0
        return {
            "run_id": run_id,
            "status": state.get("status", "unknown"),
            "plan": state.get("plan", []),
            "current_step": state.get("current_step", 0),
            "last_seq": last_seq,
        }

    async def shutdown(self) -> None:
        """Stop the batcher and clean up."""
        await self._batcher.stop()
```

The complete `agent/events.py` file should be:

```python
"""Event bus and token batcher for real-time streaming."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from store.models import Event

# Priority classification
_P0_TYPES = frozenset({"approval", "error", "stop", "review"})
_P1_TYPES = frozenset({"stream", "diff", "git"})
_NO_PERSIST_TYPES = frozenset({"stream"})


class TokenBatcher:
    """Buffers items and flushes them at a fixed interval.

    Usage:
        batcher = TokenBatcher(flush_interval=0.05)
        batcher.start(on_flush_callback)
        batcher.add(event)
        ...
        await batcher.stop()
    """

    def __init__(self, flush_interval: float = 0.05):
        self.flush_interval = flush_interval
        self._buffer: list[Any] = []
        self._task: asyncio.Task | None = None
        self._on_flush: Callable[[list[Any]], Awaitable[None]] | None = None
        self._running = False

    def start(self, on_flush: Callable[[list[Any]], Awaitable[None]]) -> None:
        """Start the background flush loop."""
        self._on_flush = on_flush
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())

    def add(self, item: Any) -> None:
        """Add an item to the buffer."""
        self._buffer.append(item)

    async def stop(self) -> None:
        """Stop the flush loop and flush remaining items."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # Flush remaining items
        if self._buffer and self._on_flush is not None:
            items = list(self._buffer)
            self._buffer.clear()
            await self._on_flush(items)

    async def _flush_loop(self) -> None:
        """Background loop that flushes buffer at fixed intervals."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            if self._buffer and self._on_flush is not None:
                items = list(self._buffer)
                self._buffer.clear()
                await self._on_flush(items)


class EventBus:
    """Central event bus with priority-based routing.

    P0 (approval, error, stop, review): send immediately, persist.
    P1 (stream, diff, git): buffer in batcher, persist non-stream events.
    P2 (status, file, exec, ...): persist and send at node boundaries.
    """

    def __init__(self, store: Any):
        self.store = store
        self._send_callback: Callable[[Event], Awaitable[None]] | None = None
        self._batcher = TokenBatcher(flush_interval=0.05)
        self._seq_counters: dict[str, int] = {}  # run_id -> next seq
        self._p2_queue: list[Event] = []

    def set_send_callback(
        self, callback: Callable[[Event], Awaitable[None]]
    ) -> None:
        """Set the callback used to send events to connected clients."""
        self._send_callback = callback

    def start_batcher(self) -> None:
        """Start the background token batcher flush loop."""
        self._batcher.start(self._flush_batch)

    async def _flush_batch(self, items: list[Event]) -> None:
        """Callback invoked by TokenBatcher on flush."""
        if self._send_callback is not None:
            for event in items:
                await self._send_callback(event)

    async def emit(self, event: Event) -> None:
        """Emit an event: assign seq, persist (if durable), route by priority."""
        run_id = event.run_id
        if run_id not in self._seq_counters:
            max_seq = await self.store.get_max_seq(run_id)
            self._seq_counters[run_id] = max_seq + 1

        event.seq = self._seq_counters[run_id]
        self._seq_counters[run_id] += 1

        should_persist = event.type not in _NO_PERSIST_TYPES
        if should_persist:
            await self.store.append_event(event)

        if event.type in _P0_TYPES:
            if self._send_callback is not None:
                await self._send_callback(event)
        elif event.type in _P1_TYPES:
            self._batcher.add(event)
        else:
            self._p2_queue.append(event)

    async def flush_node_boundary(self) -> None:
        """Send all queued P2 events. Called at node transitions."""
        if self._send_callback is not None:
            for event in self._p2_queue:
                await self._send_callback(event)
        self._p2_queue.clear()

    async def replay(self, run_id: str, after_seq: int = 0) -> list[Event]:
        """Replay persisted events for a run after a given seq."""
        return await self.store.replay_events(run_id, after_seq=after_seq)

    def get_snapshot(self, run_id: str, state: dict) -> dict:
        """Build a snapshot dict for reconnecting clients."""
        last_seq = self._seq_counters.get(run_id, 1) - 1
        if last_seq < 0:
            last_seq = 0
        return {
            "run_id": run_id,
            "status": state.get("status", "unknown"),
            "plan": state.get("plan", []),
            "current_step": state.get("current_step", 0),
            "last_seq": last_seq,
        }

    async def shutdown(self) -> None:
        """Stop the batcher and clean up."""
        await self._batcher.stop()
```

### 3.4 Run Tests (expect pass)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_event_bus.py tests/test_token_batcher.py -v 2>&1 | tail -40
```

### 3.5 Commit

```bash
cd /Users/rohanthomas/Shipyard && git add agent/events.py tests/test_event_bus.py && git commit -m "feat: add EventBus with priority routing, seq assignment, and replay"
```

---

## Task 4: ConnectionManager — WebSocket state, subscriptions, send

### 4.1 Write Tests

**File:** `tests/test_connection_manager.py`

```python
"""Tests for ConnectionManager — WebSocket state management and message routing."""
import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from store.sqlite import SQLiteSessionStore
from store.models import Event
from agent.events import EventBus
from server.websocket import ConnectionManager, WebSocketState


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


@pytest_asyncio.fixture
def manager(bus):
    return ConnectionManager(bus)


def _make_ws(project_id="proj1"):
    """Create a mock WebSocket object."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


# --- connect/disconnect ---

@pytest.mark.asyncio
async def test_connect_adds_to_connections(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")
    assert "proj1" in manager._connections
    assert len(manager._connections["proj1"]) == 1


@pytest.mark.asyncio
async def test_connect_multiple_clients_same_project(manager):
    ws1 = _make_ws()
    ws2 = _make_ws()
    await manager.connect(ws1, "proj1")
    await manager.connect(ws2, "proj1")
    assert len(manager._connections["proj1"]) == 2


@pytest.mark.asyncio
async def test_disconnect_removes_from_connections(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")
    await manager.disconnect(ws)
    # Either key removed or list is empty
    conns = manager._connections.get("proj1", [])
    ws_objects = [s.ws for s in conns]
    assert ws not in ws_objects


@pytest.mark.asyncio
async def test_disconnect_nonexistent_does_not_raise(manager):
    ws = _make_ws()
    await manager.disconnect(ws)  # Should not raise


# --- send_to_subscribed ---

@pytest.mark.asyncio
async def test_send_to_subscribed_delivers_event(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")

    # Subscribe to a run
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(run_id="r1", type="status", seq=1, data={"msg": "hello"})
    await manager.send_to_subscribed(event, project_id="proj1")

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "status"
    assert payload["seq"] == 1


@pytest.mark.asyncio
async def test_send_to_subscribed_skips_unsubscribed_run(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")

    # Subscribe to r1, but send event for r2
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(run_id="r2", type="status", seq=1, data={"msg": "hello"})
    await manager.send_to_subscribed(event, project_id="proj1")

    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_send_to_subscribed_multiple_clients(manager):
    ws1 = _make_ws()
    ws2 = _make_ws()
    await manager.connect(ws1, "proj1")
    await manager.connect(ws2, "proj1")

    for state in manager._connections["proj1"]:
        state.subscribed_runs.add("r1")

    event = Event(run_id="r1", type="error", seq=1)
    await manager.send_to_subscribed(event, project_id="proj1")

    assert ws1.send_json.call_count == 1
    assert ws2.send_json.call_count == 1


# --- handle_client_message: subscribe ---

@pytest.mark.asyncio
async def test_handle_subscribe_message(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")

    data = {"action": "subscribe", "run_id": "r1"}
    await manager.handle_client_message(ws, data)

    state = manager._connections["proj1"][0]
    assert "r1" in state.subscribed_runs


# --- handle_client_message: reconnect ---

@pytest.mark.asyncio
async def test_handle_reconnect_replays_events(manager, bus, store):
    ws = _make_ws()
    await manager.connect(ws, "proj1")

    # Emit some events to the store
    e1 = Event(run_id="r1", type="status", seq=1)
    e2 = Event(run_id="r1", type="diff", seq=2)
    await store.append_event(e1)
    await store.append_event(e2)

    data = {"action": "reconnect", "run_id": "r1", "last_seq": 0}
    await manager.handle_client_message(ws, data)

    # Should have sent the replayed events
    assert ws.send_json.call_count >= 2


# --- handle_client_message: stop ---

@pytest.mark.asyncio
async def test_handle_stop_message(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")

    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    stopped_runs = []

    async def on_stop(run_id):
        stopped_runs.append(run_id)

    manager.set_stop_callback(on_stop)

    data = {"action": "stop", "run_id": "r1"}
    await manager.handle_client_message(ws, data)

    assert "r1" in stopped_runs


# --- heartbeat ---

@pytest.mark.asyncio
async def test_broadcast_heartbeat(manager):
    ws = _make_ws()
    await manager.connect(ws, "proj1")

    await manager.broadcast_heartbeat()

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "heartbeat"


# --- WebSocketState ---

def test_websocket_state_defaults():
    ws = _make_ws()
    state = WebSocketState(ws=ws, project_id="proj1")
    assert state.project_id == "proj1"
    assert state.subscribed_runs == set()
    assert state.last_seq == {}
```

### 4.2 Run Tests (expect failures — module not found)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_connection_manager.py -v 2>&1 | head -30
```

### 4.3 Implement

**File:** `server/websocket.py`

```python
"""WebSocket ConnectionManager for real-time event streaming."""
from __future__ import annotations

import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from store.models import Event
from agent.events import EventBus

logger = logging.getLogger(__name__)


@dataclass
class WebSocketState:
    """Tracks state for a single WebSocket connection."""
    ws: Any
    project_id: str
    subscribed_runs: set[str] = field(default_factory=set)
    last_seq: dict[str, int] = field(default_factory=dict)  # run_id -> last_seq seen
    connected_at: float = field(default_factory=time.time)


class ConnectionManager:
    """Manages WebSocket connections, subscriptions, and message routing."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._connections: dict[str, list[WebSocketState]] = {}  # project_id -> states
        self._ws_to_project: dict[int, str] = {}  # id(ws) -> project_id
        self._stop_callback: Callable[[str], Awaitable[None]] | None = None
        self._approve_callback: Callable[[str, str], Awaitable[None]] | None = None
        self._reject_callback: Callable[[str, str], Awaitable[None]] | None = None
        self._update_mode_callback: Callable[[str, str], Awaitable[None]] | None = None

    def set_stop_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self._stop_callback = callback

    def set_approve_callback(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        self._approve_callback = callback

    def set_reject_callback(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        self._reject_callback = callback

    def set_update_mode_callback(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        self._update_mode_callback = callback

    async def connect(self, ws: Any, project_id: str) -> WebSocketState:
        """Register a new WebSocket connection."""
        state = WebSocketState(ws=ws, project_id=project_id)
        if project_id not in self._connections:
            self._connections[project_id] = []
        self._connections[project_id].append(state)
        self._ws_to_project[id(ws)] = project_id
        return state

    async def disconnect(self, ws: Any) -> None:
        """Remove a WebSocket connection."""
        ws_id = id(ws)
        project_id = self._ws_to_project.pop(ws_id, None)
        if project_id is None:
            return
        if project_id in self._connections:
            self._connections[project_id] = [
                s for s in self._connections[project_id] if s.ws is not ws
            ]
            if not self._connections[project_id]:
                del self._connections[project_id]

    async def send_to_subscribed(self, event: Event, project_id: str) -> None:
        """Send an event to all clients subscribed to that event's run_id."""
        states = self._connections.get(project_id, [])
        payload = {
            "type": event.type,
            "run_id": event.run_id,
            "seq": event.seq,
            "node": event.node,
            "data": event.data,
            "timestamp": event.timestamp,
        }
        dead = []
        for state in states:
            if event.run_id in state.subscribed_runs:
                try:
                    await state.ws.send_json(payload)
                    state.last_seq[event.run_id] = event.seq
                except Exception:
                    logger.warning("Failed to send to WebSocket, marking for removal")
                    dead.append(state)
        # Clean up dead connections
        for state in dead:
            await self.disconnect(state.ws)

    async def handle_client_message(self, ws: Any, data: dict) -> None:
        """Process an incoming client message."""
        action = data.get("action")
        ws_id = id(ws)
        project_id = self._ws_to_project.get(ws_id)
        if project_id is None:
            return

        state = self._find_state(ws)
        if state is None:
            return

        if action == "subscribe":
            run_id = data.get("run_id")
            if run_id:
                state.subscribed_runs.add(run_id)

        elif action == "reconnect":
            run_id = data.get("run_id")
            last_seq = data.get("last_seq", 0)
            if run_id:
                state.subscribed_runs.add(run_id)
                events = await self.event_bus.replay(run_id, after_seq=last_seq)
                for event in events:
                    payload = {
                        "type": event.type,
                        "run_id": event.run_id,
                        "seq": event.seq,
                        "node": event.node,
                        "data": event.data,
                        "timestamp": event.timestamp,
                    }
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        break

        elif action == "approve":
            run_id = data.get("run_id")
            edit_id = data.get("edit_id", "")
            if self._approve_callback and run_id:
                await self._approve_callback(run_id, edit_id)

        elif action == "reject":
            run_id = data.get("run_id")
            edit_id = data.get("edit_id", "")
            if self._reject_callback and run_id:
                await self._reject_callback(run_id, edit_id)

        elif action == "stop":
            run_id = data.get("run_id")
            if self._stop_callback and run_id:
                await self._stop_callback(run_id)

        elif action == "update_mode":
            run_id = data.get("run_id")
            mode = data.get("mode", "")
            if self._update_mode_callback and run_id:
                await self._update_mode_callback(run_id, mode)

    async def broadcast_heartbeat(self) -> None:
        """Send a heartbeat message to all connected clients."""
        payload = {"type": "heartbeat", "timestamp": time.time()}
        dead = []
        for project_id, states in self._connections.items():
            for state in states:
                try:
                    await state.ws.send_json(payload)
                except Exception:
                    dead.append(state)
        for state in dead:
            await self.disconnect(state.ws)

    def _find_state(self, ws: Any) -> WebSocketState | None:
        """Find the WebSocketState for a given ws object."""
        ws_id = id(ws)
        project_id = self._ws_to_project.get(ws_id)
        if project_id is None:
            return None
        for state in self._connections.get(project_id, []):
            if state.ws is ws:
                return state
        return None
```

### 4.4 Run Tests (expect pass)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_connection_manager.py -v 2>&1 | tail -30
```

### 4.5 Commit

```bash
cd /Users/rohanthomas/Shipyard && git add server/websocket.py tests/test_connection_manager.py && git commit -m "feat: add ConnectionManager for WebSocket state and message routing"
```

---

## Task 5: WebSocket Endpoint — FastAPI route, connect/disconnect, heartbeat

### 5.1 Write Tests

**File:** `tests/test_websocket_endpoint.py`

```python
"""Tests for the WebSocket endpoint at /ws/{project_id}."""
import asyncio
import json
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from store.sqlite import SQLiteSessionStore
from store.models import Project
from agent.events import EventBus
from server.websocket import ConnectionManager


@pytest.fixture
def app_with_ws(tmp_path):
    """Create a test app with WebSocket support wired up."""
    db_path = str(tmp_path / "test_ws.db")
    os.environ["SHIPYARD_DB_PATH"] = db_path

    import importlib
    import server.main as main_module
    importlib.reload(main_module)
    from server.main import app

    # We need to manually set up state since TestClient doesn't trigger lifespan reliably
    # Use sync setup via asyncio.run
    store = SQLiteSessionStore(db_path)
    loop = asyncio.new_event_loop()
    loop.run_until_complete(store.initialize())

    # Create a test project
    project = Project(id="test-proj", name="Test", path="/tmp/test")
    loop.run_until_complete(store.create_project(project))
    loop.close()

    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)

    app.state.store = store
    app.state.event_bus = event_bus
    app.state.conn_manager = conn_manager

    yield app, store, event_bus, conn_manager


def test_websocket_connect_valid_project(app_with_ws):
    """WebSocket connection to valid project_id should succeed."""
    app, store, event_bus, conn_manager = app_with_ws

    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-proj") as ws:
            # Connection succeeded — send a subscribe message
            ws.send_json({"action": "subscribe", "run_id": "r1"})
            # Close cleanly
            ws.close()


def test_websocket_connect_invalid_project(app_with_ws):
    """WebSocket connection to non-existent project_id should close with 4004."""
    app, store, event_bus, conn_manager = app_with_ws

    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/nonexistent") as ws:
                # Should not get here — connection should be rejected
                pytest.fail("Expected connection to be rejected")
        except Exception:
            # Connection rejected as expected
            pass


def test_websocket_subscribe_and_receive_event(app_with_ws):
    """Client should receive events after subscribing to a run."""
    app, store, event_bus, conn_manager = app_with_ws

    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-proj") as ws:
            # Subscribe to run
            ws.send_json({"action": "subscribe", "run_id": "r1"})

            # We cannot easily push events from outside in sync test,
            # but we can verify the subscribe was processed by checking
            # that the connection manager has the subscription.
            # The integration test (Task 6) will cover full flow.
            ws.close()


def test_websocket_reconnect_replays(app_with_ws):
    """Client sending reconnect should receive replayed events."""
    app, store, event_bus, conn_manager = app_with_ws

    # Pre-populate events in store
    from store.models import Event
    loop = asyncio.new_event_loop()
    e1 = Event(run_id="r1", type="status", seq=1, data={"msg": "step1"})
    e2 = Event(run_id="r1", type="diff", seq=2, data={"file": "a.py"})
    loop.run_until_complete(store.append_event(e1))
    loop.run_until_complete(store.append_event(e2))
    loop.close()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-proj") as ws:
            ws.send_json({"action": "reconnect", "run_id": "r1", "last_seq": 0})

            # Should receive replayed events
            msg1 = ws.receive_json()
            assert msg1["type"] == "status"
            assert msg1["seq"] == 1

            msg2 = ws.receive_json()
            assert msg2["type"] == "diff"
            assert msg2["seq"] == 2

            ws.close()


def test_websocket_reconnect_partial_replay(app_with_ws):
    """Reconnect with last_seq=1 should only replay events after seq 1."""
    app, store, event_bus, conn_manager = app_with_ws

    from store.models import Event
    loop = asyncio.new_event_loop()
    e1 = Event(run_id="r1", type="status", seq=1, data={"msg": "step1"})
    e2 = Event(run_id="r1", type="diff", seq=2, data={"file": "a.py"})
    e3 = Event(run_id="r1", type="error", seq=3, data={"msg": "fail"})
    loop.run_until_complete(store.append_event(e1))
    loop.run_until_complete(store.append_event(e2))
    loop.run_until_complete(store.append_event(e3))
    loop.close()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-proj") as ws:
            ws.send_json({"action": "reconnect", "run_id": "r1", "last_seq": 1})

            msg1 = ws.receive_json()
            assert msg1["seq"] == 2
            msg2 = ws.receive_json()
            assert msg2["seq"] == 3

            ws.close()
```

### 5.2 Run Tests (expect failures — endpoint not wired)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_websocket_endpoint.py -v 2>&1 | head -40
```

### 5.3 Implement

**File:** `server/main.py` — Add WebSocket route and update lifespan

Replace the entire file:

```python
import os
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from agent.graph import build_graph
from agent.router import ModelRouter
from agent.events import EventBus
from server.websocket import ConnectionManager
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run

logger = logging.getLogger(__name__)

runs: dict[str, dict] = {}

DB_PATH = os.environ.get("SHIPYARD_DB_PATH", "shipyard.db")

HEARTBEAT_INTERVAL = 15  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SQLiteSessionStore(DB_PATH)
    await store.initialize()

    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)

    # Wire the event bus send callback to the connection manager
    # We need project_id context, so we store it on event_bus for now
    # and route through conn_manager
    app.state.store = store
    app.state.router = ModelRouter()
    app.state.graph = build_graph()
    app.state.event_bus = event_bus
    app.state.conn_manager = conn_manager

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(_heartbeat_loop(conn_manager))

    yield

    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    await event_bus.shutdown()
    await store.close()


async def _heartbeat_loop(conn_manager: ConnectionManager) -> None:
    """Send heartbeat to all connected clients at fixed interval."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        try:
            await conn_manager.broadcast_heartbeat()
        except Exception:
            logger.exception("Error in heartbeat loop")


app = FastAPI(title="Shipyard Agent", lifespan=lifespan)


class InstructionRequest(BaseModel):
    instruction: str
    working_directory: str
    context: dict = {}
    project_id: str | None = None


class InstructionResponse(BaseModel):
    run_id: str
    status: str


class CreateProjectRequest(BaseModel):
    name: str
    path: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/instruction", response_model=InstructionResponse)
async def submit_instruction(req: InstructionRequest):
    store: SQLiteSessionStore = app.state.store
    router: ModelRouter = app.state.router

    run_id = str(uuid.uuid4())[:8]
    runs[run_id] = {"status": "running", "result": None}

    # Persist Run to store
    project_id = req.project_id or "default"
    db_run = Run(
        id=run_id,
        project_id=project_id,
        instruction=req.instruction,
        status="running",
        context=req.context,
    )
    try:
        await store.create_run(db_run)
    except Exception:
        pass  # store may not have the project; proceed anyway

    async def execute():
        try:
            graph = app.state.graph
            initial_state = {
                "messages": [],
                "instruction": req.instruction,
                "working_directory": req.working_directory,
                "context": req.context,
                "plan": [],
                "current_step": 0,
                "file_buffer": {},
                "edit_history": [],
                "error_state": None,
                "is_parallel": False,
                "parallel_batches": [],
                "sequential_first": [],
                "has_conflicts": False,
            }
            config = {"configurable": {"store": store, "router": router}}
            result = await graph.ainvoke(initial_state, config=config)
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return InstructionResponse(run_id=run_id, status="running")


@app.get("/status/{run_id}")
async def get_status(run_id: str):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = runs[run_id]
    return {"run_id": run_id, "status": run["status"], "result": run.get("result")}


@app.post("/instruction/{run_id}")
async def continue_run(run_id: str, req: InstructionRequest):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    store: SQLiteSessionStore = app.state.store
    router: ModelRouter = app.state.router
    runs[run_id]["status"] = "running"

    async def execute():
        try:
            graph = app.state.graph
            state = runs[run_id].get("result", {})
            if isinstance(state, str):
                state = {}
            state["instruction"] = req.instruction
            state["context"] = req.context
            state["error_state"] = None
            config = {"configurable": {"store": store, "router": router}}
            result = await graph.ainvoke(state, config=config)
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return {"run_id": run_id, "status": "running"}


@app.get("/projects")
async def list_projects():
    store: SQLiteSessionStore = app.state.store
    projects = await store.list_projects()
    return [p.model_dump() for p in projects]


@app.post("/projects", status_code=201)
async def create_project(req: CreateProjectRequest):
    store: SQLiteSessionStore = app.state.store
    project = Project(name=req.name, path=req.path)
    created = await store.create_project(project)
    return created.model_dump()


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time event streaming."""
    store: SQLiteSessionStore = app.state.store
    conn_manager: ConnectionManager = app.state.conn_manager

    # Validate project exists
    project = await store.get_project(project_id)
    if project is None:
        await websocket.close(code=4004, reason="Project not found")
        return

    await websocket.accept()
    await conn_manager.connect(websocket, project_id)

    try:
        while True:
            data = await websocket.receive_json()
            await conn_manager.handle_client_message(websocket, data)
    except WebSocketDisconnect:
        await conn_manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error for project %s", project_id)
        await conn_manager.disconnect(websocket)
```

### 5.4 Run Tests (expect pass)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_websocket_endpoint.py -v 2>&1 | tail -30
```

### 5.5 Commit

```bash
cd /Users/rohanthomas/Shipyard && git add server/main.py tests/test_websocket_endpoint.py && git commit -m "feat: add WebSocket endpoint with project validation and reconnect replay"
```

---

## Task 6: Server Wiring — Integration test for full event flow

### 6.1 Write Tests

**File:** `tests/test_ws_integration.py`

```python
"""Integration tests for the full WebSocket event bus pipeline.

Tests the flow: EventBus.emit -> ConnectionManager.send_to_subscribed -> WebSocket client.
"""
import asyncio
import json
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from store.sqlite import SQLiteSessionStore
from store.models import Project, Event
from agent.events import EventBus
from server.websocket import ConnectionManager


@pytest_asyncio.fixture
async def stack(tmp_path):
    """Set up the full store -> event_bus -> connection_manager stack."""
    db_path = str(tmp_path / "integration.db")
    store = SQLiteSessionStore(db_path)
    await store.initialize()

    project = Project(id="proj1", name="Integration", path="/tmp/int")
    await store.create_project(project)

    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)

    # Wire the event bus to send through the connection manager
    async def send_callback(event: Event):
        await conn_manager.send_to_subscribed(event, project_id="proj1")

    event_bus.set_send_callback(send_callback)
    event_bus.start_batcher()

    yield store, event_bus, conn_manager

    await event_bus.shutdown()
    await store.close()


def _mock_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# --- Full pipeline tests ---

@pytest.mark.asyncio
async def test_p0_event_reaches_client(stack):
    """P0 error event emitted by bus arrives at subscribed WebSocket client."""
    store, bus, manager = stack
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(run_id="r1", type="error", data={"msg": "boom"})
    await bus.emit(event)

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "error"
    assert payload["data"]["msg"] == "boom"
    assert payload["seq"] == 1


@pytest.mark.asyncio
async def test_p1_stream_event_reaches_client_after_flush(stack):
    """P1 stream event arrives at client after batcher flush."""
    store, bus, manager = stack
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(run_id="r1", type="stream", data={"token": "hello"})
    await bus.emit(event)

    # Not sent yet (in batcher)
    ws.send_json.assert_not_called()

    # Wait for batcher flush
    await asyncio.sleep(0.1)

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "stream"
    assert payload["data"]["token"] == "hello"


@pytest.mark.asyncio
async def test_p1_stream_not_persisted(stack):
    """Stream events should not be in the store after emit."""
    store, bus, manager = stack

    event = Event(run_id="r1", type="stream", data={"token": "x"})
    await bus.emit(event)

    events = await store.replay_events("r1")
    assert len(events) == 0


@pytest.mark.asyncio
async def test_p2_event_sent_on_boundary(stack):
    """P2 status event sent only when flush_node_boundary is called."""
    store, bus, manager = stack
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(run_id="r1", type="status", data={"step": 1})
    await bus.emit(event)

    ws.send_json.assert_not_called()

    await bus.flush_node_boundary()

    ws.send_json.assert_called_once()
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "status"


@pytest.mark.asyncio
async def test_p2_event_persisted(stack):
    """P2 events should be persisted even before boundary flush."""
    store, bus, manager = stack

    event = Event(run_id="r1", type="status", data={"step": 1})
    await bus.emit(event)

    events = await store.replay_events("r1")
    assert len(events) == 1
    assert events[0].type == "status"


@pytest.mark.asyncio
async def test_reconnect_replays_persisted_events(stack):
    """Reconnecting client receives persisted events after last_seq."""
    store, bus, manager = stack

    # Emit events (P0 and P2 get persisted)
    e1 = Event(run_id="r1", type="error", data={"msg": "err1"})
    e2 = Event(run_id="r1", type="status", data={"step": 2})
    e3 = Event(run_id="r1", type="error", data={"msg": "err2"})
    await bus.emit(e1)
    await bus.emit(e2)
    await bus.emit(e3)

    # New client connects and sends reconnect
    ws = _mock_ws()
    await manager.connect(ws, "proj1")
    await manager.handle_client_message(ws, {
        "action": "reconnect",
        "run_id": "r1",
        "last_seq": 1,
    })

    # Should have received events with seq > 1
    assert ws.send_json.call_count == 2
    calls = [c[0][0] for c in ws.send_json.call_args_list]
    seqs = [c["seq"] for c in calls]
    assert seqs == [2, 3]


@pytest.mark.asyncio
async def test_seq_monotonic_across_multiple_emits(stack):
    """Seq should be monotonically increasing across all event types."""
    store, bus, manager = stack

    events = []
    for i, t in enumerate(["error", "stream", "status", "diff", "approval"]):
        e = Event(run_id="r1", type=t, data={"i": i})
        await bus.emit(e)
        events.append(e)

    seqs = [e.seq for e in events]
    assert seqs == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_multiple_runs_independent_seq(stack):
    """Different runs should have independent seq counters."""
    store, bus, manager = stack

    e1 = Event(run_id="r1", type="error")
    e2 = Event(run_id="r2", type="error")
    e3 = Event(run_id="r1", type="status")
    await bus.emit(e1)
    await bus.emit(e2)
    await bus.emit(e3)

    assert e1.seq == 1
    assert e2.seq == 1
    assert e3.seq == 2


@pytest.mark.asyncio
async def test_snapshot_includes_last_seq(stack):
    """Snapshot should reflect the latest seq for the run."""
    store, bus, manager = stack

    e1 = Event(run_id="r1", type="error")
    e2 = Event(run_id="r1", type="status")
    await bus.emit(e1)
    await bus.emit(e2)

    snap = bus.get_snapshot("r1", {"status": "running", "plan": ["a"], "current_step": 1})
    assert snap["last_seq"] == 2
    assert snap["status"] == "running"
    assert snap["plan"] == ["a"]


@pytest.mark.asyncio
async def test_dead_connection_cleaned_up(stack):
    """If a client send fails, the connection should be removed."""
    store, bus, manager = stack
    ws = _mock_ws()
    ws.send_json.side_effect = Exception("Connection lost")
    await manager.connect(ws, "proj1")
    state = manager._connections["proj1"][0]
    state.subscribed_runs.add("r1")

    event = Event(run_id="r1", type="error", data={"msg": "test"})
    await bus.emit(event)

    # Connection should have been cleaned up
    conns = manager._connections.get("proj1", [])
    assert len(conns) == 0


@pytest.mark.asyncio
async def test_heartbeat_reaches_all_clients(stack):
    """Heartbeat should be sent to all connected clients."""
    store, bus, manager = stack
    ws1 = _mock_ws()
    ws2 = _mock_ws()
    await manager.connect(ws1, "proj1")
    await manager.connect(ws2, "proj1")

    await manager.broadcast_heartbeat()

    assert ws1.send_json.call_count == 1
    assert ws2.send_json.call_count == 1
    assert ws1.send_json.call_args[0][0]["type"] == "heartbeat"
```

### 6.2 Run Tests (expect pass)

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_ws_integration.py -v 2>&1 | tail -30
```

### 6.3 Run All Tests

```bash
cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_store_seq.py tests/test_store.py tests/test_token_batcher.py tests/test_event_bus.py tests/test_connection_manager.py tests/test_websocket_endpoint.py tests/test_ws_integration.py tests/test_server.py -v 2>&1 | tail -50
```

### 6.4 Commit

```bash
cd /Users/rohanthomas/Shipyard && git add tests/test_ws_integration.py && git commit -m "test: add integration tests for full WebSocket event bus pipeline"
```

---

## Summary of Files Modified/Created

| File | Action | Description |
|---|---|---|
| `store/models.py` | Modified | Add `seq: int = 0` field to Event |
| `store/protocol.py` | Modified | Change `replay_events` to use `after_seq: int`, add `get_max_seq` |
| `store/sqlite.py` | Modified | Add `seq` column, `idx_events_run_seq` index, update `append_event`/`replay_events`, add `get_max_seq` |
| `agent/events.py` | Created | `TokenBatcher` and `EventBus` classes |
| `server/websocket.py` | Created | `WebSocketState` dataclass and `ConnectionManager` class |
| `server/main.py` | Modified | Add `EventBus`/`ConnectionManager` init in lifespan, heartbeat task, WebSocket route |
| `tests/test_store_seq.py` | Created | Tests for seq field and after_seq replay |
| `tests/test_store.py` | Modified | Fix `test_replay_events_after_cursor` for new signature |
| `tests/test_token_batcher.py` | Created | Tests for TokenBatcher flush behavior |
| `tests/test_event_bus.py` | Created | Tests for EventBus priority routing, seq, replay, snapshot |
| `tests/test_connection_manager.py` | Created | Tests for ConnectionManager state and message handling |
| `tests/test_websocket_endpoint.py` | Created | Tests for FastAPI WebSocket route |
| `tests/test_ws_integration.py` | Created | End-to-end integration tests for full pipeline |

## Dependency Notes

No new pip dependencies are needed. `FastAPI` already includes WebSocket support via Starlette. `asyncio` is stdlib. `aiosqlite` is already installed. For the sync `TestClient` WebSocket tests, `starlette.testclient` is included with FastAPI.

## Commit Sequence

1. `feat: add seq field to Event model, update replay_events to use after_seq`
2. `feat: add TokenBatcher with background flush loop`
3. `feat: add EventBus with priority routing, seq assignment, and replay`
4. `feat: add ConnectionManager for WebSocket state and message routing`
5. `feat: add WebSocket endpoint with project validation and reconnect replay`
6. `test: add integration tests for full WebSocket event bus pipeline`
