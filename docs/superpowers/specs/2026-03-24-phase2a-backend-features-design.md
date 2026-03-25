# Phase 2a: Backend Features — WebSocket, Approval Gates, Git Integration

## Overview

Phase 2a adds three backend capabilities to the Shipyard agent: real-time WebSocket streaming, an approval state machine for supervised editing, and full Git/GitHub integration. These are built in order — event bus first, approval gates second, Git third — because each depends on the previous.

**Builds on:** Phase 1 (OpenAI migration, model router, SQLite store, typed plan steps)

**Prerequisites:** All Phase 1 modules: `agent/router.py`, `agent/models.py`, `agent/steps.py`, `agent/context.py`, `store/sqlite.py`, updated `server/main.py`

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

### Required Store/Model Updates (before sub-phases)

These changes are prerequisites for all three sub-phases:

**`store/models.py` — Updates:**
```python
from typing import Literal
EDIT_STATUSES = Literal["proposed", "approved", "rejected", "applied", "committed"]

class EditRecord(BaseModel):
    status: EDIT_STATUSES = "proposed"
    last_op_id: str | None = None  # idempotency tracking

class Event(BaseModel):
    seq: int = 0  # per-run monotonic sequence number, assigned by EventBus
    # ... existing fields unchanged
```

**`store/protocol.py` — Add `get_edit` method:**
```python
async def get_edit(self, edit_id: str) -> EditRecord | None: ...
```

**`store/sqlite.py` — Implement `get_edit`:**
```python
async def get_edit(self, edit_id: str) -> EditRecord | None:
    cursor = await self._db.execute("SELECT * FROM edits WHERE id = ?", (edit_id,))
    row = await cursor.fetchone()
    return EditRecord(**dict(row)) if row else None
```

**`agent/state.py` — Add Phase 2a fields:**
```python
autonomy_mode: str          # "supervised" | "autonomous"
branch: str                  # current git branch
```

Note: `pending_approvals` is NOT stored in AgentState. It is always derived from the store by querying edits with `status == "proposed"` for the current run. This avoids split-brain between graph state and durable state.

**`agent/tools/shell.py` — Add async variant (argv form):**
```python
async def run_command_async(argv: list[str], cwd: str = ".", timeout: int = 60) -> dict:
    """Non-blocking subprocess execution using asyncio. Uses argv list form (no shell=True)."""
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=cwd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {"stdout": stdout.decode(), "stderr": stderr.decode(), "exit_code": proc.returncode}
    except asyncio.TimeoutError:
        proc.kill()
        return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}
```

GitManager uses `run_command_async` with argv list form (e.g., `["git", "commit", "-m", message]`) to avoid shell injection and event loop blocking.

---

## Sub-phase 2a-1: WebSocket Event Bus + Streaming

### Architecture

```
Agent Nodes ──→ EventBus ──→ PriorityQueue
                                │   │   │
                               P0  P1  P2
                                │   │   │
                                ▼   ▼   ▼
                         ┌──────────────┐
                         │ TokenBatcher  │
                         │ (flush @50ms) │
                         └──────┬───────┘
                                │
                    ┌───────────┼──────────┐
                    │   ConnectionManager   │
                    │   - subscriptions     │
                    │   - heartbeat (15s)   │
                    │   - reconnect+replay  │
                    └───────────────────────┘
                                │
                         ┌──────┴──────┐
                         │ SQLite      │
                         │ (durable    │
                         │  events)    │
                         └─────────────┘
```

### Priority Channels

| Priority | Event Types | Behavior |
|---|---|---|
| P0 (instant) | `approval`, `error`, `stop`, `review` | Sent immediately, never batched |
| P1 (real-time) | `stream`, `diff`, `git` | Buffered, flushed every ~50ms |
| P2 (batched) | `status`, `file`, `exec` | Aggregated, sent at node boundaries |

### Event Persistence

- `stream` events are **not persisted** (transient, token-level)
- All other event types are persisted to the `events` table in SQLite
- On reconnect, only persisted events are replayed

### Token Batcher

Buffers P1 events (primarily LLM token stream) and flushes every 50ms. This feels instant to the user while cutting WebSocket message volume by 10-20x.

