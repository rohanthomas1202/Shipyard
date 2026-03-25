# Shipyard V2 — Frosted Glassmorphic IDE Design Spec

## Overview

Shipyard V2 transforms the current API-only autonomous coding agent into a full-featured, visually stunning IDE-like application with a Frosted Glassmorphic UI, multi-model OpenAI routing, real-time streaming, Git/GitHub integration, and configurable autonomy.

**Key decisions:**
- Switch from Anthropic Claude to OpenAI (o3 / GPT-4o / GPT-4o-mini)
- Aggressive context strategy — send as much context as fits model windows (200K for o3, 128K for GPT-4o), no artificial budgeting
- Multi-model routing with classify + auto-escalate
- Web UI: Frosted Glassmorphic IDE (macOS-inspired, Linear/Vercel aesthetic)
- Configurable autonomy: autonomous vs. supervised, toggleable mid-run
- Full Git lifecycle: branch, commit, push, PR, review loop, merge
- SQLite persistence with Protocol abstraction for future Postgres swap
- Ship-first, then generalize to any codebase
- Single-user, local-first — no authentication layer in V2

**Out of scope for V2:**
- Multi-user / multi-tenant support
- User authentication and authorization
- Cloud-hosted deployment (Railway is local-push only)
- GitHub webhook receivers (polling only for V2)
- SSE fallback transport (WebSocket only)

**Dependency migration (Anthropic → OpenAI):**
- Remove: `anthropic`, `langchain-anthropic`
- Add: `openai`, `langchain-openai`, `aiosqlite`, `httpx` (for GitHub API)
- Update: `.env.example` to use `OPENAI_API_KEY` instead of `ANTHROPIC_API_KEY`

---

## 1. System Architecture

Two separate apps connected by WebSockets + REST:

