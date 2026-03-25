# Sub-phase 2a-2: Approval State Machine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an edit approval state machine with idempotent transitions, separate approve/apply steps, and LangGraph checkpoint integration.

**Architecture:** ApprovalManager owns the edit lifecycle state machine (proposed->approved->applied->committed, proposed->rejected). approve() and apply_edit() are separate operations. Idempotent via stable op_id. Integrates with EventBus for real-time notifications and with the editor node for LangGraph flow control.

**Tech Stack:** Python, Pydantic, aiosqlite, FastAPI

**Spec:** `docs/superpowers/specs/2026-03-24-phase2a-backend-features-design.md` (Sub-phase 2a-2)

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

**Prerequisite:** Sub-phase 2a-1 (WebSocket Event Bus) must be complete. `agent/events.py` (EventBus) and `server/websocket.py` (ConnectionManager) must exist.

---

## File Structure

### New Files
- `agent/approval.py` — ApprovalManager class with state machine logic
- `tests/test_approval.py` — Unit tests for ApprovalManager
- `tests/test_approval_store.py` — Store-level tests for new get_edit, migration, index
- `tests/test_approval_rest.py` — REST endpoint tests for PATCH /runs/:id/edits/:edit_id
- `tests/test_approval_ws.py` — WebSocket integration tests for approve/reject messages

### Modified Files
- `store/models.py` — Add `Literal` status validation and `last_op_id` field to EditRecord
- `store/protocol.py` — Add `get_edit(edit_id)` method signature
- `store/sqlite.py` — Add `get_edit()` impl, migration for `last_op_id`, index, update `create_edit`/`update_edit_status` for new fields
- `agent/state.py` — Add `autonomy_mode` and `branch` fields to AgentState
- `agent/nodes/editor.py` — Integrate approval gate (supervised vs autonomous mode)
- `server/main.py` — Add PATCH `/runs/{run_id}/edits/{edit_id}` endpoint, wire ApprovalManager

---

## Task 1: Store Prerequisites — EditRecord Model Updates

**Files:**
- Modify: `store/models.py`
- New: `tests/test_approval_store.py`

- [ ] **Step 1: Write tests for EditRecord model updates**

Create `tests/test_approval_store.py`. These tests validate the model-level changes before touching the database.

```python
"""Tests for approval state machine store prerequisites."""
import pytest
from pydantic import ValidationError
from store.models import EditRecord, EDIT_STATUSES


def test_edit_statuses_literal_type():
    """EDIT_STATUSES includes all five lifecycle states."""
    from typing import get_args
    allowed = get_args(EDIT_STATUSES)
    assert set(allowed) == {"proposed", "approved", "rejected", "applied", "committed"}


def test_edit_record_default_status_is_proposed():
    """New EditRecord defaults to proposed status."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    assert edit.status == "proposed"


def test_edit_record_accepts_valid_statuses():
    """EditRecord accepts all valid statuses without error."""
    for status in ("proposed", "approved", "rejected", "applied", "committed"):
        edit = EditRecord(run_id="r1", file_path="a.py", status=status)
        assert edit.status == status


def test_edit_record_rejects_invalid_status():
    """EditRecord rejects statuses not in the Literal type."""
    with pytest.raises(ValidationError):
        EditRecord(run_id="r1", file_path="a.py", status="bogus")


def test_edit_record_last_op_id_defaults_to_none():
    """last_op_id defaults to None."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    assert edit.last_op_id is None


def test_edit_record_last_op_id_can_be_set():
    """last_op_id can be set to a string."""
    edit = EditRecord(run_id="r1", file_path="a.py", last_op_id="op_abc_approve")
    assert edit.last_op_id == "op_abc_approve"
```

- [ ] **Step 2: Update EditRecord in store/models.py**

Add the `EDIT_STATUSES` type alias and update `EditRecord`:

```python
from typing import Any, Literal

EDIT_STATUSES = Literal["proposed", "approved", "rejected", "applied", "committed"]


class EditRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    file_path: str
    step: int = 0
    anchor: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    status: EDIT_STATUSES = "proposed"
    approved_at: datetime | None = None
    last_op_id: str | None = None
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_approval_store.py -v
```

---

## Task 2: Store Prerequisites — get_edit, Migration, Index

**Files:**
- Modify: `store/protocol.py`
- Modify: `store/sqlite.py`
- Modify: `tests/test_approval_store.py`

- [ ] **Step 1: Add store-level tests to test_approval_store.py**

Append these tests to the existing file:

```python
import pytest_asyncio
from store.sqlite import SQLiteSessionStore


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test_approval.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_get_edit_returns_edit_by_id(store):
    """get_edit returns a single EditRecord by its id."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    await store.create_edit(edit)
    fetched = await store.get_edit(edit.id)
    assert fetched is not None
    assert fetched.id == edit.id
    assert fetched.file_path == "a.py"


@pytest.mark.asyncio
async def test_get_edit_returns_none_for_missing(store):
    """get_edit returns None when edit_id does not exist."""
    fetched = await store.get_edit("nonexistent")
    assert fetched is None


@pytest.mark.asyncio
async def test_create_edit_persists_last_op_id(store):
    """create_edit persists the last_op_id field."""
    edit = EditRecord(run_id="r1", file_path="a.py", last_op_id="op_abc_approve")
    await store.create_edit(edit)
    fetched = await store.get_edit(edit.id)
    assert fetched.last_op_id == "op_abc_approve"


@pytest.mark.asyncio
async def test_update_edit_status_with_op_id(store):
    """update_edit_status persists both status and last_op_id."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    await store.create_edit(edit)
    await store.update_edit_status(edit.id, "approved", last_op_id="op_abc_approve")
    fetched = await store.get_edit(edit.id)
    assert fetched.status == "approved"
    assert fetched.last_op_id == "op_abc_approve"


@pytest.mark.asyncio
async def test_get_edits_by_run_id_and_status(store):
    """get_edits can filter by status when provided."""
    e1 = EditRecord(run_id="r1", file_path="a.py", status="proposed")
    e2 = EditRecord(run_id="r1", file_path="b.py", status="approved")
    e3 = EditRecord(run_id="r1", file_path="c.py", status="proposed")
    await store.create_edit(e1)
    await store.create_edit(e2)
    await store.create_edit(e3)
    proposed = await store.get_edits("r1", status="proposed")
    assert len(proposed) == 2
    all_edits = await store.get_edits("r1")
    assert len(all_edits) == 3


@pytest.mark.asyncio
async def test_idx_edits_run_status_index_exists(store):
    """The idx_edits_run_status index exists on the edits table."""
    async with store._db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_edits_run_status'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None
```

- [ ] **Step 2: Add get_edit to store/protocol.py**

Add after the existing `update_edit_status` line:

```python
    async def get_edit(self, edit_id: str) -> EditRecord | None: ...
    async def get_edits(self, run_id: str, status: str | None = None) -> list[EditRecord]: ...
    async def update_edit_status(self, edit_id: str, status: str, last_op_id: str | None = None) -> None: ...
```

This replaces the existing `get_edits` and `update_edit_status` signatures (adding the optional parameters).

- [ ] **Step 3: Update store/sqlite.py**

Update the `_SCHEMA` edits table to add `last_op_id` column and index:

```python
CREATE TABLE IF NOT EXISTS edits (
    id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
    file_path TEXT NOT NULL, step INTEGER DEFAULT 0,
    anchor TEXT, old_content TEXT, new_content TEXT,
    status TEXT DEFAULT 'proposed', approved_at TIMESTAMP,
    last_op_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_edits_run_status ON edits(run_id, status);
```

Add the `get_edit` method to `SQLiteSessionStore`:

```python
    async def get_edit(self, edit_id: str) -> EditRecord | None:
        async with self._db.execute(
            "SELECT * FROM edits WHERE id = ?", (edit_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return EditRecord(**dict(row))
```

Update `create_edit` to persist `last_op_id`:

```python
    async def create_edit(self, edit: EditRecord) -> EditRecord:
        await self._db.execute(
            """INSERT INTO edits
               (id, run_id, file_path, step, anchor, old_content, new_content,
                status, approved_at, last_op_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                edit.id, edit.run_id, edit.file_path, edit.step,
                edit.anchor, edit.old_content, edit.new_content, edit.status,
                edit.approved_at.isoformat() if edit.approved_at else None,
                edit.last_op_id,
            ),
        )
        await self._db.commit()
        return edit
```

Update `get_edits` to accept optional `status` filter:

```python
    async def get_edits(self, run_id: str, status: str | None = None) -> list[EditRecord]:
        if status is not None:
            async with self._db.execute(
                "SELECT * FROM edits WHERE run_id = ? AND status = ?", (run_id, status)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with self._db.execute(
                "SELECT * FROM edits WHERE run_id = ?", (run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [EditRecord(**dict(row)) for row in rows]
```

Update `update_edit_status` to accept optional `last_op_id`:

```python
    async def update_edit_status(self, edit_id: str, status: str, last_op_id: str | None = None) -> None:
        if last_op_id is not None:
            await self._db.execute(
                "UPDATE edits SET status = ?, last_op_id = ? WHERE id = ?",
                (status, last_op_id, edit_id),
            )
        else:
            await self._db.execute(
                "UPDATE edits SET status = ? WHERE id = ?", (status, edit_id)
            )
        await self._db.commit()
```

- [ ] **Step 4: Run tests, verify pass**

```bash
python -m pytest tests/test_approval_store.py -v
python -m pytest tests/test_store.py -v  # ensure no regressions
```

---

## Task 3: AgentState Update

**Files:**
- Modify: `agent/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write tests for new AgentState fields**

Add to `tests/test_state.py`:

```python
def test_agent_state_has_autonomy_mode():
    """AgentState includes autonomy_mode field."""
    from agent.state import AgentState
    state: AgentState = {
        "messages": [],
        "instruction": "test",
        "working_directory": "/tmp",
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "supervised",
        "branch": "feature/test",
    }
    assert state["autonomy_mode"] == "supervised"
    assert state["branch"] == "feature/test"


def test_agent_state_autonomy_mode_autonomous():
    """autonomy_mode can be set to autonomous."""
    from agent.state import AgentState
    state: AgentState = {
        "messages": [],
        "instruction": "test",
        "working_directory": "/tmp",
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "autonomous",
        "branch": "",
    }
    assert state["autonomy_mode"] == "autonomous"