### Event Format

```json
{
  "id": "evt_abc123",
  "run_id": "run_456",
  "seq": 42,
  "type": "stream",
  "node": "editor",
  "model": "o3",
  "timestamp": 1711300000,
  "data": { "token": "const router = ", "done": false }
}
```

`seq` is a per-run monotonic sequence number (integer, starts at 1). Assigned by `EventBus.emit()` using an in-memory counter per run_id. Persisted events store `seq`; transient `stream` events also carry `seq` for ordering but are not persisted. The replay cursor uses `seq`, not event ID or timestamp.

### WebSocket Endpoint

`ws://localhost:8000/ws/{project_id}` — one persistent connection per project. On connect, validate that `project_id` exists in the store; close with code 4004 if not found.

**Server → Client messages:**
- Events (by subscription)
- Heartbeat (`{"type": "heartbeat"}` every 15s)
- Run snapshot (on reconnect)

**Client → Server messages:**
```json
{ "action": "subscribe", "channels": ["diff", "approval"], "panel": "diff-viewer" }
{ "action": "approve", "run_id": "run_456", "edit_id": "edit_abc", "op_id": "op_edit_abc_approve" }
{ "action": "reject", "run_id": "run_456", "edit_id": "edit_abc", "op_id": "op_edit_abc_reject" }
{ "action": "stop", "run_id": "run_456" }
{ "action": "update_mode", "mode": "autonomous" }
{ "action": "reconnect", "run_id": "run_456", "last_seq": 42 }
```

### Reconnect with Replay

1. Client reconnects, sends `{"action": "reconnect", "run_id": "run_456", "last_seq": 42}`
2. Server builds `pending_approvals` from store (edits where `status == "proposed"` for this run)
3. Server sends a **run snapshot**:
```json
{
  "type": "snapshot",
  "run_id": "run_456",
  "active_node": "editor",
  "current_step": 3,
  "total_steps": 7,
  "pending_approvals": ["edit_abc"],
  "current_branch": "shipyard/refactor-auth",
  "autonomy_mode": "supervised",
  "status": "running"
}
```
4. Server replays all persisted events with `seq > 42`
5. Client reconstructs panel state from snapshot + replayed events
6. **Missed transient stream tokens** are not replayed — the client shows current node status from the snapshot and picks up the live stream from the current position. This is acceptable because token streams are ephemeral display content, not durable state.

### Heartbeat

- Server sends `{"type": "heartbeat"}` every 15s
- If client misses 3 consecutive heartbeats, it triggers auto-reconnect
- Powers the "Agent Idle" / "Agent Active" indicator in the UI

### New Files

| File | Responsibility |
|---|---|
| `agent/events.py` | `EventBus` — emit, prioritize, batch, persist |
| `server/websocket.py` | `ConnectionManager` + FastAPI WebSocket endpoint |
| `tests/test_events.py` | Event bus unit tests |
| `tests/test_websocket.py` | WebSocket endpoint integration tests |

### Module: `agent/events.py`

```python
from typing import Callable, Awaitable

class EventBus:
    def __init__(self, store: SessionStore):
        self.store = store
        self._send_callback: Callable[[Event], Awaitable[None]] | None = None
        self._batcher = TokenBatcher(flush_interval=0.05)

    def set_send_callback(self, callback: Callable[[Event], Awaitable[None]]):
        """Register a callback for sending events to clients.
        ConnectionManager registers its send_to_subscribed method here.
        This avoids circular dependency between EventBus and ConnectionManager."""

    async def emit(self, event: Event):
        """Emit event. Persist if durable, route by priority, send via callback."""

    async def replay(self, run_id: str, after_seq: int = 0) -> list[Event]:
        """Replay persisted events with seq > after_seq."""

    def get_snapshot(self, run_id: str, state: dict) -> dict:
        """Build a run snapshot from current graph state."""


class TokenBatcher:
    """Buffers P1 events and flushes every 50ms.

    Mechanism: A background asyncio.Task is started on the first add() call.
    It flushes the buffer every 50ms. The task is cancelled when the stream
    completes (on receiving an event with data.done == True).
    """
    def __init__(self, flush_interval: float = 0.05,
                 send_callback: Callable[[list[Event]], Awaitable[None]] | None = None):
        self._buffer: list[Event] = []
        self._flush_interval = flush_interval
        self._send_callback = send_callback
        self._flush_task: asyncio.Task | None = None

    async def add(self, event: Event):
        """Add event to buffer. Starts flush task on first call."""
        self._buffer.append(event)
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())
        # Stop flushing when stream ends
        if event.data.get("done"):
            await self.flush()
            self._flush_task.cancel()
            self._flush_task = None

    async def _flush_loop(self):
        """Background loop that flushes every flush_interval."""
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush()

    async def flush(self):
        """Send all buffered events, clear buffer."""
        if self._buffer and self._send_callback:
            events = self._buffer.copy()
            self._buffer.clear()
            await self._send_callback(events)
```