```
┌─────────────────────────────────────────────────┐
│                  WEB FRONTEND                    │
│              (Vite + React + TypeScript)          │
│                                                   │
│  ┌──────────┬──────────────────┬──────────────┐  │
│  │  File    │  Diff/Code View  │ Agent Panel  │  │
│  │  Explorer│                  │ (streaming)  │  │
│  └──────────┴──────────────────┴──────────────┘  │
│         │              │              │           │
│         └──────── WebSocket ──────────┘           │
│                        │                          │
└────────────────────────┼──────────────────────────┘
                         │
┌────────────────────────┼──────────────────────────┐
│                  AGENT BACKEND                     │
│              (FastAPI + LangGraph)                  │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Event Bus   │  │ Multi-Model  │  │ Session   │ │
│  │ (WebSocket) │  │ Router       │  │ Store     │ │
│  │             │  │ (o3/4o/mini) │  │ (SQLite)  │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │           LangGraph Agent                    │   │
│  │  receive → plan → coordinate → classify      │   │
│  │    → read → edit → validate → report         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Tool     │  │ Git      │  │ GitHub Client    │ │
│  │ Layer    │  │ Manager  │  │ (REST API)       │ │
│  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**Components:**
- **Web Frontend** — Vite + React + TypeScript. Frosted Glassmorphic IDE design. Connects to backend via WebSocket.
- **Agent Backend** — FastAPI + LangGraph. Enhanced graph with new nodes. Persists to SQLite.
- **Event Bus** — Priority-based WebSocket streaming with token batching and reconnect replay.
- **Multi-Model Router** — Intelligent routing across o3, GPT-4o, GPT-4o-mini with auto-escalation.
- **Session Store** — SQLite with Protocol interface for future Postgres swap.
- **Git Manager** — Branch creation, commits, push operations.
- **GitHub Client** — PR creation, review comment polling, comment responses, merge.

---

## 2. Multi-Model Router

Replaces the current single-model `agent/llm.py` with an intelligent routing layer.

### Routing Rules

| Agent Node | Default Model | Escalation | Reasoning |
|---|---|---|---|
| `planner` | o3 | — | Planning is highest-leverage; bad plans waste everything downstream |
| `coordinator` | o3 | — | Parallel task decomposition needs strong reasoning |
| `editor` (complex) | o3 | — | Multi-file refactors, architecture changes |
| `editor` (simple) | GPT-4o | o3 on validation fail | Single-file, localized edits |
| `reader` | GPT-4o | — | File comprehension, summarization |
| `validator` | GPT-4o-mini | GPT-4o on failure | Syntax checks are mechanical |
| `classifier` | — (no LLM) | GPT-4o-mini if keyword match fails | Step routing via keyword matching (fast, deterministic), with LLM fallback for ambiguous steps |
| `merger` | GPT-4o | o3 on conflict | Merge parallel branch outputs; uses LLM only when conflicts detected |
| `reporter` | GPT-4o | — | Summarization |
| `test_runner` | — (no LLM) | — | Runs shell commands |
| `parse_results` | GPT-4o | o3 on complex failures | Analyze test output |
| `git_ops` | — (no LLM) | — | Git/GitHub API calls |

### Design Decisions

- **Aggressive context** — send as much file content as fits the model's context window (200K for o3, 128K for GPT-4o). When total context exceeds the window, prioritize: current file being edited > files referenced in the plan > surrounding files. No artificial truncation.
- Each model call records `model_used` in the trace for observability.
- The router is a standalone module (`agent/router.py`). No node knows which model it's talking to.
- **Escalation logic:** When a node fails validation or produces low-confidence output, the router retries with the next-tier model. Max one escalation per node invocation.

### Failure Definitions

| Failure Type | Trigger | Behavior |
|---|---|---|
| Malformed output | LLM returns unparseable JSON or missing fields | Retry same model once, then escalate |
| Validation error | Syntax check fails on edited code | Rollback edit, escalate model, retry with error context |
| Timeout | o3: 120s, GPT-4o: 60s, GPT-4o-mini: 30s | Retry same model once, then escalate |
| API error (429/500) | OpenAI rate limit or server error | Exponential backoff (1s, 2s, 4s), max 3 retries |
| Terminal failure | Final escalation tier also fails | Emit `error` event, set run status to `waiting_for_human`, pause for user intervention |

### Edit Complexity Classification

The `planner` node classifies each step's complexity when generating the plan. Classification criteria:
- **Simple:** Single file, localized change (add/remove/modify within one function or block)
- **Complex:** Multi-file changes, architectural modifications, changes that affect type signatures used across files, refactors touching >3 functions

The classification is stored as `complexity: "simple" | "complex"` in each plan step. The `editor` node reads this to select its model via the router.

### Module: `agent/router.py`

```python
class ModelRouter:
    """Routes LLM calls to the optimal OpenAI model based on task type."""

    async def call(
        self,
        task_type: str,       # "plan", "edit_simple", "edit_complex", "classify", etc.
        messages: list,
        structured_output: type | None = None,
    ) -> LLMResponse:
        """Route to appropriate model, auto-escalate on failure."""

    async def escalate(
        self,
        task_type: str,
        messages: list,
        prior_failure: str,
    ) -> LLMResponse:
        """Retry with a more powerful model after failure."""
