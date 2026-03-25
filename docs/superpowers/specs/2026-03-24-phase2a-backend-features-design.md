# Phase 2a: Backend Features — WebSocket, Approval Gates, Git Integration

## Overview

Phase 2a adds three backend capabilities to the Shipyard agent: real-time WebSocket streaming, an approval state machine for supervised editing, and full Git/GitHub integration. These are built in order — event bus first, approval gates second, Git third — because each depends on the previous.

**Builds on:** Phase 1 (OpenAI migration, model router, SQLite store, typed plan steps)

**Prerequisites:** All Phase 1 modules: `agent/router.py`, `agent/models.py`, `agent/steps.py`, `agent/context.py`, `store/sqlite.py`, updated `server/main.py`

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

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
  "type": "stream",
  "node": "editor",
  "model": "o3",
  "timestamp": 1711300000,
  "data": { "tokens": "const router = ", "done": false }
}
```

### WebSocket Endpoint

`ws://localhost:8000/ws/{project_id}` — one persistent connection per project.

**Server → Client messages:**
- Events (by subscription)
- Heartbeat (`{"type": "heartbeat"}` every 15s)
- Run snapshot (on reconnect)

**Client → Server messages:**
```json
{ "action": "subscribe", "channels": ["diff", "approval"], "panel": "diff-viewer" }
{ "action": "approve", "run_id": "run_456", "edit_id": "edit_abc" }
{ "action": "reject", "run_id": "run_456", "edit_id": "edit_abc" }
{ "action": "stop", "run_id": "run_456" }
{ "action": "update_mode", "mode": "autonomous" }
{ "action": "reconnect", "last_event_id": "evt_xxx" }
```

### Reconnect with Replay

1. Client reconnects, sends `{"action": "reconnect", "last_event_id": "evt_xxx"}`
2. Server sends a **run snapshot** first:
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
3. Server replays all persisted events after `last_event_id`
4. Client reconstructs panel state from snapshot + replayed events

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
class EventBus:
    def __init__(self, store: SessionStore):
        self.store = store
        self._manager: ConnectionManager | None = None
        self._batcher = TokenBatcher(flush_interval=0.05)

    def set_manager(self, manager: ConnectionManager):
        """Set the connection manager (called by server on startup)."""

    async def emit(self, event: Event):
        """Emit event. Persist if durable, route by priority."""

    async def replay(self, run_id: str, after_id: str | None) -> list[Event]:
        """Replay persisted events for reconnection."""

    def get_snapshot(self, run_id: str, state: dict) -> dict:
        """Build a run snapshot from current graph state."""


class TokenBatcher:
    def __init__(self, flush_interval: float = 0.05):
        self._buffer: list[Event] = []
        self._flush_interval = flush_interval

    async def add(self, event: Event):
        """Add event to buffer. Auto-flush after interval."""

    async def flush(self):
        """Send all buffered events to subscribed connections."""
```

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

- Every action has an idempotency key: `{edit_id}_{action}_{timestamp}`
- Duplicate approvals on already-approved edits are no-ops
- Transitions only from valid predecessor states
- REST is authoritative, WebSocket is advisory — both write to same store

### LangGraph Integration

**Supervised mode:**
1. Editor creates `EditRecord` with `proposed` status
2. Emits `approval` event (P0) via event bus
3. Graph state set to `waiting_for_human`
4. LangGraph checkpoints graph state
5. User approves → server resumes from checkpoint
6. Edit applied, status → `applied`

**Autonomous mode:**
1. Editor creates edit → auto-approves immediately
2. Edit applied to file
3. `diff` event emitted for post-review
4. Graph continues without pause

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
| `server/main.py` | Add `PATCH /runs/:id/edits/:edit_id` |
| `server/websocket.py` | Handle approve/reject client actions |

### Module: `agent/approval.py`

```python
class ApprovalManager:
    def __init__(self, store: SessionStore, event_bus: EventBus):
        self.store = store
        self.event_bus = event_bus

    async def propose_edit(self, run_id: str, edit: EditRecord) -> EditRecord:
        """Create a proposed edit. Emits approval event in supervised mode."""

    async def approve(self, edit_id: str, idempotency_key: str) -> EditRecord:
        """Transition proposed → approved → applied. Idempotent."""

    async def reject(self, edit_id: str, idempotency_key: str) -> EditRecord:
        """Transition proposed → rejected. Idempotent."""

    async def mark_committed(self, edit_ids: list[str]) -> None:
        """Transition applied → committed after git commit."""

    async def auto_approve_pending(self, run_id: str) -> list[EditRecord]:
        """Auto-approve all proposed edits (for autonomous mode switch)."""

    def is_valid_transition(self, current: str, target: str) -> bool:
        """Check if state transition is allowed."""
```

### REST Endpoint

```
PATCH /runs/:id/edits/:edit_id
Body: { "action": "approve" | "reject", "idempotency_key": "..." }
Response: { "edit_id": "...", "status": "approved" | "rejected" }
```

---

## Sub-phase 2a-3: Git Integration

### Architecture

GitManager wraps `run_command()` from `agent/tools/shell.py` for local git operations. GitHubClient uses `httpx.AsyncClient` for GitHub REST API. Both are injected into the `git_ops` node via LangGraph config.

### Smart Branching

```python
async def ensure_branch(self, task_slug: str) -> str:
    branch = await self.get_current_branch()
    if branch in ("main", "master"):
        return await self.create_branch(f"shipyard/{task_slug}")
    return branch  # stay on current feature branch
```

### Commit Flow

1. All edits in `applied` status → stage their file paths
2. Generate commit message via router (`"summarize"` task type → GPT-4o)
3. In supervised mode: emit approval event for commit, user can edit message
4. Run `git commit -m "<message>"`
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
| `agent/graph.py` | Wire git_ops node before reporter |
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
                        draft: bool = False, reviewers: list[str] = []) -> dict
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
| `agent/nodes/editor.py` | 2a-2 |
| `agent/graph.py` | 2a-3 |
| `server/main.py` | 2a-1, 2a-2, 2a-3 |

---

## Testing Strategy

Each sub-phase is independently testable:

- **2a-1 (Event Bus):** Unit test the event bus (emit, persist, replay, batching). Integration test the WebSocket endpoint (connect, subscribe, receive events, reconnect).
- **2a-2 (Approval):** Unit test state transitions (valid/invalid), idempotency, auto-approve. Integration test with event bus (approval events emitted).
- **2a-3 (Git):** Unit test GitManager against temp git repos (real git commands). Mock httpx for GitHubClient. Integration test git_ops node with mock router + temp repo.

All tests use the existing `SQLiteSessionStore` with `tmp_path` fixtures — no mocking the store.