**Initialization order in server lifespan:**
1. Create `EventBus(store)`
2. Create `ConnectionManager(event_bus)`
3. `event_bus.set_send_callback(connection_manager.send_to_subscribed)` — no circular reference

### Module: `server/websocket.py`

```python
class ConnectionManager:
    def __init__(self, event_bus: EventBus):
        self._connections: dict[str, list[WebSocketState]] = {}  # project_id → connections

    async def connect(self, ws: WebSocket, project_id: str)
    async def disconnect(self, ws: WebSocket)
    async def send_to_subscribed(self, event: Event)
    async def handle_client_message(self, ws: WebSocket, data: dict)
    async def broadcast_heartbeat(self)
```

---

## Sub-phase 2a-2: Approval State Machine

### Edit State Machine

```
proposed → approved → applied → committed
    ↓
  rejected
```

### State Transitions

| From | To | Trigger | Who |
|---|---|---|---|
| proposed | approved | User approves (or auto in autonomous mode) | WebSocket/REST |
| proposed | rejected | User rejects | WebSocket/REST |
| approved | applied | Edit applied to file | Automatic |
| applied | committed | Git commit includes this edit | git_ops node |

### Idempotency Rules

- Every action has a stable operation ID: `op_{edit_id}_{action}` (e.g., `op_edit_abc_approve`). No timestamp — the same logical operation always produces the same key.
- Duplicate requests with the same `op_id` are deterministic no-ops: return the current edit state without re-processing.
- Transitions only from valid predecessor states. Invalid transitions return an error, not a silent no-op.
- REST is authoritative, WebSocket is advisory — both delegate to `ApprovalManager` which writes to the same store.

**Idempotency storage:** Add `last_op_id TEXT` column to the `edits` table. Check flow:
1. Fetch edit by ID
2. If `last_op_id == incoming op_id` → return current state (no-op)
3. If transition is invalid → return error
4. Apply transition, set `last_op_id = incoming op_id`, persist

### LangGraph Integration

**Supervised mode:**
1. Editor creates `EditRecord` with `proposed` status via `ApprovalManager.propose_edit()`
2. `approval` event emitted (P0) via event bus
3. Graph state set to `waiting_for_human`
4. LangGraph checkpoints graph state
5. User approves → `ApprovalManager.approve()` transitions to `approved`
6. Server calls `ApprovalManager.apply_edit()` which writes the edit to the file system and transitions to `applied`
7. Server resumes graph from checkpoint

`approve()` and `apply_edit()` are **separate operations**. `approve()` only changes status to `approved`. `apply_edit()` performs the file write and changes status to `applied`. This separation allows the system to handle failures during file application without corrupting approval state.

**Autonomous mode:**
1. Editor creates edit via `ApprovalManager.propose_edit()`
2. `ApprovalManager.approve()` called immediately (auto-approve)
3. `ApprovalManager.apply_edit()` writes to file, status → `applied`
4. `diff` event emitted for post-review
5. Graph continues without pause

### Mode Toggle Mid-Run

- **→ Autonomous:** auto-approve all pending `proposed` edits, skip future gates
- **→ Supervised:** pause at next edit boundary, don't retroactively require approval

### New Files