```

---

## 3. Event Bus v2

Real-time streaming layer between backend and frontend.

### Priority Channels

| Priority | Types | Behavior |
|---|---|---|
| P0 (instant) | `approval`, `error`, `stop`, `review` | Sent immediately, never batched |
| P1 (real-time) | `stream`, `diff`, `git` | Buffered, flushed every ~50ms |
| P2 (batched) | `status`, `file`, `exec` | Aggregated, sent at node boundaries |

### Event Format

```json
{
  "id": "evt_abc123",
  "run_id": "run_456",
  "type": "stream",
  "node": "editor",
  "model": "o3",
  "timestamp": 1711300000,
  "data": { "token": "const ", "done": false }
}
```

### Transport

- **WebSocket** — bidirectional for events + user actions. Only transport in V2.

### Key Features

- **Token batching** — Buffer LLM tokens, flush every ~50ms. Feels instant, cuts message volume 10-20x.
- **Reconnection with replay** — On disconnect/reconnect, server replays missed events from SQLite using `last_event_id` cursor.
- **Client-side subscriptions** — Frontend panels subscribe to specific event types:
  ```json
  { "action": "subscribe", "channels": ["diff", "approval"], "panel": "diff-viewer" }
  ```
- **Event aggregation** — Collapse repetitive events (e.g., "reading 12 files" instead of 12 individual `file` events).
- **Bidirectional actions** — User actions sent as structured WebSocket messages:
  ```json
  { "action": "approve", "run_id": "run_456", "step": 2 }
  { "action": "stop", "run_id": "run_456" }
  { "action": "update_mode", "mode": "autonomous" }
  ```
- **Heartbeat** — Server sends heartbeat every 15s. Three missed heartbeats trigger auto-reconnect + replay. Powers "Agent Idle" / "Agent Active" indicator.
- **Event retention** — Token-level `stream` events are NOT persisted to SQLite (transient). Only `status`, `diff`, `approval`, `error`, `git`, `review`, `file`, and `exec` events are persisted. This keeps the events table manageable for long-running sessions. On reconnect, the current streaming state is reconstructed from the latest `status` event + live stream.

### Frontend Consumption

React context provider wraps the WebSocket connection. Each panel subscribes to relevant events:
- Agent panel → `status`, `stream`, `error`, `review`
- Diff viewer → `diff`, `approval`
- File explorer → `file`, `git`
- Progress bar → `status`

---

## 4. Git & GitHub Integration

Full Git lifecycle managed from within Shipyard.

### Branch Strategy (Smart Default)

- New task while on `main` → auto-create `shipyard/<task-slug>` branch
- Already on a feature branch → commit there
- Detection via `git rev-parse --abbrev-ref HEAD`

### Commit Flow

1. Agent makes edits → proposed in diff viewer
2. User approves diffs (per-step in supervised mode, auto in autonomous mode)
3. Approved edits staged to git
4. Commit message auto-generated by GPT-4o (conventional-commit style)
5. User can edit message before confirming

### PR Creation

- Auto-generated title and description summarizing all commits on branch
- Uses GitHub REST API via personal access token (configured in Project Settings)
- Configurable: labels, reviewers, draft mode per project

### PR Review Loop

1. Poll GitHub API for new review comments on open PRs
2. New comments surface in the AI Agent panel as notifications
3. Agent reads comment context + referenced code
4. Agent proposes a fix → shown as new diff in viewer
5. User approves → commit pushed, agent replies to comment on GitHub
6. Merge available from within Shipyard when PR is approved

### Git Integration Module

```python
class GitManager:
    """Manages local git operations."""
    async def get_current_branch(self) -> str
    async def create_branch(self, slug: str) -> str
    async def stage_files(self, paths: list[str]) -> None
    async def commit(self, message: str) -> str  # returns sha
    async def push(self, branch: str) -> None

class GitHubClient:
    """Manages GitHub API operations."""
    async def create_pr(self, branch, title, body, ...) -> PR
    async def get_review_comments(self, pr_number) -> list[Comment]
    async def reply_to_comment(self, pr_number, comment_id, body) -> None
    async def merge_pr(self, pr_number, method="squash") -> None
