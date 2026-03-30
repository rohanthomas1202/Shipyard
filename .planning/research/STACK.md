# Stack Research

**Domain:** Autonomous coding agent -- persistent loop, from-scratch generation, intervention logging, comparative analysis
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Assessment

The v1.3 features require **zero new Python dependencies** and **zero new frontend dependencies**. Every capability maps cleanly onto existing infrastructure. The danger is adding libraries where none are needed.

The existing stack (FastAPI WebSocket, EventBus, SQLite, Zustand, asyncio) already provides the primitives for persistent loops, structured logging, and analysis generation. What's needed is new **application code** wired to existing libraries, not new libraries.

## What Already Exists (DO NOT Add)

These capabilities are fully covered by the current stack. Listed to prevent accidental re-introduction.

| Capability Needed | Already Covered By | Location |
|---|---|---|
| WebSocket bidirectional messaging | FastAPI WebSocket + ConnectionManager | `server/websocket.py` |
| Real-time event streaming | EventBus with P0/P1/P2 routing | `agent/events.py` |
| Background task execution | `asyncio.create_task()` pattern | `server/main.py` |
| SQLite persistence | aiosqlite + WAL mode | `store/sqlite.py` |
| Frontend state management | Zustand 5.x | `web/package.json` |
| LLM calls for analysis generation | OpenAI via ModelRouter | `agent/router.py` |
| DAG execution + scheduling | DAGScheduler + BranchManager | `agent/orchestrator/` |
| Structured event models | Pydantic BaseModel | `store/models.py` |
| Shell command execution | `run_command_async()` | `agent/tools/shell.py` |
| Git operations | GitManager | `agent/git.py` |
| JSON serialization | stdlib `json` | Built-in |
| Markdown generation | Python f-strings / template strings | No library needed |

## New Code Required (No New Dependencies)

### 1. Persistent Agent Loop (Backend)

**What:** `POST /rebuild` endpoint that wraps `run_rebuild()` as a background task, streaming progress through the existing EventBus.

**Stack decision:** Use `asyncio.create_task()` directly. Do NOT use Celery, ARQ, or any task queue.

**Why:** Single-process uvicorn deployment on Railway. Adding a task queue means adding Redis/RabbitMQ infrastructure, a worker process, and a Procfile change -- all for running exactly one rebuild at a time. `asyncio.create_task()` is the established pattern in `server/main.py` already, and the rebuild is inherently async (LLM calls, git operations). The EventBus already handles streaming to WebSocket clients.

**Implementation pattern:**
```python
# server/main.py -- new endpoint
@app.post("/rebuild")
async def start_rebuild(req: RebuildRequest):
    run_id = _new_id()
    task = asyncio.create_task(_run_rebuild_with_events(run_id, req, app.state.event_bus))
    runs[run_id] = {"status": "running", "task": task}
    return {"run_id": run_id}
```

**WebSocket instruction flow:** Extend `ConnectionManager.handle_client_message()` with a new `action: "rebuild"` that triggers the same background task. This keeps the existing subscribe/reconnect/approve/reject/stop protocol intact and adds one new action type.

### 2. From-Scratch Code Generation

**What:** Remove `_seed_output_from_source()` from the rebuild pipeline. Instead, the planner generates file-creation tasks, and the executor writes files from scratch using the existing `file_ops.write_file()`.

**Stack decision:** No new dependencies. The existing `agent/tools/file_ops.py` already has `write_file()`. The LangGraph editor node already handles file creation (it writes `new_content` when `old_content` is empty/None).

**Why:** The current pipeline seeds files then edits them. For from-scratch generation, the planner must emit `create` tasks instead of `edit` tasks. This is a planning prompt change + a small executor change, not a library change.

**Key change:** The `ship_executor.py` `build_agent_executor()` must handle tasks where no file exists yet. Currently it assumes files exist. The fix is in the agent state setup: set `instruction` to include the full file content to generate, and the editor node's "no anchor = write whole file" path handles the rest.

### 3. Intervention Logging

**What:** New SQLite table + Pydantic model for structured intervention records. Each intervention captures: timestamp, rebuild phase, what went wrong, what the human did, time spent, and outcome.

**Stack decision:** Use the existing `aiosqlite` + Pydantic pattern. Add a new `Intervention` model to `store/models.py` and a new table to the SQLite schema.

**Why:** The pattern is established (Project, Run, Event, EditRecord, etc. all follow it). No ORM needed -- raw SQL with Pydantic serialization is the project convention.

**New model:**
```python
class Intervention(BaseModel):
    id: str = Field(default_factory=_new_id)
    rebuild_id: str
    phase: str  # "clone", "analyze", "plan", "execute", "build", "deploy"
    trigger: str  # What went wrong
    action: str  # What the human did
    outcome: str  # Result of the intervention
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
```