| File | Responsibility |
|---|---|
| `agent/approval.py` | `ApprovalManager` — state machine, idempotency |
| `tests/test_approval.py` | State machine tests |

### Modified Files

| File | Change |
|---|---|
| `agent/nodes/editor.py` | Integrate approval gates |
| `agent/state.py` | Add `autonomy_mode`, `pending_approvals`, `branch` fields |
| `store/models.py` | Add `Literal` validation to `EditRecord.status`, add `last_op_id` field |
| `store/protocol.py` | Add `get_edit(edit_id)` method |
| `store/sqlite.py` | Implement `get_edit`, add `last_op_id` column |
| `server/main.py` | Add `PATCH /runs/:id/edits/:edit_id` |
| `server/websocket.py` | Handle approve/reject client actions |

### Module: `agent/approval.py`

```python
class ApprovalManager:
    def __init__(self, store: SessionStore, event_bus: EventBus):
        self.store = store
        self.event_bus = event_bus

    async def propose_edit(self, run_id: str, edit: EditRecord) -> EditRecord:
        """Create edit with proposed status. Emits approval event in supervised mode."""

    async def approve(self, edit_id: str, op_id: str) -> EditRecord:
        """Transition proposed → approved only. Idempotent via op_id."""

    async def apply_edit(self, edit_id: str) -> EditRecord:
        """Transition approved → applied. Writes the edit to the file system.
        Called by server after approval, not by the user directly."""

    async def reject(self, edit_id: str, op_id: str) -> EditRecord:
        """Transition proposed → rejected. Idempotent via op_id."""

    async def mark_committed(self, edit_ids: list[str]) -> None:
        """Transition applied → committed after git commit."""

    async def auto_approve_pending(self, run_id: str) -> list[EditRecord]:
        """Auto-approve all proposed edits (for autonomous mode switch).
        Does NOT auto-apply — caller must call apply_edit() for each."""

    def is_valid_transition(self, current: str, target: str) -> bool:
        """Check if state transition is allowed."""

    async def get_pending(self, run_id: str) -> list[EditRecord]:
        """Get all edits with status == 'proposed' for a run. Source of truth for pending_approvals."""
```

### REST Endpoint

```
PATCH /runs/:id/edits/:edit_id
Body: { "action": "approve" | "reject", "op_id": "op_edit_abc_approve" }
Response: { "edit_id": "...", "status": "approved" | "rejected" }
```

Both the REST endpoint and the WebSocket `approve`/`reject` handler delegate to `ApprovalManager.approve()` / `ApprovalManager.reject()`. No business logic in endpoint handlers.

---

## Sub-phase 2a-3: Git Integration

### Architecture

GitManager wraps `run_command()` from `agent/tools/shell.py` for local git operations. GitHubClient uses `httpx.AsyncClient` for GitHub REST API. Both are injected into the `git_ops` node via LangGraph config.

### Smart Branching

```python
async def ensure_branch(self, task_slug: str, run_id: str) -> str:
    """Branch naming includes short run_id suffix to avoid collisions."""
    branch = await self.get_current_branch()
    if branch in ("main", "master"):
        short_id = run_id[:8]
        new_branch = f"shipyard/{task_slug}-{short_id}"
        return await self.create_branch(new_branch)
    return branch  # stay on current feature branch
```

**Edge case handling:**
- **Dirty working tree:** `ensure_branch` checks `git status --porcelain`. If dirty, stash changes before branching, pop after checkout.
- **Detached HEAD:** Refuse to operate. Return error asking user to checkout a branch first.
- **Branch already exists:** Append `-2`, `-3` etc. suffix until a unique name is found.
- **Not a git repo:** Return clear error. Do not `git init` automatically.

### Git Operation Lock

GitManager holds a per-instance `asyncio.Lock` (`self._lock`). All mutating operations (`stage_files`, `commit`, `push`, `create_branch`) acquire the lock before executing. This prevents concurrent graph steps or WebSocket actions from corrupting git state.

```python
async def commit(self, message: str) -> str:
    async with self._lock:
        await self._run(["git", "commit", "-m", message])
        ...
```

### Commit Flow

