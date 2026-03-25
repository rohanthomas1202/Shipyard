# Shipyard V2 — Frosted Glassmorphic IDE Design Spec

## Overview

Shipyard V2 transforms the current API-only autonomous coding agent into a full-featured, visually stunning IDE-like application with a Frosted Glassmorphic UI, multi-model OpenAI routing, real-time streaming, Git/GitHub integration, and configurable autonomy.

**Key decisions:**
- Switch from Anthropic Claude to OpenAI via a model-capability registry and policy-based router. Initial defaults use o3 / GPT-4o / GPT-4o-mini, but model selection is configuration-driven and swappable as OpenAI's recommended defaults evolve
- Deterministic context assembly — fill available window using ranked working set, deduplicated file content, execution evidence, and dependency-aware summaries. Prefer relevance-ranked saturation over naive maximal inclusion
- Policy-based multi-model routing with typed step execution + auto-escalate
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

Replaces the current single-model `agent/llm.py` with a policy-based routing layer backed by a model capability registry.

### Model Capability Registry

Models are not hardcoded into the architecture. Instead, a configuration-driven registry maps model IDs to capabilities, allowing seamless swaps as OpenAI's recommended defaults evolve.

```python
# agent/models.py — model registry (config-driven, not hardcoded)
MODEL_REGISTRY = {
    "o3": {
        "id": "o3",
        "context_window": 200_000,
        "max_output": 100_000,
        "tier": "reasoning",       # reasoning | general | fast
        "timeout": 120,
        "capabilities": ["planning", "complex_edit", "conflict_resolution"],
    },
    "gpt-4o": {
        "id": "gpt-4o",
        "context_window": 128_000,
        "max_output": 16_384,
        "tier": "general",
        "timeout": 60,
        "capabilities": ["edit", "read", "summarize", "merge"],
    },
    "gpt-4o-mini": {
        "id": "gpt-4o-mini",
        "context_window": 128_000,
        "max_output": 16_384,
        "tier": "fast",
        "timeout": 30,
        "capabilities": ["classify", "validate", "syntax_check"],
    },
}
```

When OpenAI releases new models (e.g., gpt-5.4), update the registry — no code changes needed in nodes.

### Routing Policy

Routing is policy-based: each task type maps to a model tier, not a specific model name. The router resolves the tier to the best available model from the registry.

| Task Type | Tier | Default Resolution | Escalation |
|---|---|---|---|
| `plan` | reasoning | o3 | — |
| `coordinate` | reasoning | o3 | — |
| `edit_complex` | reasoning | o3 | — |
| `edit_simple` | general | GPT-4o | reasoning tier on validation fail |
| `read` | general | GPT-4o | — |
| `validate` | fast | GPT-4o-mini | general tier on failure |
| `classify` | — (no LLM) | keyword match | fast tier if ambiguous |
| `merge` | general | GPT-4o | reasoning tier on conflict |
| `summarize` | general | GPT-4o | — |
| `parse_results` | general | GPT-4o | reasoning tier on complex failures |

### Deterministic Context Assembly

Instead of "send as much as fits," context is assembled through a ranked pipeline:

```
┌─────────────────────────────────────────────┐
│         Context Assembly Pipeline            │
│                                              │
│  1. Task context (always included)           │
│     - current instruction, active step       │
│     - current branch, working directory      │
│                                              │
│  2. Working set (highest priority)           │
│     - file being edited (full content)       │
│     - active error/stack trace               │
│     - open diffs pending approval            │
│                                              │
│  3. Reference set (fill remaining window)    │
│     - files in plan's target_files           │
│     - imports / call graph neighbors         │
│     - type definitions used by edited code   │
│                                              │
│  4. Execution evidence                       │
│     - latest test failures                   │
│     - lint output, build errors              │
│                                              │
│  5. Conversation memory (evict first)        │
│     - minimum needed to continue reasoning   │
│                                              │
│  Rules:                                      │
│  - Dedupe identical file chunks              │
│  - Never resend unchanged payloads on retry  │
│  - Pin current file + error trace            │
│  - Evict conversation memory first           │
│  - Cap at model's context_window from        │
│    registry (not hardcoded)                  │
└─────────────────────────────────────────────┘
```

### Typed Plan Steps

The planner outputs structured step objects. This replaces keyword-based classification with schema-driven execution.

```python
class PlanStep(BaseModel):
    id: str
    kind: Literal["read", "edit", "exec", "test", "git"]
    target_files: list[str] = []
    command: str | None = None              # for exec/test steps
    acceptance_criteria: list[str] = []
    complexity: Literal["simple", "complex"]
    depends_on: list[str] = []              # step IDs for ordering
```

The classifier becomes a lightweight resolver only when a step is malformed or missing fields — not the primary routing mechanism.

### Dynamic Complexity Promotion

The planner assigns initial complexity, but runtime triggers can promote "simple" to "complex":

- Multiple files actually touched during edit
- Changed public/exported API signature
- First validation attempt failed
- Retry count > 0