```

- [ ] **Step 2: Update agent/state.py**

Add `autonomy_mode` and `branch` to `AgentState`:

```python
from typing import Annotated, Optional, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    instruction: str
    working_directory: str
    context: dict
    plan: list[str]
    current_step: int
    file_buffer: dict[str, str]
    edit_history: list[dict]
    error_state: Optional[str]
    # Multi-agent coordination fields
    is_parallel: bool
    parallel_batches: list[list[int]]
    sequential_first: list[int]
    has_conflicts: bool
    model_usage: dict[str, int]
    # Approval state machine fields
    autonomy_mode: str          # "supervised" | "autonomous"
    branch: str                 # current git branch name
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_state.py -v
```

---

## Task 4: ApprovalManager Core — State Machine Transitions and Idempotency

**Files:**
- New: `agent/approval.py`
- New: `tests/test_approval.py`

- [ ] **Step 1: Write tests for state machine transitions and idempotency**

Create `tests/test_approval.py`:

```python
"""Tests for ApprovalManager core: transitions, idempotency, error handling."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from store.models import EditRecord
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager, InvalidTransitionError


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test_approval.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest_asyncio.fixture
async def manager(store, event_bus):
    return ApprovalManager(store=store, event_bus=event_bus)


# --- is_valid_transition ---

class TestIsValidTransition:
    def test_proposed_to_approved(self, manager):
        assert manager.is_valid_transition("proposed", "approved") is True

    def test_proposed_to_rejected(self, manager):
        assert manager.is_valid_transition("proposed", "rejected") is True

    def test_approved_to_applied(self, manager):
        assert manager.is_valid_transition("approved", "applied") is True

    def test_applied_to_committed(self, manager):
        assert manager.is_valid_transition("applied", "committed") is True

    def test_proposed_to_applied_is_invalid(self, manager):
        """Cannot skip approved and go directly to applied."""
        assert manager.is_valid_transition("proposed", "applied") is False

    def test_approved_to_rejected_is_invalid(self, manager):
        """Can only reject from proposed."""
        assert manager.is_valid_transition("approved", "rejected") is False

    def test_committed_to_anything_is_invalid(self, manager):
        """committed is a terminal state."""
        assert manager.is_valid_transition("committed", "proposed") is False
        assert manager.is_valid_transition("committed", "approved") is False

    def test_rejected_to_anything_is_invalid(self, manager):
        """rejected is a terminal state."""
        assert manager.is_valid_transition("rejected", "proposed") is False
        assert manager.is_valid_transition("rejected", "approved") is False

    def test_same_state_is_invalid(self, manager):
        assert manager.is_valid_transition("proposed", "proposed") is False


# --- propose_edit ---

class TestProposeEdit:
    @pytest.mark.asyncio
    async def test_propose_edit_creates_with_proposed_status(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        result = await manager.propose_edit("r1", edit)
        assert result.status == "proposed"
        fetched = await store.get_edit(result.id)
        assert fetched is not None
        assert fetched.status == "proposed"

    @pytest.mark.asyncio
    async def test_propose_edit_emits_event(self, manager, event_bus):
        edit = EditRecord(run_id="r1", file_path="a.py")
        await manager.propose_edit("r1", edit)
        event_bus.emit.assert_called_once()
        call_args = event_bus.emit.call_args
        assert call_args[0][0] == "edit.proposed"


# --- approve ---

class TestApprove:
    @pytest.mark.asyncio
    async def test_approve_transitions_proposed_to_approved(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        op_id = f"op_{created.id}_approve"
        result = await manager.approve(created.id, op_id)
        assert result.status == "approved"
        fetched = await store.get_edit(created.id)
        assert fetched.status == "approved"
        assert fetched.last_op_id == op_id

    @pytest.mark.asyncio
    async def test_approve_idempotent_with_same_op_id(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        op_id = f"op_{created.id}_approve"
        result1 = await manager.approve(created.id, op_id)
        result2 = await manager.approve(created.id, op_id)
        assert result1.status == "approved"
        assert result2.status == "approved"

    @pytest.mark.asyncio
    async def test_approve_emits_event(self, manager, event_bus):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        op_id = f"op_{created.id}_approve"
        await manager.approve(created.id, op_id)
        # Two events: propose + approve
        assert event_bus.emit.call_count == 2
        second_call = event_bus.emit.call_args_list[1]
        assert second_call[0][0] == "edit.approved"

    @pytest.mark.asyncio
    async def test_approve_raises_on_invalid_transition(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        op_id_approve = f"op_{created.id}_approve"
        await manager.approve(created.id, op_id_approve)
        # Try to approve again with a different op_id (already approved)
        with pytest.raises(InvalidTransitionError):
            await manager.approve(created.id, "op_different_approve")

    @pytest.mark.asyncio
    async def test_approve_raises_on_nonexistent_edit(self, manager):
        with pytest.raises(ValueError, match="not found"):
            await manager.approve("nonexistent", "op_x_approve")


# --- reject ---

class TestReject:
    @pytest.mark.asyncio
    async def test_reject_transitions_proposed_to_rejected(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        op_id = f"op_{created.id}_reject"
        result = await manager.reject(created.id, op_id)
        assert result.status == "rejected"
        fetched = await store.get_edit(created.id)
        assert fetched.status == "rejected"
        assert fetched.last_op_id == op_id

    @pytest.mark.asyncio
    async def test_reject_idempotent_with_same_op_id(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        op_id = f"op_{created.id}_reject"
        result1 = await manager.reject(created.id, op_id)
        result2 = await manager.reject(created.id, op_id)
        assert result1.status == "rejected"
        assert result2.status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_raises_on_approved_edit(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        await manager.approve(created.id, f"op_{created.id}_approve")
        with pytest.raises(InvalidTransitionError):
            await manager.reject(created.id, f"op_{created.id}_reject")

    @pytest.mark.asyncio
    async def test_reject_emits_event(self, manager, event_bus):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        await manager.reject(created.id, f"op_{created.id}_reject")
        second_call = event_bus.emit.call_args_list[1]
        assert second_call[0][0] == "edit.rejected"
```

- [ ] **Step 2: Create agent/approval.py with core logic**

```python
"""Approval state machine for edit lifecycle management."""
from __future__ import annotations
from store.models import EditRecord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from store.protocol import SessionStore
    from agent.events import EventBus


class InvalidTransitionError(Exception):
    """Raised when a state transition is not valid."""
    pass


# Valid state transitions: {current_state: [allowed_target_states]}
_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["approved", "rejected"],
    "approved": ["applied"],
    "applied": ["committed"],
    "rejected": [],
    "committed": [],
}


class ApprovalManager:
    """Manages the edit approval lifecycle state machine.

    State diagram:
        proposed -> approved -> applied -> committed
            |
            v
        rejected

    Idempotency: Each mutation accepts a stable op_id. If the edit's
    last_op_id matches the incoming op_id, the call is a no-op and
    returns the current state.
    """

    def __init__(self, store: SessionStore, event_bus: EventBus):
        self.store = store
        self.event_bus = event_bus

    def is_valid_transition(self, current: str, target: str) -> bool:
        """Check if transitioning from current to target is allowed."""
        return target in _TRANSITIONS.get(current, [])

    async def propose_edit(self, run_id: str, edit: EditRecord) -> EditRecord:
        """Create an edit with proposed status and emit an event."""
        edit.status = "proposed"
        edit.run_id = run_id
        created = await self.store.create_edit(edit)
        await self.event_bus.emit("edit.proposed", {
            "edit_id": created.id,
            "run_id": run_id,
            "file_path": created.file_path,
        })
        return created

    async def _transition(self, edit_id: str, target: str, op_id: str, event_type: str) -> EditRecord:
        """Generic idempotent state transition.

        1. Fetch the edit (raise if not found).
        2. If last_op_id == op_id, return current state (idempotent no-op).
        3. If transition is invalid, raise InvalidTransitionError.
        4. Apply transition, set last_op_id, persist, emit event.
        """
        edit = await self.store.get_edit(edit_id)
        if edit is None:
            raise ValueError(f"Edit {edit_id} not found")

        # Idempotency check
        if edit.last_op_id == op_id:
            return edit

        if not self.is_valid_transition(edit.status, target):
            raise InvalidTransitionError(
                f"Cannot transition from '{edit.status}' to '{target}' "
                f"for edit {edit_id}"
            )

        await self.store.update_edit_status(edit_id, target, last_op_id=op_id)
        edit = await self.store.get_edit(edit_id)

        await self.event_bus.emit(event_type, {
            "edit_id": edit_id,
            "run_id": edit.run_id,
            "status": target,
        })
        return edit

    async def approve(self, edit_id: str, op_id: str) -> EditRecord:
        """Transition proposed -> approved. Only changes status, does NOT apply."""
        return await self._transition(edit_id, "approved", op_id, "edit.approved")

    async def reject(self, edit_id: str, op_id: str) -> EditRecord:
        """Transition proposed -> rejected."""
        return await self._transition(edit_id, "rejected", op_id, "edit.rejected")
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_approval.py -v
```

---

## Task 5: ApprovalManager — Separate approve/apply and apply_edit

**Files:**
- Modify: `agent/approval.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Write tests for apply_edit**

Append to `tests/test_approval.py`:

```python
import os
import tempfile


class TestApplyEdit:
    @pytest.mark.asyncio
    async def test_apply_edit_transitions_approved_to_applied(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py", old_content="old", new_content="new")
        created = await manager.propose_edit("r1", edit)
        await manager.approve(created.id, f"op_{created.id}_approve")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("old")
            f.flush()
            # Update file_path to the temp file
            await store._db.execute(
                "UPDATE edits SET file_path = ? WHERE id = ?", (f.name, created.id)
            )
            await store._db.commit()
        try:
            result = await manager.apply_edit(created.id)
            assert result.status == "applied"
            with open(f.name) as fh:
                assert fh.read() == "new"
        finally:
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_apply_edit_raises_on_proposed(self, manager, store):
        """Cannot apply an edit that is only proposed (not approved)."""
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        with pytest.raises(InvalidTransitionError):
            await manager.apply_edit(created.id)

    @pytest.mark.asyncio
    async def test_apply_edit_raises_on_rejected(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        await manager.reject(created.id, f"op_{created.id}_reject")
        with pytest.raises(InvalidTransitionError):
            await manager.apply_edit(created.id)

    @pytest.mark.asyncio
    async def test_apply_edit_file_write_failure_stays_approved(self, manager, store):
        """If file write fails, status stays approved (not applied)."""
        edit = EditRecord(
            run_id="r1",
            file_path="/nonexistent/path/file.py",
            old_content="old",
            new_content="new",
        )
        created = await manager.propose_edit("r1", edit)
        await manager.approve(created.id, f"op_{created.id}_approve")
        with pytest.raises(OSError):
            await manager.apply_edit(created.id)
        fetched = await store.get_edit(created.id)
        assert fetched.status == "approved"  # NOT applied

    @pytest.mark.asyncio
    async def test_apply_edit_emits_event(self, manager, store, event_bus):
        edit = EditRecord(run_id="r1", file_path="a.py", old_content="old", new_content="new")
        created = await manager.propose_edit("r1", edit)
        await manager.approve(created.id, f"op_{created.id}_approve")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("old")
            f.flush()
            await store._db.execute(
                "UPDATE edits SET file_path = ? WHERE id = ?", (f.name, created.id)
            )
            await store._db.commit()
        try:
            await manager.apply_edit(created.id)
            # Events: propose, approve, apply = 3 total
            assert event_bus.emit.call_count == 3
            last_call = event_bus.emit.call_args_list[2]
            assert last_call[0][0] == "edit.applied"
        finally:
            os.unlink(f.name)
```

- [ ] **Step 2: Implement apply_edit in agent/approval.py**

Add the `apply_edit` method to `ApprovalManager`:

```python
    async def apply_edit(self, edit_id: str) -> EditRecord:
        """Transition approved -> applied. Writes the edit to the filesystem.

        IMPORTANT: The file write happens BEFORE the status transition.
        If the write fails, the edit stays in 'approved' status so it
        can be retried without corrupting approval state.
        """
        edit = await self.store.get_edit(edit_id)
        if edit is None:
            raise ValueError(f"Edit {edit_id} not found")

        if not self.is_valid_transition(edit.status, "applied"):
            raise InvalidTransitionError(
                f"Cannot transition from '{edit.status}' to 'applied' "
                f"for edit {edit_id}"
            )

        # Write to filesystem FIRST — if this fails, status stays 'approved'
        self._write_edit_to_file(edit)

        # Only update status after successful write
        op_id = f"op_{edit_id}_apply"
        await self.store.update_edit_status(edit_id, "applied", last_op_id=op_id)
        edit = await self.store.get_edit(edit_id)

        await self.event_bus.emit("edit.applied", {
            "edit_id": edit_id,
            "run_id": edit.run_id,
            "file_path": edit.file_path,
            "status": "applied",
        })
        return edit

    @staticmethod
    def _write_edit_to_file(edit: EditRecord) -> None:
        """Apply the edit's content change to the filesystem.

        Raises OSError if the file cannot be read or written.
        """
        with open(edit.file_path, "r") as f:
            content = f.read()

        if edit.old_content is not None and edit.old_content in content:
            content = content.replace(edit.old_content, edit.new_content or "", 1)
        elif edit.new_content is not None:
            # Full file replacement if old_content is None
            content = edit.new_content

        with open(edit.file_path, "w") as f:
            f.write(content)
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_approval.py -v
```

---

## Task 6: ApprovalManager — mark_committed, auto_approve_pending, get_pending

**Files:**
- Modify: `agent/approval.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Write tests for mark_committed, auto_approve_pending, get_pending**

Append to `tests/test_approval.py`:

```python
class TestMarkCommitted:
    @pytest.mark.asyncio
    async def test_mark_committed_transitions_applied_to_committed(self, manager, store):
        edit = EditRecord(run_id="r1", file_path="a.py", old_content="x", new_content="y")
        created = await manager.propose_edit("r1", edit)
        await manager.approve(created.id, f"op_{created.id}_approve")
        # We need a real file for apply_edit
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x")
            f.flush()
            await store._db.execute(
                "UPDATE edits SET file_path = ? WHERE id = ?", (f.name, created.id)
            )
            await store._db.commit()
        try:
            await manager.apply_edit(created.id)
            await manager.mark_committed([created.id])
            fetched = await store.get_edit(created.id)
            assert fetched.status == "committed"
        finally:
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_mark_committed_skips_non_applied_edits(self, manager, store):
        """mark_committed silently skips edits not in 'applied' status."""
        edit = EditRecord(run_id="r1", file_path="a.py")
        created = await manager.propose_edit("r1", edit)
        # Still proposed, not applied
        await manager.mark_committed([created.id])
        fetched = await store.get_edit(created.id)
        assert fetched.status == "proposed"  # unchanged

    @pytest.mark.asyncio
    async def test_mark_committed_emits_event(self, manager, store, event_bus):
        edit = EditRecord(run_id="r1", file_path="a.py", old_content="x", new_content="y")
        created = await manager.propose_edit("r1", edit)
        await manager.approve(created.id, f"op_{created.id}_approve")
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x")
            f.flush()
            await store._db.execute(
                "UPDATE edits SET file_path = ? WHERE id = ?", (f.name, created.id)
            )
            await store._db.commit()
        try:
            await manager.apply_edit(created.id)
            event_bus.emit.reset_mock()
            await manager.mark_committed([created.id])
            event_bus.emit.assert_called_once()
            assert event_bus.emit.call_args[0][0] == "edit.committed"
        finally:
            os.unlink(f.name)


class TestAutoApprovePending:
    @pytest.mark.asyncio
    async def test_auto_approve_pending_approves_all_proposed(self, manager, store):
        e1 = EditRecord(run_id="r1", file_path="a.py")
        e2 = EditRecord(run_id="r1", file_path="b.py")
        await manager.propose_edit("r1", e1)
        await manager.propose_edit("r1", e2)
        approved = await manager.auto_approve_pending("r1")
        assert len(approved) == 2
        for edit in approved:
            assert edit.status == "approved"

    @pytest.mark.asyncio
    async def test_auto_approve_pending_does_not_apply(self, manager, store):
        """auto_approve_pending only approves, it does NOT apply (write to filesystem)."""
        edit = EditRecord(run_id="r1", file_path="a.py")
        await manager.propose_edit("r1", edit)
        approved = await manager.auto_approve_pending("r1")
        assert len(approved) == 1
        assert approved[0].status == "approved"  # not "applied"

    @pytest.mark.asyncio
    async def test_auto_approve_pending_ignores_other_statuses(self, manager, store):
        e1 = EditRecord(run_id="r1", file_path="a.py")
        e2 = EditRecord(run_id="r1", file_path="b.py")
        created1 = await manager.propose_edit("r1", e1)
        await manager.propose_edit("r1", e2)
        # Reject e1
        await manager.reject(created1.id, f"op_{created1.id}_reject")
        approved = await manager.auto_approve_pending("r1")
        assert len(approved) == 1
        assert approved[0].file_path == "b.py"

    @pytest.mark.asyncio
    async def test_auto_approve_pending_different_run_ids(self, manager, store):
        e1 = EditRecord(run_id="r1", file_path="a.py")
        e2 = EditRecord(run_id="r2", file_path="b.py")
        await manager.propose_edit("r1", e1)
        await manager.propose_edit("r2", e2)
        approved = await manager.auto_approve_pending("r1")
        assert len(approved) == 1
        assert approved[0].file_path == "a.py"


class TestGetPending:
    @pytest.mark.asyncio
    async def test_get_pending_returns_proposed_edits(self, manager, store):
        e1 = EditRecord(run_id="r1", file_path="a.py")
        e2 = EditRecord(run_id="r1", file_path="b.py")
        await manager.propose_edit("r1", e1)
        created2 = await manager.propose_edit("r1", e2)
        await manager.approve(created2.id, f"op_{created2.id}_approve")
        pending = await manager.get_pending("r1")
        assert len(pending) == 1
        assert pending[0].file_path == "a.py"

    @pytest.mark.asyncio
    async def test_get_pending_empty_when_no_proposed(self, manager, store):
        pending = await manager.get_pending("r1")
        assert pending == []
```

- [ ] **Step 2: Implement mark_committed, auto_approve_pending, get_pending**

Add to `ApprovalManager` in `agent/approval.py`:

```python
    async def mark_committed(self, edit_ids: list[str]) -> None:
        """Transition applied -> committed for a batch of edits after git commit.

        Silently skips edits not in 'applied' status.
        """
        for edit_id in edit_ids:
            edit = await self.store.get_edit(edit_id)
            if edit is None:
                continue
            if not self.is_valid_transition(edit.status, "committed"):
                continue
            op_id = f"op_{edit_id}_commit"
            await self.store.update_edit_status(edit_id, "committed", last_op_id=op_id)

        await self.event_bus.emit("edit.committed", {
            "edit_ids": edit_ids,
        })

    async def auto_approve_pending(self, run_id: str) -> list[EditRecord]:
        """Auto-approve all proposed edits for a run. Does NOT auto-apply.

        Returns the list of newly approved EditRecords.
        """
        pending = await self.get_pending(run_id)
        approved = []
        for edit in pending:
            op_id = f"op_{edit.id}_approve"
            result = await self.approve(edit.id, op_id)
            approved.append(result)
        return approved

    async def get_pending(self, run_id: str) -> list[EditRecord]:
        """Return all edits in 'proposed' status for a run."""
        return await self.store.get_edits(run_id, status="proposed")
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_approval.py -v
```

---

## Task 7: Editor Node Integration — Supervised/Autonomous Approval Gates

**Files:**
- Modify: `agent/nodes/editor.py`
- Modify: `tests/test_editor_node.py`

- [ ] **Step 1: Write tests for editor node approval integration**

Add to `tests/test_editor_node.py`:

```python
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from store.models import EditRecord
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager


@pytest_asyncio.fixture
async def store_for_editor(tmp_path):
    db_path = str(tmp_path / "test_editor.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def event_bus_for_editor():
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def approval_manager(store_for_editor, event_bus_for_editor):
    return ApprovalManager(store=store_for_editor, event_bus=event_bus_for_editor)


def make_config_with_approval(return_value, store, approval_manager, mode="supervised"):
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=return_value)
    return {
        "configurable": {
            "router": mock_router,
            "store": store,
            "approval_manager": approval_manager,
            "autonomy_mode": mode,
        }
    }


def make_supervised_state(tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()
    return {
        "messages": [],
        "instruction": "Add a due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "supervised",
        "branch": "",
    }


@pytest.mark.asyncio
async def test_editor_supervised_mode_proposes_and_waits(
    tmp_codebase, store_for_editor, approval_manager
):
    """In supervised mode, editor proposes an edit and returns waiting_for_human."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })
    state = make_supervised_state(tmp_codebase)
    config = make_config_with_approval(
        mock_response, store_for_editor, approval_manager, mode="supervised"
    )
    result = await editor_node(state, config=config)

    # Edit should NOT be applied to the file yet
    with open(ts_path) as f:
        content = f.read()
    assert "due_date" not in content

    # Should signal waiting for human
    assert result.get("waiting_for_human") is True

    # Edit should be persisted in store as proposed
    edits = await store_for_editor.get_edits(state.get("run_id", ""), status="proposed")
    # Note: run_id may need to come from config/state