**Logging mechanism:** Two paths:
1. **Automatic:** Wrap rebuild phases in try/except; on failure, emit an `intervention_needed` event via EventBus. When the rebuild resumes after human action, record the intervention.
2. **Manual:** `POST /rebuild/{id}/intervention` endpoint for the human to log what they did (for interventions that happen outside the system, like fixing Railway billing).

### 4. Comparative Analysis Generation

**What:** After rebuild completes, generate a 7-section analysis document comparing the rebuilt Ship to the original. Uses LLM to draft sections from structured data.

**Stack decision:** Use the existing `ModelRouter.call()` for LLM generation. Output as Markdown written to the filesystem. No templating library needed.

**Why:** The analysis sections (architecture comparison, code quality metrics, test coverage, etc.) require LLM reasoning over structured data. The ModelRouter already handles `gpt-4o` calls with the right context window (128k). The data sources are: intervention logs (from SQLite), task execution results (from DAG persistence), token usage (from token_usage table), and file-level diffs (from git).

**Data collection:** All inputs already exist:
- Task results: `task_executions` table
- Token usage: `token_usage` table
- Intervention logs: New `interventions` table (above)
- Code metrics: Python line counting (`os.walk` + read)
- Git diffs: `run_command_async(["git", "diff", "--stat", ...])`

### 5. Frontend Live Rebuild Panel

**What:** New React component showing rebuild progress (clone -> analyze -> plan -> execute -> build -> deploy) with live task completion counts.

**Stack decision:** Use existing Zustand store + WebSocket subscription. Add a new Zustand slice for rebuild state. No new frontend dependencies.

**Why:** The frontend already handles real-time event streams via `useWebSocket`. The rebuild progress events will use the same EventBus P0 event types (`dag_started`, `task_completed`, `progress_update`, etc.) that the orchestrator already emits. The frontend just needs a new component to render them.

### 6. Railway Deployment

**What:** Deploy the rebuilt Ship app to Railway.

**Stack decision:** Use Railway CLI (`railway`) via `run_command_async()`. No Railway SDK needed.

**Why:** Railway CLI is the standard deployment tool. It's a single `railway up` command. The deployment step is a shell command, not a library integration. Install Railway CLI as a system dependency on the build machine, not as a Python package.

**Required:** `RAILWAY_TOKEN` environment variable. Add to `.env.example`.

## Recommended Stack (Unchanged)

### Core Technologies (No Changes)

| Technology | Version | Purpose | Status for v1.3 |
|---|---|---|---|
| Python | 3.11 | Backend runtime | No change |
| LangGraph | 1.1.3 | Agent orchestration | No change |
| FastAPI | >=0.115.0 | HTTP + WebSocket server | No change, use existing WebSocket |
| React | 19.2.4 | Frontend UI | No change |
| Zustand | 5.0.12 | Frontend state | No change, add rebuild slice |
| SQLite/aiosqlite | >=0.20.0 | Persistence | No change, add interventions table |
| OpenAI | >=1.60.0 | LLM calls | No change |
| networkx | >=3.6 | DAG operations | No change |

### Supporting Libraries (No Changes)

| Library | Version | Purpose | v1.3 Usage |
|---|---|---|---|
| httpx | >=0.28.0 | HTTP client | Railway API if CLI unavailable |
| pyyaml | >=6.0 | YAML parsing | PRD/spec parsing |
| Pydantic | (via FastAPI) | Data models | New Intervention model |
| uvicorn | >=0.34.0 | ASGI server | No change |

### Development Tools (No Changes)

| Tool | Purpose | Notes |
|---|---|---|
| pytest + pytest-asyncio | Python testing | Test new endpoints and models |
| Playwright | E2E testing | Test rebuild UI flow |
| ESLint | Frontend linting | No change |

## What NOT to Add

| Avoid | Why | Use Instead |
|---|---|---|
| Celery / ARQ / Dramatiq | Requires Redis + worker process; single rebuild at a time doesn't justify it | `asyncio.create_task()` |
| Jinja2 / Mako | Markdown analysis is simple string formatting, not HTML templating | f-strings with `textwrap.dedent` |
| SQLAlchemy / Tortoise ORM | Project uses raw SQL with Pydantic; adding ORM for one table is wrong | aiosqlite + Pydantic (existing pattern) |
| Railway Python SDK | No official SDK exists; CLI is the deployment tool | `railway` CLI via shell |
| Socket.IO / python-socketio | Already have native FastAPI WebSocket; Socket.IO adds complexity and a dependency | FastAPI WebSocket (existing) |
| Redis | No pub/sub or caching need; single-process with in-memory EventBus | EventBus (existing) |
| Pandas / NumPy | Comparative analysis is LLM-generated narrative, not statistical computation | Python stdlib + LLM |
| react-query / SWR | Zustand already manages server state via WebSocket; HTTP polling not needed | Zustand + WebSocket (existing) |
| Markdown parsing library (Python) | We generate Markdown, we don't parse it | f-strings |
| `cloc` (external binary) | Nice-to-have for LOC counting but adds system dependency | Python line counting (walk + count) |