Promotion is automatic and logged in the trace.

### Failure Definitions

| Failure Type | Trigger | Behavior |
|---|---|---|
| Malformed output | LLM returns unparseable JSON or missing fields | Retry same model once, then escalate tier |
| Syntax validation fail | Syntax check fails on edited code | Rollback edit, escalate tier, retry with error context |
| Type validation fail | Type checker reports errors | Include diagnostic output, escalate tier, retry |
| Test failure | Tests fail after edit | Route through `parse_results` → repair loop (up to 3 retries) |
| Nondeterministic test fail | Test fails intermittently | Quarantine and surface to human — do not retry |
| Timeout | Per model's `timeout` from registry | Retry same model once, then escalate tier |
| API error (429/500) | OpenAI rate limit or server error | Exponential backoff (1s, 2s, 4s), max 3 retries |
| Terminal failure | Final escalation tier also fails | Emit `error` event, set run status to `waiting_for_human`, pause for user intervention |

### Module: `agent/router.py`

```python
class ModelRouter:
    """Policy-based router with model capability registry."""

    def __init__(self, registry: dict, policy: dict):
        self.registry = registry   # model ID → capabilities
        self.policy = policy       # task type → tier

    async def call(
        self,
        task_type: str,
        messages: list,
        context: ContextAssembly,
        structured_output: type | None = None,
    ) -> LLMResponse:
        """Resolve tier → model, assemble context, call, auto-escalate on failure."""

    async def escalate(
        self,
        task_type: str,
        messages: list,
        prior_failure: str,
    ) -> LLMResponse:
        """Retry with next-higher tier model after failure."""

    def resolve_model(self, task_type: str) -> ModelConfig:
        """Look up tier for task, resolve to best available model."""
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
| `validator` | Enhanced | Multi-layer validation pipeline (syntax → lint → typecheck → test). Escalation on failure. Rollback + retry with stronger model |
| `executor` | Same | Runs shell commands |
| `test_runner` | **New** | Runs project tests, captures output |
| `parse_results` | **New** | Analyzes test output, identifies which edits caused failures |
| `git_ops` | **New** | Branch creation, commits, push, PR creation, PR comment response |
| `reporter` | Enhanced | Richer summary, includes model usage stats, git operations |
| `merger` | Enhanced | Fully wired conflict detection for parallel agent outputs |

### Validation Pipeline

Validation is a multi-layer pipeline, not just syntax checking. Each layer runs in order; failure at any layer triggers the appropriate escalation.

| Layer | Tool | Trigger | Failure Behavior |
|---|---|---|---|
| 1. Syntax | Language-specific parser (ts-node, python -c) | Every edit | Same-model retry once, then escalate tier |
| 2. Lint/Format | Project's configured lint command | Every edit | Include diagnostic, retry with lint output |
| 3. Typecheck | `tsc --noEmit`, `mypy`, etc. | Edits touching type signatures | Include full diagnostic, escalate tier |
| 4. Targeted test | Project's test command (scoped to affected files) | After all step edits approved | Route through `parse_results` → repair loop |
| 5. Full build | Project's build command | End of run (optional) | Surface to human if fails |

Layers 1-2 run automatically. Layers 3-5 run only if the project has configured the relevant commands in Project Settings.

### Merge Conflict Semantics

Three-tier merge check for parallel branch outputs:

| Tier | Check | Resolution |
|---|---|---|
| 1. File overlap | Same file edited by multiple branches | Proceed to tier 2 |
| 2. Range/symbol overlap | Same function or code range edited | GPT-4o semantic merge, escalate to o3 if needed |
| 3. Interface overlap | Changed exported signatures that affect other branches | Downstream validation required — re-run validation on merged result |

Rules:
- Disjoint edits in same file → auto-merge (no LLM needed)
- Overlapping edits → semantic merge with LLM
- Changed exported signatures → trigger downstream re-validation before accepting merge
- Merge result always re-runs relevant tests before proceeding to git_ops
- Unresolvable conflicts → pause for human

### Key Improvements

- **Test feedback loop** — agent runs tests after edits. If they fail, it reads the error, identifies the cause, and fixes (up to 3 retries). Nondeterministic failures are quarantined and surfaced to human.
- **Deterministic context assembly** — ranked pipeline fills model window by relevance. Dedupes file content, evicts conversation memory first, never resends unchanged payloads on retry.
- **Approval state machine** — edits follow a strict state machine with idempotent transitions (see Run Safety section below).
- **Parallel execution** — coordinator fans out independent steps via LangGraph `Send` API. Merger node reconverges outputs with 3-tier conflict semantics.

### Run Safety & Idempotency

Edit approval is a persisted state machine, not a fire-and-forget WebSocket message.

**Edit states:**
```
proposed → approved → applied → committed
    ↓
  rejected