@pytest.mark.asyncio
async def test_editor_autonomous_mode_proposes_approves_applies(
    tmp_codebase, store_for_editor, approval_manager
):
    """In autonomous mode, editor proposes, approves, and applies immediately."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })
    state = make_supervised_state(tmp_codebase)
    state["autonomy_mode"] = "autonomous"
    config = make_config_with_approval(
        mock_response, store_for_editor, approval_manager, mode="autonomous"
    )
    result = await editor_node(state, config=config)

    # Edit SHOULD be applied to the file
    with open(ts_path) as f:
        content = f.read()
    assert "due_date" in content

    # Should not be waiting for human
    assert result.get("waiting_for_human") is not True
```

- [ ] **Step 2: Update agent/nodes/editor.py with approval gates**

The updated editor_node integrates with ApprovalManager. When `approval_manager` is available in config, the editor uses approval gates. When it is not (backward compatibility), it behaves as before.

```python
import json
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER
from agent.tools.file_ops import read_file, edit_file
from agent.tracing import TraceLogger
from store.models import EditRecord

tracer = TraceLogger()


async def editor_node(state: dict, config: dict) -> dict:
    router = config["configurable"]["router"]
    file_buffer = state.get("file_buffer", {})
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if not file_buffer:
        return {"error_state": "No files in buffer to edit"}

    file_path = list(file_buffer.keys())[0]
    content = file_buffer[file_path]

    # Determine complexity from typed step
    complexity = "simple"
    if current_step < len(plan):
        step = plan[current_step]
        if isinstance(step, dict):
            complexity = step.get("complexity", "simple")

    task_type = "edit_complex" if complexity == "complex" else "edit_simple"

    # Number the lines for the LLM
    lines = content.split("\n")
    numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    # Build instruction from step
    step_text = ""
    if current_step < len(plan):
        step = plan[current_step]
        step_text = step if isinstance(step, str) else step.get("id", "edit")

    context = state.get("context", {})
    context_section = ""
    if context.get("spec"):
        context_section = f"Spec: {context['spec']}"

    user_prompt = EDITOR_USER.format(
        file_path=file_path,
        numbered_content=numbered,
        edit_instruction=step_text,
        context_section=context_section,
    )

    raw = await router.call(task_type, EDITOR_SYSTEM, user_prompt)

    # Parse JSON response
    try:
        data = json.loads(raw)
        anchor = data["anchor"]
        replacement = data["replacement"]
    except (json.JSONDecodeError, KeyError) as e:
        return {"error_state": f"Editor output parse error: {e}"}

    # --- Approval gate ---
    approval_manager = config["configurable"].get("approval_manager")
    if approval_manager is not None:
        return await _editor_with_approval(
            state, config, file_path, file_buffer, anchor, replacement, task_type, approval_manager
        )

    # --- Legacy path (no approval manager) ---
    result = edit_file(file_path, anchor, replacement)
    if result.get("error"):
        tracer.log("editor", {"file": file_path, "error": result["error"]})
        return {
            "error_state": result["error"],
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "error": result["error"]}
            ],
        }

    tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type})

    updated_content = read_file(file_path)
    return {
        "file_buffer": {**file_buffer, file_path: updated_content},
        "edit_history": state.get("edit_history", []) + [
            {"file": file_path, "old": anchor, "new": replacement, "snapshot": result.get("snapshot")}
        ],
        "error_state": None,
    }


async def _editor_with_approval(
    state, config, file_path, file_buffer, anchor, replacement, task_type, approval_manager
):
    """Editor path with approval state machine integration."""
    autonomy_mode = config["configurable"].get("autonomy_mode", "supervised")
    run_id = config["configurable"].get("run_id", state.get("run_id", ""))

    # Create proposed edit
    edit = EditRecord(
        run_id=run_id,
        file_path=file_path,
        step=state.get("current_step", 0),
        anchor=anchor,
        old_content=anchor,
        new_content=replacement,
        status="proposed",
    )
    proposed = await approval_manager.propose_edit(run_id, edit)

    tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type, "mode": autonomy_mode})

    if autonomy_mode == "autonomous":
        # Auto-approve and apply immediately
        op_id = f"op_{proposed.id}_approve"
        await approval_manager.approve(proposed.id, op_id)
        await approval_manager.apply_edit(proposed.id)

        updated_content = read_file(file_path)
        return {
            "file_buffer": {**file_buffer, file_path: updated_content},
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "old": anchor, "new": replacement, "edit_id": proposed.id}
            ],
            "error_state": None,
        }
    else:
        # Supervised mode: propose and wait for human
        return {
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "old": anchor, "new": replacement, "edit_id": proposed.id}
            ],
            "error_state": None,
            "waiting_for_human": True,
        }
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_editor_node.py -v
python -m pytest tests/test_approval.py -v
```

---

## Task 8: REST Endpoint — PATCH /runs/{run_id}/edits/{edit_id}

**Files:**
- Modify: `server/main.py`
- New: `tests/test_approval_rest.py`

- [ ] **Step 1: Write tests for the REST endpoint**

Create `tests/test_approval_rest.py`:

```python
"""Tests for the edit approval REST endpoint."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from store.models import EditRecord
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager, InvalidTransitionError


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test_rest.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest_asyncio.fixture
async def approval_manager(store, event_bus):
    return ApprovalManager(store=store, event_bus=event_bus)