## New SQLite Schema Additions

```sql
-- Intervention logging for rebuild runs
CREATE TABLE IF NOT EXISTS interventions (
    id TEXT PRIMARY KEY,
    rebuild_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    trigger TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    duration_seconds REAL DEFAULT 0.0,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_interventions_rebuild ON interventions(rebuild_id);

-- Rebuild runs (extends dag_runs with rebuild-specific fields)
CREATE TABLE IF NOT EXISTS rebuild_runs (
    id TEXT PRIMARY KEY,
    dag_run_id TEXT REFERENCES dag_runs(id),
    project_id TEXT REFERENCES projects(id),
    source_repo TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    current_phase TEXT DEFAULT 'init',
    clone_dir TEXT,
    output_dir TEXT,
    analysis_path TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## New API Endpoints

| Method | Path | Purpose | Request Body |
|---|---|---|---|
| POST | `/rebuild` | Start a rebuild run | `{repo_url, output_dir?, max_concurrency?}` |
| GET | `/rebuild/{id}` | Get rebuild status | -- |
| POST | `/rebuild/{id}/intervention` | Log an intervention | `{phase, trigger, action, outcome, duration_seconds?}` |
| GET | `/rebuild/{id}/interventions` | List interventions | -- |
| GET | `/rebuild/{id}/analysis` | Get comparative analysis | -- |
| POST | `/rebuild/{id}/cancel` | Cancel a rebuild | -- |

## New EventBus Event Types

| Event Type | Priority | Purpose |
|---|---|---|
| `rebuild_started` | P0 | Rebuild kicked off |
| `rebuild_phase_changed` | P0 | Phase transition (clone -> analyze -> plan -> execute -> build -> deploy) |
| `rebuild_completed` | P0 | Rebuild finished successfully |
| `rebuild_failed` | P0 | Rebuild failed |
| `intervention_needed` | P0 | Human intervention required |
| `intervention_logged` | P0 | Intervention recorded |
| `analysis_ready` | P0 | Comparative analysis generated |

These integrate with existing P0 immediate-send behavior. No EventBus code changes needed -- just new type strings added to `_P0_TYPES` frozenset.

## New WebSocket Actions

| Action | Direction | Purpose |
|---|---|---|
| `rebuild` | Client -> Server | Start a rebuild (alternative to POST /rebuild) |
| `log_intervention` | Client -> Server | Log an intervention during rebuild |

These extend the existing `handle_client_message()` switch in `ConnectionManager`.

## Installation

No new packages to install. The existing `pip install -e .` and `cd web && npm install` cover everything.

The only new system-level tool is the Railway CLI for deployment:
```bash
# Railway CLI (for deployment step only)
npm install -g @railway/cli
# or
brew install railway
```

## Version Compatibility

No new compatibility concerns. All additions use existing packages at their current pinned versions.

| Component | Existing Version | v1.3 Impact |
|---|---|---|
| aiosqlite >=0.20.0 | Used for new tables | Schema migration via existing pattern (try ALTER, catch if exists) |
| FastAPI >=0.115.0 | New endpoints | Standard route additions |
| Pydantic (transitive) | New models | Same BaseModel pattern |
| Zustand 5.0.12 | New store slice | Standard slice addition |

## Integration Points

### Backend Flow
```
POST /rebuild
  -> asyncio.create_task(run_rebuild_with_events())
    -> EventBus.emit(rebuild_started)
    -> clone_repo()          -> EventBus.emit(rebuild_phase_changed)
    -> analyze_codebase()    -> EventBus.emit(rebuild_phase_changed)
    -> run_pipeline()        -> EventBus.emit(rebuild_phase_changed)
    -> DAGScheduler.run()    -> existing task_started/completed events
    -> generate_analysis()   -> EventBus.emit(analysis_ready)
    -> EventBus.emit(rebuild_completed)
```

### Frontend Flow
```
User clicks "Rebuild" -> WebSocket action: "rebuild"
  -> Zustand rebuild slice updates phase
  -> RebuildPanel renders progress bar
  -> TaskGrid shows individual task statuses
  -> InterventionModal pops on intervention_needed
  -> AnalysisView renders when analysis_ready arrives
```

## Sources

- FastAPI WebSocket documentation (official) -- confirmed background task pattern with asyncio.create_task
- Project codebase analysis -- `server/main.py`, `agent/events.py`, `server/websocket.py`, `store/sqlite.py`, `scripts/ship_rebuild.py`
- Railway CLI documentation -- deployment via CLI, RAILWAY_TOKEN env var
- Existing project patterns -- all recommendations follow established conventions in the codebase

---
*Stack research for: Shipyard v1.3 -- persistent loop, from-scratch generation, intervention logging, comparative analysis*
*Researched: 2026-03-30*