```

### UI Touchpoints

- Diff viewer footer: "Commit & Push" button alongside Approve/Reject
- Agent panel: "PR Reviews" section showing open comments with notification badges
- Project Settings: "GitHub" tab for PAT, default reviewers, label config

---

## 5. Session & State Persistence

SQLite with a Protocol-based abstraction for future Postgres swap.

### Schema

```sql
-- Projects: workspace configuration
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    github_repo TEXT,          -- e.g. "owner/repo"
    github_pat TEXT,           -- personal access token (local-only, single-user; encrypt at rest in future multi-user version)
    default_model TEXT DEFAULT 'gpt-4o',
    autonomy_mode TEXT DEFAULT 'supervised',  -- 'supervised' | 'autonomous'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Runs: each agent execution
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    instruction TEXT NOT NULL,
    status TEXT DEFAULT 'running',  -- running | completed | failed | waiting_for_human
    branch TEXT,
    context JSON,
    plan JSON,
    model_usage JSON,              -- {"o3": 12000, "gpt-4o": 8000, "gpt-4o-mini": 2000}
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Events: append-only event log for streaming + replay
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL,
    node TEXT,
    model TEXT,
    data JSON,
    timestamp REAL NOT NULL
);
CREATE INDEX idx_events_replay ON events(run_id, timestamp);