@pytest_asyncio.fixture
async def client(store, approval_manager):
    from server.main import app
    app.state.store = store
    app.state.approval_manager = approval_manager
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_patch_approve_edit(client, store, approval_manager):
    """PATCH approve transitions proposed -> approved."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    op_id = f"op_{created.id}_approve"
    resp = await client.patch(
        f"/runs/r1/edits/{created.id}",
        json={"action": "approve", "op_id": op_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["edit_id"] == created.id


@pytest.mark.asyncio
async def test_patch_reject_edit(client, store, approval_manager):
    """PATCH reject transitions proposed -> rejected."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    op_id = f"op_{created.id}_reject"
    resp = await client.patch(
        f"/runs/r1/edits/{created.id}",
        json={"action": "reject", "op_id": op_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"


@pytest.mark.asyncio
async def test_patch_invalid_action_returns_422(client, store, approval_manager):
    """PATCH with invalid action returns 422."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    resp = await client.patch(
        f"/runs/r1/edits/{created.id}",
        json={"action": "explode", "op_id": "op_x"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_nonexistent_edit_returns_404(client):
    """PATCH on nonexistent edit returns 404."""
    resp = await client.patch(
        "/runs/r1/edits/nonexistent",
        json={"action": "approve", "op_id": "op_x_approve"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_invalid_transition_returns_409(client, store, approval_manager):
    """PATCH with invalid transition (e.g., approve already approved) returns 409."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    await approval_manager.approve(created.id, f"op_{created.id}_approve")
    resp = await client.patch(
        f"/runs/r1/edits/{created.id}",
        json={"action": "approve", "op_id": "op_different_approve"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patch_idempotent_approve(client, store, approval_manager):
    """PATCH with same op_id is idempotent (returns 200 both times)."""
    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    op_id = f"op_{created.id}_approve"
    resp1 = await client.patch(
        f"/runs/r1/edits/{created.id}",
        json={"action": "approve", "op_id": op_id},
    )
    resp2 = await client.patch(
        f"/runs/r1/edits/{created.id}",
        json={"action": "approve", "op_id": op_id},
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
```

- [ ] **Step 2: Add the PATCH endpoint to server/main.py**

Add the following to `server/main.py`:

```python
from agent.approval import ApprovalManager, InvalidTransitionError
from typing import Literal as TypingLiteral


class EditActionRequest(BaseModel):
    action: TypingLiteral["approve", "reject"]
    op_id: str


@app.patch("/runs/{run_id}/edits/{edit_id}")
async def patch_edit(run_id: str, edit_id: str, req: EditActionRequest):
    approval_manager: ApprovalManager = app.state.approval_manager
    try:
        if req.action == "approve":
            result = await approval_manager.approve(edit_id, req.op_id)
        else:
            result = await approval_manager.reject(edit_id, req.op_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Edit {edit_id} not found")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"edit_id": edit_id, "status": result.status, "run_id": result.run_id}
```

Also update the `lifespan` function to wire ApprovalManager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SQLiteSessionStore(DB_PATH)
    await store.initialize()
    app.state.store = store
    app.state.router = ModelRouter()
    app.state.graph = build_graph()
    # Wire up approval manager (event_bus comes from 2a-1)
    from agent.events import EventBus
    event_bus = EventBus()
    app.state.event_bus = event_bus
    app.state.approval_manager = ApprovalManager(store=store, event_bus=event_bus)
    yield
    await store.close()
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_approval_rest.py -v
python -m pytest tests/test_server.py -v  # ensure no regressions
```

---

## Task 9: WebSocket Integration — Handle approve/reject in ConnectionManager

**Files:**
- Modify: `server/websocket.py`
- New: `tests/test_approval_ws.py`

- [ ] **Step 1: Write tests for WebSocket approve/reject messages**

Create `tests/test_approval_ws.py`:

```python
"""Tests for WebSocket approval message handling."""
import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from store.models import EditRecord
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager, InvalidTransitionError


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test_ws.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def event_bus():
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest_asyncio.fixture
async def approval_manager(store, event_bus):
    return ApprovalManager(store=store, event_bus=event_bus)


class FakeWebSocket:
    """Minimal fake WebSocket for testing message handling."""
    def __init__(self):
        self.sent: list[str] = []

    async def send_text(self, data: str):
        self.sent.append(data)

    async def send_json(self, data: dict):
        self.sent.append(json.dumps(data))


@pytest.mark.asyncio
async def test_handle_approve_message(approval_manager, store):
    """WebSocket 'approve' message delegates to ApprovalManager.approve."""
    from server.websocket import handle_client_message

    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    ws = FakeWebSocket()

    message = {
        "type": "approve",
        "edit_id": created.id,
        "op_id": f"op_{created.id}_approve",
    }
    await handle_client_message(ws, message, approval_manager)

    fetched = await store.get_edit(created.id)
    assert fetched.status == "approved"

    # Should have sent a success response
    assert len(ws.sent) == 1
    resp = json.loads(ws.sent[0])
    assert resp["type"] == "edit.approved"
    assert resp["edit_id"] == created.id


@pytest.mark.asyncio
async def test_handle_reject_message(approval_manager, store):
    """WebSocket 'reject' message delegates to ApprovalManager.reject."""
    from server.websocket import handle_client_message

    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    ws = FakeWebSocket()

    message = {
        "type": "reject",
        "edit_id": created.id,
        "op_id": f"op_{created.id}_reject",
    }
    await handle_client_message(ws, message, approval_manager)

    fetched = await store.get_edit(created.id)
    assert fetched.status == "rejected"

    resp = json.loads(ws.sent[0])
    assert resp["type"] == "edit.rejected"


@pytest.mark.asyncio
async def test_handle_invalid_transition_sends_error(approval_manager, store):
    """WebSocket message for invalid transition sends error response."""
    from server.websocket import handle_client_message

    edit = EditRecord(run_id="r1", file_path="a.py")
    created = await approval_manager.propose_edit("r1", edit)
    await approval_manager.approve(created.id, f"op_{created.id}_approve")
    ws = FakeWebSocket()

    message = {
        "type": "approve",
        "edit_id": created.id,
        "op_id": "op_different_approve",
    }
    await handle_client_message(ws, message, approval_manager)

    resp = json.loads(ws.sent[0])
    assert resp["type"] == "error"
    assert "transition" in resp["message"].lower() or "cannot" in resp["message"].lower()


@pytest.mark.asyncio
async def test_handle_nonexistent_edit_sends_error(approval_manager):
    """WebSocket message for nonexistent edit sends error response."""
    from server.websocket import handle_client_message

    ws = FakeWebSocket()
    message = {
        "type": "approve",
        "edit_id": "nonexistent",
        "op_id": "op_x_approve",
    }
    await handle_client_message(ws, message, approval_manager)

    resp = json.loads(ws.sent[0])
    assert resp["type"] == "error"
    assert "not found" in resp["message"].lower()


@pytest.mark.asyncio
async def test_handle_update_mode_message(approval_manager):
    """WebSocket 'update_mode' message is accepted without error."""
    from server.websocket import handle_client_message

    ws = FakeWebSocket()
    message = {
        "type": "update_mode",
        "mode": "autonomous",
    }
    await handle_client_message(ws, message, approval_manager)

    resp = json.loads(ws.sent[0])
    assert resp["type"] == "mode.updated"
```

- [ ] **Step 2: Add handle_client_message to server/websocket.py**

Add the `handle_client_message` function to the existing `server/websocket.py`. This function is called by `ConnectionManager` when a client sends a message. It delegates approval actions to `ApprovalManager`.

```python
import json
from agent.approval import ApprovalManager, InvalidTransitionError


async def handle_client_message(websocket, message: dict, approval_manager: ApprovalManager) -> None:
    """Handle an incoming client message for approval actions.

    Supported message types:
    - {"type": "approve", "edit_id": "...", "op_id": "..."}
    - {"type": "reject",  "edit_id": "...", "op_id": "..."}
    - {"type": "update_mode", "mode": "autonomous" | "supervised"}
    """
    msg_type = message.get("type")

    if msg_type in ("approve", "reject"):
        edit_id = message.get("edit_id", "")
        op_id = message.get("op_id", "")
        try:
            if msg_type == "approve":
                result = await approval_manager.approve(edit_id, op_id)
            else:
                result = await approval_manager.reject(edit_id, op_id)
            await websocket.send_text(json.dumps({
                "type": f"edit.{result.status}",
                "edit_id": edit_id,
                "status": result.status,
            }))
        except ValueError as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except InvalidTransitionError as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))

    elif msg_type == "update_mode":
        mode = message.get("mode", "supervised")
        # Mode update is stored at the project/run level by the caller.
        # Here we just acknowledge.
        await websocket.send_text(json.dumps({
            "type": "mode.updated",
            "mode": mode,
        }))

    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        }))
```

- [ ] **Step 3: Run tests, verify pass**

```bash
python -m pytest tests/test_approval_ws.py -v
```

---

## Verification

After all tasks are complete, run the full test suite to ensure no regressions:

```bash
python -m pytest tests/ -v --tb=short
```

Expected new/modified test files:
- `tests/test_approval_store.py` — 9 tests (model validation + store methods)
- `tests/test_approval.py` — 22 tests (ApprovalManager transitions, idempotency, apply, mark_committed, auto_approve, get_pending)
- `tests/test_approval_rest.py` — 6 tests (PATCH endpoint)
- `tests/test_approval_ws.py` — 5 tests (WebSocket message handling)
- `tests/test_state.py` — 2 new tests (autonomy_mode, branch fields)
- `tests/test_editor_node.py` — 2 new tests (supervised/autonomous paths)

Total: ~46 new tests across 6 files.

---

## Addendum: Required Corrections

The agentic worker MUST apply these corrections when implementing the tasks above.

### Fix 1: Use 2a-1 EventBus.emit(Event(...)) API — not (type, payload)

The plan emits events like `await self.event_bus.emit("edit.proposed", {...})`. This is wrong — 2a-1's `EventBus.emit()` takes an `Event` object.

**All event emissions must use:**
```python
await self.event_bus.emit(Event(
    project_id=project_id,   # required — added in 2a-1 addendum
    run_id=run_id,
    type="approval",          # use P0 type for priority routing
    data={
        "event": "edit.proposed",
        "edit_id": created.id,
        "file_path": created.file_path,
    },
))
```

This applies to ALL emit calls in ApprovalManager: `propose_edit`, `approve`, `reject`, `apply_edit`, `mark_committed`.

### Fix 2: Event types must match 2a-1 priority routing

2a-1 routes priorities by `event.type`:
- P0 (instant): `approval`, `error`, `stop`, `review`
- P1 (batched): `stream`, `diff`, `git`
- P2 (aggregated): everything else

The plan uses types like `edit.proposed`, `edit.approved` — these fall into P2 and would NOT be sent immediately.

**Fix:** All approval lifecycle events must use `type="approval"` with a domain subtype in `data["event"]`:
```python
type="approval"                    # P0 — sent immediately
data={"event": "edit.proposed"}    # domain-specific subtype
data={"event": "edit.approved"}
data={"event": "edit.rejected"}
data={"event": "edit.applied"}
data={"event": "edit.committed"}
```

### Fix 3: Reuse existing EventBus from 2a-1 — do not create a new one

The plan creates a new `EventBus()` in server wiring. This is wrong — 2a-1 already creates one in the lifespan.

**Fix:** In server/main.py, do NOT instantiate a new EventBus. Instead:
```python
# In lifespan or wherever ApprovalManager is created:
event_bus = app.state.event_bus       # reuse from 2a-1
store = app.state.store               # reuse from 2a-1
app.state.approval_manager = ApprovalManager(store=store, event_bus=event_bus)
```

### Fix 4: Define the supervised resume flow explicitly

The plan leaves ambiguous: who resumes the graph after approval, and how `file_buffer` gets refreshed.

**The V1 supervised flow must be:**
1. `editor_node` calls `approval_manager.propose_edit()` — creates edit with `proposed` status
2. `editor_node` returns `{"error_state": None, "waiting_for_human": True}` — graph checkpoints
3. User approves via REST/WebSocket → server calls `approval_manager.approve(edit_id, op_id)`
4. Server calls `approval_manager.apply_edit(edit_id)` — writes edit to filesystem
5. Server resumes graph from checkpoint via `POST /instruction/{run_id}` or equivalent
6. The resumed editor (or `advance` node) re-reads the file into `file_buffer` to pick up the applied edit

The plan must include this flow in Task 7 (editor node integration) with explicit code for steps 4-6.

### Fix 5: Require and validate run_id in editor integration

The plan has a test comment: `# Note: run_id may need to come from config/state`. This is not acceptable.

**Fix:** `run_id` must be present in config:
```python
run_id = config["configurable"].get("run_id", "")
```

The server must pass `run_id` in the config when invoking the graph. All editor tests must include `run_id` in their config fixtures.

### Fix 6: Validate run_id ownership in REST endpoint

The plan's `PATCH /runs/{run_id}/edits/{edit_id}` looks up the edit by `edit_id` but never checks that `edit.run_id == run_id`.

**Fix:** Add ownership validation:
```python
edit = await store.get_edit(edit_id)
if edit is None:
    raise HTTPException(status_code=404, detail="Edit not found")
if edit.run_id != run_id:
    raise HTTPException(status_code=404, detail="Edit not found for this run")
```

### Fix 7: Merge WebSocket approval into existing ConnectionManager

The plan adds a standalone `handle_client_message()` function in `server/websocket.py`. This conflicts with 2a-1's `ConnectionManager.handle_client_message()`.

**Fix:** Extend the EXISTING `ConnectionManager.handle_client_message()` to handle `approve`, `reject`, and `update_mode` actions by delegating to ApprovalManager. Do not create a second handler.

```python
# In ConnectionManager.handle_client_message():
elif action == "approve":
    edit_id = data.get("edit_id")
    op_id = data.get("op_id")
    run_id = data.get("run_id")
    result = await self.approval_manager.approve(edit_id, op_id)
    await ws.send_json({"type": "approval", "data": {"event": "edit.approved", "edit_id": edit_id, "status": result.status}})

elif action == "reject":
    # similar pattern
```

ConnectionManager needs an `approval_manager` reference — pass it during construction or via a setter.

### Fix 8: Align WebSocket message schema with 2a-1

The plan uses `{"type": "approve", ...}` for client messages. 2a-1 uses `{"action": "approve", ...}`.

**Fix:** All client→server messages use `action` as the key, matching 2a-1:
```json
{ "action": "approve", "run_id": "run_456", "edit_id": "edit_abc", "op_id": "op_edit_abc_approve" }
{ "action": "reject", "run_id": "run_456", "edit_id": "edit_abc", "op_id": "op_edit_abc_reject" }
{ "action": "update_mode", "mode": "autonomous" }
```

Update all WebSocket tests to use `action` not `type`.

### Fix 9: Maintain `approved_at` or remove it

The model has `approved_at: datetime | None = None` but no code ever sets it.

**Fix:** Set `approved_at` when transitioning to `approved`:
```python
async def approve(self, edit_id: str, op_id: str) -> EditRecord:
    # ... after validating transition ...
    edit.status = "approved"
    edit.approved_at = datetime.now(timezone.utc)
    edit.last_op_id = op_id
    await self.store.update_edit_status(edit.id, "approved", approved_at=edit.approved_at, last_op_id=op_id)
```

Update `update_edit_status` in store to accept and persist `approved_at`.

### Fix 10: Document last_op_id as V1-only idempotency

Add this note to ApprovalManager docstring or module docstring:
```
Idempotency note (V1): last_op_id provides last-operation-only idempotency.
This is sufficient for single-writer / low-concurrency V1. It does NOT provide
a full operation history or distinguish duplicate retries from racing actors.
```

### Fix 11: mark_committed() event must include run_id and only emit for actually transitioned edits

```python
async def mark_committed(self, run_id: str, edit_ids: list[str]) -> None:
    transitioned = []
    for edit_id in edit_ids:
        edit = await self.store.get_edit(edit_id)
        if edit and edit.status == "applied":
            await self.store.update_edit_status(edit_id, "committed")
            transitioned.append(edit_id)
    if transitioned:
        await self.event_bus.emit(Event(
            project_id=...,  # from run or config
            run_id=run_id,
            type="approval",
            data={"event": "edit.committed", "edit_ids": transitioned},
        ))
```

### Fix 12: Remove `branch` from AgentState in this phase

`branch` belongs in 2a-3 (Git Integration), not 2a-2. Adding it here is harmless but mixed-scope. The worker may skip adding `branch` in Task 3 and defer it to 2a-3.