1. All edits in `applied` status → stage their file paths
2. Generate commit message via router (`"summarize"` task type → GPT-4o)
3. In supervised mode: emit approval event for commit, user can edit message
4. Run `["git", "commit", "-m", message]` (argv form, no shell)
5. Update edit statuses to `committed`
6. Log to `git_operations` table

### PR Creation

- Auto-generated title and body summarizing all commits on the branch
- Uses GitHub REST API via personal access token from project settings
- Configurable: draft mode, labels, reviewers (from `projects` table)

### git_ops Node

Wired into the graph between the last step and `reporter`:

```
[all steps done?] → git_ops → reporter → END
```

The node:
1. Calls `git_manager.ensure_branch(task_slug)`
2. Stages all edited files
3. Generates commit message
4. In supervised mode: pauses for approval
5. Commits and pushes
6. Creates PR if GitHub is configured
7. Logs all operations to `git_operations` table via store

### New Files

| File | Responsibility |
|---|---|
| `agent/git.py` | `GitManager` — local git via subprocess |
| `agent/github.py` | `GitHubClient` — GitHub REST API via httpx |
| `agent/nodes/git_ops.py` | `git_ops` graph node |
| `agent/prompts/git.py` | Commit message generation prompt |
| `tests/test_git.py` | GitManager tests (uses temp git repos) |
| `tests/test_github.py` | GitHubClient tests (mocked httpx) |
| `tests/test_git_ops_node.py` | git_ops node integration tests |

### Modified Files

| File | Change |
|---|---|
| `agent/graph.py` | Two changes: (1) Update `classify_step` to route `kind == "git"` to `"git_ops"` instead of `"reporter"`. (2) Add `git_ops` node and edge `git_ops → reporter` for end-of-run git operations. |
| `agent/tools/shell.py` | Add `run_command_async` (non-blocking subprocess) |
| `server/main.py` | Add git REST endpoints (commit, push, PR, merge) |

### Module: `agent/git.py`

```python
class GitManager:
    def __init__(self, working_directory: str):
        self.cwd = working_directory

    async def get_current_branch(self) -> str
    async def create_branch(self, name: str) -> str
    async def ensure_branch(self, task_slug: str) -> str
    async def stage_files(self, paths: list[str]) -> None
    async def commit(self, message: str) -> str  # returns SHA
    async def push(self, branch: str | None = None) -> None
    async def get_status(self) -> dict
    async def get_diff_summary(self) -> str  # for commit message generation
```

### Module: `agent/github.py`

```python
class GitHubClient:
    def __init__(self, repo: str, token: str):
        self.repo = repo  # "owner/repo"
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={"Authorization": f"token {token}"},
        )

    async def create_pr(self, branch: str, title: str, body: str,
                        draft: bool = False, reviewers: list[str] | None = None) -> dict
    async def get_review_comments(self, pr_number: int,
                                   since: str | None = None) -> list[dict]
    async def merge_pr(self, pr_number: int, method: str = "squash") -> dict
    async def close(self):
        await self._client.aclose()
```

### REST Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/runs/:id/git/commit` | POST | Commit approved edits |
| `/runs/:id/git/push` | POST | Push branch to remote |
| `/runs/:id/git/pr` | POST | Create PR |
| `/runs/:id/git/merge` | POST | Merge PR |

---

## File Summary

### New Files (Phase 2a total)

| File | Sub-phase |
|---|---|
| `agent/events.py` | 2a-1 |
| `server/websocket.py` | 2a-1 |
| `agent/approval.py` | 2a-2 |
| `agent/git.py` | 2a-3 |
| `agent/github.py` | 2a-3 |
| `agent/nodes/git_ops.py` | 2a-3 |
| `agent/prompts/git.py` | 2a-3 |
| `tests/test_events.py` | 2a-1 |
| `tests/test_websocket.py` | 2a-1 |
| `tests/test_approval.py` | 2a-2 |
| `tests/test_git.py` | 2a-3 |
| `tests/test_github.py` | 2a-3 |
| `tests/test_git_ops_node.py` | 2a-3 |

### Modified Files