```

**Rules:**
- Every approval/reject action has an idempotency key (edit ID + action + timestamp)
- Resume only advances from allowed predecessor states
- Edit application is atomic — all file writes in a step succeed or all roll back
- WebSocket actions are advisory (low-latency UX), REST is authoritative (durable state)
- Duplicate approvals are no-ops (idempotent)
- If UI disconnects after approval but before resume, the server still has the durable state and will resume when reconnected

**Mode toggle during run:**
- Switching to autonomous mid-run auto-approves all pending `proposed` edits and skips future approval gates
- Switching to supervised mid-run pauses at the next edit boundary — does not retroactively require approval for already-applied edits

### Reconnect UI Recovery

On WebSocket reconnect, the server sends a compact **run snapshot** before replaying durable events:

```json
{
  "type": "snapshot",
  "run_id": "run_456",
  "active_node": "editor",
  "current_step": 3,
  "total_steps": 7,
  "pending_approvals": ["edit_abc", "edit_def"],
  "latest_diffs": [...],
  "current_branch": "shipyard/refactor-auth",
  "autonomy_mode": "supervised",
  "status": "running"
}
```

This allows the frontend to reconstruct panel state deterministically without needing the full token stream history.

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

### REST vs WebSocket Responsibilities

| Concern | WebSocket | REST |
|---|---|---|
| Event streaming | Primary delivery | — |
| Approve/reject edits | Low-latency advisory | Authoritative durable write |
| Stop run | Immediate signal | — |
| Subscribe to channels | Panel registration | — |
| Read run state | — | Source of truth |
| Create/resume runs | — | Only via REST |
| Git operations | — | Only via REST |
| Reconnect recovery | Snapshot + replay | Full state read |

**Principle:** WebSocket is for real-time UX. REST is the source of truth for all durable state. On any conflict, REST wins.

---

## 10. File Structure (V2)

```
Shipyard/
├── agent/                          # Core agent logic (Python)
│   ├── __init__.py
│   ├── state.py                    # Enhanced AgentState
│   ├── graph.py                    # LangGraph graph with new nodes
│   ├── router.py                   # NEW: Policy-based model router
│   ├── models.py                   # NEW: Model capability registry
│   ├── context.py                  # NEW: Deterministic context assembly pipeline
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

## 11. Local Trust & Security

Shipyard V2 is single-user and local-first, but it holds repository mutation privileges and credentials. These guardrails apply even without multi-user auth.

### Credential Handling

- GitHub PAT stored in SQLite, accessible only on localhost
- All events and traces redact secrets (PAT, API keys) before persistence
- `.env` file excluded from git (already in `.gitignore`)
- Future: integrate with macOS Keychain / OS credential store

### Execution Safety

- Shell execution (`executor`, `test_runner`) restricted to project's working directory
- Destructive commands (`rm -rf`, `git push --force`, `DROP TABLE`) require explicit allowlist in Project Settings
- All git/network mutations logged in `git_operations` audit table
- No remote code execution — agent only modifies local files

### Trust Assumptions

This is a local development tool. The trust boundary is:
- The user trusts the agent to modify files within the configured project directory
- The user trusts the agent to push to the configured GitHub repository
- The user reviews diffs before approval (in supervised mode)
- The agent does NOT have access to files outside the project directory

---

## 12. PR Review Polling

Since webhooks are out of scope for V2, polling is the mechanism for PR review comments.

### Polling Behavior

- **Interval:** 30 seconds while a PR is open and Shipyard is running
- **Conditional requests:** Use `If-None-Match` / ETag headers to avoid rate limit waste
- **Comment cursoring:** Track `since` timestamp per PR to only fetch new comments
- **Deduplication:** Comments are deduplicated by GitHub comment ID before surfacing to UI
- **Rate limit awareness:** Back off to 60s interval if approaching GitHub API rate limit (check `X-RateLimit-Remaining` header)

---

## 13. Implementation Phases

### Phase 1: Core Migration

- OpenAI migration + model registry + router abstraction
- SQLite store with Protocol interface
- Basic run/event persistence
- Supervised diff review via REST
- No parallelism, no PR review loop

### Phase 2: Web IDE + Streaming

- Vite + React frontend shell (all 4 screens)
- WebSocket streaming with priority channels
- Approval checkpoints with state machine
- Git commit/push/PR create
- Validation pipeline (syntax + lint + typecheck)
- Test feedback loop

### Phase 3: Advanced Features

- Parallel branch execution via LangGraph Send
- Merger with 3-tier conflict resolution
- PR review polling + comment response loop
- Autonomy mode switching mid-run
- Dynamic complexity promotion
- Reconnect snapshots

---

## 14. Summary of What Changes

| Area | V1 (Current) | V2 (New) |
|---|---|---|
| **LLM** | Anthropic Claude only | OpenAI via policy-based router + model registry (o3, GPT-4o, GPT-4o-mini initial defaults) |
| **Context strategy** | Conservative, truncates files | Deterministic assembly pipeline — ranked, deduplicated, relevance-saturated |
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