-- Edits: individual file edits with approval tracking
CREATE TABLE edits (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    file_path TEXT NOT NULL,
    step INTEGER,
    anchor TEXT,               -- unique search string used to locate the edit position in the file (V1's anchor-based editing approach)
    old_content TEXT,
    new_content TEXT,
    status TEXT DEFAULT 'proposed',  -- proposed | approved | rejected
    approved_at TIMESTAMP
);

-- Conversations: AI agent sidebar chat history
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    title TEXT,
    messages JSON,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Git operations: audit trail
CREATE TABLE git_operations (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL,           -- commit | push | pr_create | pr_merge | pr_comment
    branch TEXT,
    commit_sha TEXT,
    pr_url TEXT,
    pr_number INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Repository Interface

```python
class SessionStore(Protocol):
    async def get_project(self, id: str) -> Project: ...
    async def create_run(self, project_id: str, instruction: str, context: dict) -> Run: ...
    async def append_event(self, run_id: str, event: Event) -> None: ...
    async def replay_events(self, run_id: str, after_id: str | None) -> list[Event]: ...
    async def update_edit_status(self, edit_id: str, status: str) -> None: ...
    async def get_conversations(self, project_id: str) -> list[Conversation]: ...
    async def log_git_op(self, run_id: str, op_type: str, **kwargs) -> None: ...
```

---

## 6. Enhanced Agent Graph

The LangGraph graph gets new nodes, removed token limits, and smarter flow control.

### Graph Flow

```
receive ──→ planner (o3)
                │
                ▼
          coordinator (o3)
          ┌────┴─────────────────┐
      sequential               parallel (via LangGraph Send API)
          │                 ┌────┴────┐
          │              branch_1  branch_2  (each gets state copy)
          │                 │         │
          ▼                 ▼         ▼
       classify          classify  classify
       (keyword/4o-mini)
       ┌───┼───────┼────┐
       ▼   ▼       ▼    ▼
     read  edit   exec  test
     (4o)  (4o/o3) (-)  (-)
            │            │
            ▼            ▼
         validate    parse_results
         (4o-mini)   (4o)
            │            │
       ┌────┴────┐       │
     pass      fail      │
       │     (escalate   │
       │      + retry)   │
       ▼         │       │
     advance ◄───┘───────┘
       │
       ▼
 [all steps done?] ──no──→ classify (next step)
       │
      yes
       ▼
  [was parallel?] ──yes──→ merger (4o, o3 on conflict)
       │                       │
       no                      ▼
       │              [conflicts?] ──yes──→ emit error, wait for human
       │                   │
       │                  no
       ▼                   ▼
    git_ops ──────────── git_ops
  (commit/push/PR)
       │
       ▼
    reporter (4o) ──→ done
```

**Parallel execution details:**
- Coordinator uses LangGraph `Send` API to fork state into parallel branches
- Each branch runs its own classify → read → edit → validate cycle independently
- When all branches complete, merger node receives all branch outputs
- Merger uses pure Python to check for file-level conflicts (same file edited by multiple branches)
- If conflicts found: GPT-4o attempts resolution, escalates to o3 if needed. If unresolvable, pauses for human.
- If no conflicts: branch outputs are combined into a single state

### Node Changes from V1

| Node | Status | What Changed |
|---|---|---|
| `receive` | Enhanced | Server layer injects project context from session store into initial state before graph invocation |
| `planner` | Enhanced | No token budget — sends full file contents for better plans. Uses o3. |
| `coordinator` | Enhanced | Fully wired (was a stub). Real parallel fan-out via LangGraph `Send` API |
| `classifier` | Same | Routes steps via keyword matching (same as V1). Falls back to GPT-4o-mini LLM call only for ambiguous steps |
| `reader` | Enhanced | Reads full files always — no truncation |
| `editor` | Enhanced | Sends full file + surrounding context. Smart model selection |
| `validator` | Enhanced | Escalation on failure. Rollback + retry with stronger model |
| `executor` | Same | Runs shell commands |
| `test_runner` | **New** | Runs project tests, captures output |
| `parse_results` | **New** | Analyzes test output, identifies which edits caused failures |
| `git_ops` | **New** | Branch creation, commits, push, PR creation, PR comment response |
| `reporter` | Enhanced | Richer summary, includes model usage stats, git operations |
| `merger` | Enhanced | Fully wired conflict detection for parallel agent outputs |

### Key Improvements

- **Test feedback loop** — agent runs tests after edits. If they fail, it reads the error, identifies the cause, and fixes (up to 3 retries).
- **Aggressive context** — every node gets as much context as fits the model window. Planner sees full files, editor gets full surrounding code. When context exceeds window, prioritize by relevance.
- **Approval gates** — in supervised mode, the graph uses LangGraph checkpointing to pause execution. The `editor` and `git_ops` nodes save a checkpoint, emit an `approval` event via WebSocket, and return a `waiting_for_human` status. When the user approves/rejects via WebSocket, the server resumes the graph from the checkpoint with the user's decision injected into state.
- **Parallel execution** — coordinator fans out independent steps via LangGraph `Send` API. Merger node reconverges outputs.

### Store Injection

The `SessionStore` and `ModelRouter` are injected into the graph via LangGraph's config mechanism, not the state dict. The server passes them as `configurable` params when invoking the graph:

```python
result = await graph.ainvoke(
    initial_state,
    config={"configurable": {"store": store, "router": router, "event_bus": event_bus}}
)
```

Nodes access these via `config` parameter: `store = config["configurable"]["store"]`

---

## 7. Web Frontend — Frosted Glassmorphic IDE

### Design System

| Token | Value |
|---|---|
| Primary | `#6366F1` (Indigo) |
| Background | `#0F111A` (Deep midnight) |
| Surface | `rgba(30, 33, 43, 0.6)` (Translucent) |
| Border | `rgba(255, 255, 255, 0.08)` |
| Text Primary | `#F8FAFC` |
| Text Muted | `#94A3B8` |
| Diff Add | `rgba(16, 185, 129, 0.15)` with green left border |
| Diff Remove | `rgba(239, 68, 68, 0.15)` with red left border |
| UI Font | Plus Jakarta Sans |
| Code Font | JetBrains Mono |
| Panel Radius | 16px |
| Element Radius | 8px |
| Blur | `backdrop-filter: blur(24px)` |
| Shadow | `0 8px 32px rgba(0, 0, 0, 0.4)` |

### Mesh Background

Animated blurred blobs (`#3B82F6`, `#8B5CF6`, `#EC4899`) slowly rotating behind the UI on `#0F111A` base.

### Layout

3-column fixed-height grid (100vh):
- **Left (250px):** File Explorer — translucent panel, tree structure, modified file indicators
- **Center (1fr):** Main canvas — workspace home (empty state), diff viewer (active), or code editor
- **Right (300px):** AI Agent sidebar — chat interface, streaming output, PR reviews, status

### Screens

1. **Workspace Home** — Empty state with centered prompt input (600px), quick actions (Create project, Open terminal, Settings), mesh gradient visible through translucent panels
2. **Active Diff Viewer** — Sticky file header with Accept/Reject buttons, dual line numbers, syntax-highlighted diffs with green/red backgrounds and left borders, hover highlighting
3. **AI Agent Streaming** — Chat bubbles with indigo tint for AI responses, typing indicator (3 bouncing dots), action blocks with spinning border gradient ("Refactoring auth.ts..."), auto-scroll, stop button
4. **Project Settings** — Centered modal (600px), glassmorphic depth, tabs: General / AI Models / Environment / GitHub. Heavy backdrop blur over existing content.

### Autonomy Toggle

Located in the Agent panel. Toggle switch between "Supervised" and "Autonomous" mode. Can be changed mid-run:
- **Supervised:** Agent pauses at edit proposals and git operations, waits for approval
- **Autonomous:** Agent runs to completion, presents full changeset for post-review

### Frontend Tech Stack

- Vite + React + TypeScript
- Tailwind CSS v4 with custom design tokens
- WebSocket client with auto-reconnect and event replay
- React context for WebSocket state distribution
- Component library: panels, diff viewer, chat, file tree (all custom, glassmorphic)

---

## 8. Project Configuration

Stored in the `projects` table and editable via the Project Settings modal.

### Settings

| Setting | Location | Purpose |
|---|---|---|
| Project name | General tab | Display name |
| Working directory | General tab | Path to codebase |
| GitHub repository | GitHub tab | `owner/repo` format |
| GitHub PAT | GitHub tab | Personal access token for API |
| Default reviewers | GitHub tab | Auto-assign to PRs |
| Default labels | GitHub tab | Auto-label PRs |
| Draft PRs | GitHub tab | Create as draft by default |
| Default model | AI Models tab | Override routing defaults |
| Autonomy mode | AI Models tab | Default supervised/autonomous |
| Test command | Environment tab | e.g., `npm test`, `pytest` |
| Build command | Environment tab | e.g., `npm run build` |
| Lint command | Environment tab | e.g., `npm run lint` |

---

## 9. API Endpoints (Updated)

### REST API

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/projects` | GET/POST | List/create projects |
| `/projects/:id` | GET/PUT/DELETE | Project CRUD |
| `/projects/:id/runs` | GET/POST | List runs / start new run |
| `/runs/:id` | GET | Run status + details |
| `/runs/:id/edits` | GET | List proposed edits |
| `/runs/:id/edits/:edit_id` | PATCH | Approve/reject edit |
| `/runs/:id/resume` | POST | Resume paused run |
| `/projects/:id/conversations` | GET/POST | List/create conversations |
| `/runs/:id/git/commit` | POST | Commit approved edits |
| `/runs/:id/git/push` | POST | Push branch |
| `/runs/:id/git/pr` | POST | Create PR |
| `/runs/:id/git/pr/comments` | GET | Get PR review comments |
| `/runs/:id/git/merge` | POST | Merge PR |

### WebSocket

- `ws://localhost:8000/ws/:project_id` — persistent connection per project
- Handles: event streaming, user actions (approve/reject/stop/subscribe), heartbeat

---

## 10. File Structure (V2)

```
Shipyard/
├── agent/                          # Core agent logic (Python)
│   ├── __init__.py
│   ├── state.py                    # Enhanced AgentState
│   ├── graph.py                    # LangGraph graph with new nodes
│   ├── router.py                   # NEW: Multi-model router (o3/4o/4o-mini)
│   ├── events.py                   # NEW: Event bus + priority queue
│   ├── tracing.py                  # JSON trace logger
│   ├── nodes/
│   │   ├── receive.py
│   │   ├── planner.py
│   │   ├── reader.py
│   │   ├── editor.py
│   │   ├── validator.py
│   │   ├── executor.py
│   │   ├── coordinator.py
│   │   ├── merger.py
│   │   ├── reporter.py
│   │   ├── test_runner.py          # NEW: Run tests, capture output
│   │   ├── parse_results.py        # NEW: Analyze test failures
│   │   └── git_ops.py              # NEW: Git/GitHub operations
│   ├── tools/
│   │   ├── file_ops.py
│   │   ├── search.py
│   │   └── shell.py
│   └── prompts/
│       ├── planner.py
│       ├── editor.py
│       └── coordinator.py
├── server/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app with WebSocket
│   ├── routes/                     # NEW: Organized route modules
│   │   ├── projects.py
│   │   ├── runs.py
│   │   ├── edits.py
│   │   ├── git.py
│   │   └── conversations.py
│   └── websocket.py                # NEW: WebSocket handler
├── store/                          # NEW: Persistence layer
│   ├── __init__.py
│   ├── protocol.py                 # SessionStore Protocol
│   ├── sqlite.py                   # SQLiteSessionStore
│   └── models.py                   # Pydantic models (Project, Run, Event, etc.)
├── web/                            # NEW: Frontend app
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── context/
│   │   │   ├── WebSocketContext.tsx
│   │   │   └── ProjectContext.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.tsx
│   │   │   │   └── MeshBackground.tsx
│   │   │   ├── explorer/
│   │   │   │   ├── FileTree.tsx
│   │   │   │   └── FileNode.tsx
│   │   │   ├── editor/
│   │   │   │   ├── DiffViewer.tsx
│   │   │   │   ├── DiffLine.tsx
│   │   │   │   └── WorkspaceHome.tsx
│   │   │   ├── agent/
│   │   │   │   ├── AgentPanel.tsx
│   │   │   │   ├── ChatBubble.tsx
│   │   │   │   ├── StreamingText.tsx
│   │   │   │   ├── TypingIndicator.tsx
│   │   │   │   ├── ActionBlock.tsx
│   │   │   │   └── AutonomyToggle.tsx
│   │   │   ├── git/
│   │   │   │   ├── CommitDialog.tsx
│   │   │   │   ├── PRPanel.tsx
│   │   │   │   └── ReviewComments.tsx
│   │   │   └── settings/
│   │   │       ├── SettingsModal.tsx
│   │   │       └── tabs/
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useEvents.ts
│   │   │   └── useProject.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── styles/
│   │       └── glass.css
│   └── public/
├── tests/
│   ├── conftest.py
│   ├── test_state.py
│   ├── test_file_ops.py
│   ├── test_search.py
│   ├── test_shell.py
│   ├── test_editor_node.py
│   ├── test_validator_node.py
│   ├── test_graph.py
│   ├── test_multiagent.py
│   ├── test_server.py
│   ├── test_integration.py
│   ├── test_router.py              # NEW
│   ├── test_events.py              # NEW
│   ├── test_store.py               # NEW
│   ├── test_git_ops.py             # NEW
│   └── test_websocket.py           # NEW
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-03-24-shipyard-v2-design.md
│       └── plans/
├── ship-rebuild/                    # Target application
├── pyproject.toml
├── requirements.txt
├── Procfile
├── runtime.txt
├── .env.example
└── .gitignore
```

---

## 11. Summary of What Changes

| Area | V1 (Current) | V2 (New) |
|---|---|---|
| **LLM** | Anthropic Claude only | OpenAI multi-model (o3, GPT-4o, GPT-4o-mini) |
| **Token budget** | Conservative, truncates files | Unlimited, full context everywhere |
| **Interface** | REST API only | Web UI + WebSocket + REST |
| **UI** | None | Frosted Glassmorphic IDE (4 screens) |
| **Streaming** | None | Token-level streaming with priority channels |
| **Autonomy** | Semi-autonomous | Configurable (supervised ↔ autonomous), toggleable mid-run |
| **Diff review** | After-the-fact | Real-time with per-step or end-of-run approval |
| **Git** | None | Full lifecycle (branch, commit, push, PR, review, merge) |
| **Tests** | Not fed back | Test runner node with failure analysis + retry |
| **Persistence** | None (in-memory) | SQLite with Protocol abstraction |
| **Multi-agent** | Stub | Fully wired coordinator + merger with parallel fan-out |
| **Deployment** | Railway | Local first, Railway for production |