| File | Sub-phases |
|---|---|
| `agent/state.py` | 2a-2 |
| `agent/nodes/editor.py` | 2a-2 |
| `agent/graph.py` | 2a-3 |
| `agent/tools/shell.py` | 2a-3 |
| `store/models.py` | 2a-2 |
| `store/protocol.py` | 2a-2 |
| `store/sqlite.py` | 2a-2 |
| `server/main.py` | 2a-1, 2a-2, 2a-3 |

---

## Testing Strategy

Each sub-phase is independently testable:

- **2a-1 (Event Bus):** Unit test the event bus (emit, persist, replay, batching). Integration test the WebSocket endpoint (connect, subscribe, receive events, reconnect).
- **2a-2 (Approval):** Unit test state transitions (valid/invalid), idempotency, auto-approve. Integration test with event bus (approval events emitted).
- **2a-3 (Git):** Unit test GitManager against temp git repos (real git commands). Mock httpx for GitHubClient. Integration test git_ops node with mock router + temp repo.

All tests use the existing `SQLiteSessionStore` with `tmp_path` fixtures — no mocking the store.

---

## State Ownership

| State | Source of Truth | Notes |
|---|---|---|
| LangGraph execution state | In-memory LangGraph graph + checkpoints | Ephemeral. Checkpointed at approval gates for resume. |
| Run/edit/event/project data | SQLite via `SessionStore` | Durable. Survives restarts. |
| WebSocket connections & subscriptions | In-memory `ConnectionManager` | Ephemeral. Rebuilt on reconnect. |
| Pending approvals | Derived from store (`edits WHERE status = 'proposed' AND run_id = ?`) | Never cached in `AgentState`. Always query store. |
| Autonomy mode | `AgentState.autonomy_mode` + `projects.autonomy_mode` in store | Graph state is current-run truth. Store is default for new runs. |
| Event sequence counters | In-memory per-run counter in `EventBus` | Reset on server restart. Persisted events retain their `seq` for replay. On restart, initialize counter from `MAX(seq) + 1` for active runs. |

---

## Migrations

Phase 2a requires these schema changes to the existing SQLite database:

```sql
-- Add seq column to events table (2a-1)
ALTER TABLE events ADD COLUMN seq INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events(run_id, seq);

-- Add last_op_id to edits table (2a-2)
ALTER TABLE edits ADD COLUMN last_op_id TEXT;

-- Add indexes for common queries (2a-2, 2a-3)
CREATE INDEX IF NOT EXISTS idx_edits_run_status ON edits(run_id, status);
CREATE INDEX IF NOT EXISTS idx_git_ops_run ON git_operations(run_id);
```

Run these in `SQLiteSessionStore.initialize()` using `ALTER TABLE ... ADD COLUMN` with `IF NOT EXISTS`-style error handling (catch `OperationalError` for "duplicate column name" and ignore).

---

## Observability

All `EventBus.emit()` calls and `TraceLogger.log()` calls must include these structured fields where available:

| Field | Required In | Purpose |
|---|---|---|
| `project_id` | All events, all traces | Correlate across runs |
| `run_id` | All events, all traces | Correlate within a run |
| `edit_id` | Approval events, edit traces | Track edit lifecycle |
| `seq` | All events | Ordering and replay cursor |
| `node` | All events | Which graph node emitted |
| `model` | LLM-related events | Which model was used |

No new logging framework. Use the existing `TraceLogger` and the `Event` model. The `seq` and `project_id` fields are the main additions.

---

## Transport / Service Boundary

**Design rule:** REST endpoints and WebSocket handlers must NOT contain business logic. Both delegate to the same shared service objects:

| Service | Used By |
|---|---|
| `ApprovalManager` | REST `PATCH /edits/:id`, WebSocket `approve`/`reject` action |
| `GitManager` | REST `/git/commit`, `/git/push`, `git_ops` node |
| `GitHubClient` | REST `/git/pr`, `/git/merge`, `git_ops` node |
| `EventBus` | All nodes (emit), WebSocket (send), REST (not directly) |

The server initializes these in `lifespan` and stores them on `app.state`. Endpoint handlers extract the service from `request.app.state` and call its methods. This ensures consistent behavior regardless of whether the action came from REST, WebSocket, or the agent graph.
