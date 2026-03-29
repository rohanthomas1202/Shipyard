# Phase 12: Orchestrator + DAG Engine + Contract Foundation - Research

**Researched:** 2026-03-27
**Domain:** DAG-based task orchestration, async scheduling, contract versioning
**Confidence:** HIGH

## Summary

Phase 12 builds a new orchestration layer that sits above the existing LangGraph agent. The orchestrator accepts a task DAG (directed acyclic graph), schedules tasks respecting dependencies with configurable concurrency, persists state for crash recovery, and provides a contract store that agents read from and write back to. The MVP is proven with a hardcoded test DAG running real agents.

The core stack is NetworkX 3.6.1 for DAG representation and topological sorting, the existing SQLite/aiosqlite layer for state persistence, and the existing EventBus for task lifecycle events. No new external dependencies are needed beyond NetworkX. The async scheduler is a custom `asyncio.Semaphore`-based worker pool that uses `topological_generations()` to identify parallelizable task waves.

**Primary recommendation:** Build the orchestrator as a new `agent/orchestrator/` package with three modules: `dag.py` (NetworkX wrapper + DAG model), `scheduler.py` (async execution engine), and `contracts.py` (contract store reader/writer). Persist DAG state in three new SQLite tables alongside the existing schema.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use NetworkX for DAG representation and topological sorting -- mature, no new dependencies, standard Python graph library
- **D-02:** Custom async scheduler on top of NetworkX -- manages a worker pool, checks dependency completion before releasing tasks, limits concurrency (configurable 5-15)
- **D-03:** DAG state persisted to SQLite -- task status, completion timestamps, error details, retry counts -- enables resume from failure without restart
- **D-04:** Contracts stored as git-tracked files in a `contracts/` directory (JSON/YAML/SQL) -- human-readable, diffable, agents treat them like any other file
- **D-05:** Versioning through git history -- no separate version numbers. Each commit to a contract file is a version. Agents read current state from disk.
- **D-06:** Contract types: DB schema (`.sql`), API definitions (OpenAPI `.yaml`), shared TypeScript types (`.ts`), design system rules (`.json`)
- **D-07:** Extend existing EventBus with task lifecycle events (`task_started`, `task_completed`, `task_failed`, `contract_update_requested`) -- reuses P0/P1/P2 priority routing and WebSocket streaming
- **D-08:** Agents report progress through EventBus, orchestrator subscribes and reacts -- scheduling next tasks when dependencies complete
- **D-09:** Hardcoded test DAG with 5-10 tasks with explicit dependencies -- no LLM-based planning needed
- **D-10:** Test DAG runs real agents that write real files, proving the full loop: scheduling -> agent execution -> event reporting -> contract read/write -> state persistence -> resume from failure

### Claude's Discretion
- SQLite schema design for DAG state tables (task_nodes, task_edges, task_executions)
- NetworkX integration details (DiGraph vs custom wrapper)
- Worker pool implementation (asyncio semaphore vs task queue)
- Contract file directory structure and naming conventions
- EventBus event type definitions for task lifecycle

### Deferred Ideas (OUT OF SCOPE)
- Analyzer agent that parses codebases into module maps (Phase 13)
- Planner agent that generates PRDs/specs/DAGs from analysis (Phase 13)
- Failure classification system A/B/C/D (Phase 15)
- Module ownership model (Phase 15)
- DAG visualization in the frontend (Phase 14 -- observability)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-01 | User can submit a codebase path and receive a DAG of executable tasks with dependency ordering | NetworkX DiGraph + topological_sort/topological_generations for ordering; new `/dag` REST endpoints; hardcoded test DAG for MVP proof |
| ORCH-02 | Orchestrator enforces DAG dependencies -- no task executes before its prerequisites complete | Scheduler checks task_executions table for predecessor completion status before releasing; NetworkX `ancestors()` for dependency lookup |
| ORCH-05 | Orchestrator persists DAG state to enable resume from failure without restart | Three SQLite tables (task_nodes, task_edges, task_executions) with status tracking; resume loads DAG from DB, skips completed tasks |
| CNTR-01 | Contract layer stores versioned DB schema, OpenAPI definitions, and shared types | Git-tracked files in `contracts/` directory; versioning via git history; ContractStore class for read/write operations |
| CNTR-02 | Agents read contracts before execution and write back changes through controlled updates | ContractStore.read_contract() before task execution; ContractStore.write_contract() after; EventBus `contract_update_requested` event |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **LLM Provider:** OpenAI only (o3/gpt-4o/gpt-4o-mini)
- **Framework:** LangGraph 1.1.3 -- committed, not switching. Orchestrator sits ABOVE this, not replacing it.
- **Runtime:** Python 3.11, single-process uvicorn, SQLite file DB
- **Naming:** snake_case.py modules, PascalCase classes, snake_case functions
- **Module docstrings:** Required at top of every Python module
- **Typing:** Modern Python 3.11+ syntax (`str | None`, `dict[str, str]`)
- **Persistence pattern:** Protocol-based interface (store/protocol.py), Pydantic models (store/models.py)
- **DI pattern:** `config["configurable"]` dict for graph nodes, `app.state` for server singletons
- **Testing:** pytest + pytest-asyncio

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| networkx | 3.6.1 | DAG representation, topological sorting, cycle detection | Locked decision D-01; mature, pure Python, zero transitive deps |
| aiosqlite | >=0.20.0 | Async SQLite for DAG state persistence | Already in project; reuse existing store pattern |
| pydantic | (transitive via FastAPI) | Data models for DAG tasks/edges/executions | Already in project; matches store/models.py pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyyaml | >=6.0 | Reading/writing OpenAPI YAML contracts | Already in project; used for contract files |
| asyncio (stdlib) | 3.11 | Semaphore-based concurrency control | Worker pool implementation |
| graphlib (stdlib) | 3.11 | Reference only -- NOT used (NetworkX is locked choice) | Awareness for "Don't Hand-Roll" section |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| NetworkX | graphlib.TopologicalSorter (stdlib) | Lighter weight, built-in async-ready API with prepare()/get_ready()/done(), but lacks rich graph queries (ancestors, descendants, is_dag). NetworkX chosen -- locked decision. |
| Custom scheduler | Celery/Dramatiq | Overkill for in-process scheduling; adds Redis/RabbitMQ dependency. Custom asyncio is correct for single-process uvicorn deployment. |
| File-based contracts | DB-stored contracts | Files are diffable, human-readable, git-trackable. Locked decision D-04. |

**Installation:**
```bash
pip install networkx==3.6.1
```

Add to `pyproject.toml` dependencies: `"networkx>=3.6,<4.0"`

## Architecture Patterns

### Recommended Project Structure
```
agent/orchestrator/
    __init__.py           # Empty (project convention)
    dag.py                # TaskDAG class wrapping NetworkX DiGraph
    scheduler.py          # DAGScheduler -- async worker pool
    contracts.py          # ContractStore -- read/write contract files
    models.py             # Pydantic models: TaskNode, TaskEdge, TaskExecution
    events.py             # Task lifecycle event type constants
```

### Pattern 1: TaskDAG -- NetworkX DiGraph Wrapper
**What:** Thin wrapper around `nx.DiGraph` that adds domain-specific methods and serialization to/from SQLite.
**When to use:** All DAG operations -- construction, validation, querying ready tasks, serialization.
**Example:**
```python
# Source: NetworkX 3.6.1 official docs
import networkx as nx

class TaskDAG:
    """DAG representation for task dependency scheduling."""

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def add_task(self, task_id: str, **attrs) -> None:
        self._graph.add_node(task_id, **attrs)

    def add_dependency(self, from_task: str, to_task: str) -> None:
        """from_task must complete before to_task starts."""
        self._graph.add_edge(from_task, to_task)

    def validate(self) -> bool:
        """Returns True if graph is a valid DAG (no cycles)."""
        return nx.is_directed_acyclic_graph(self._graph)

    def get_ready_tasks(self, completed: set[str]) -> list[str]:
        """Return tasks whose all predecessors are in completed set."""
        ready = []
        for node in self._graph.nodes:
            if node in completed:
                continue
            preds = set(self._graph.predecessors(node))
            if preds.issubset(completed):
                ready.append(node)
        return ready

    def get_execution_waves(self) -> list[list[str]]:
        """Return tasks grouped by topological generation (parallelizable waves)."""
        return [list(gen) for gen in nx.topological_generations(self._graph)]

    def get_ancestors(self, task_id: str) -> set[str]:
        """All transitive dependencies of a task."""
        return nx.ancestors(self._graph, task_id)
```

### Pattern 2: DAGScheduler -- Async Semaphore Worker Pool
**What:** Manages concurrent task execution using `asyncio.Semaphore` for concurrency limiting. Subscribes to EventBus for task completion signals and releases downstream tasks.
**When to use:** Runtime scheduling of task execution.
**Example:**
```python
import asyncio

class DAGScheduler:
    """Async DAG-aware task scheduler with configurable concurrency."""

    def __init__(
        self,
        dag: TaskDAG,
        max_concurrency: int = 10,
        event_bus: EventBus | None = None,
        store: Any = None,
    ) -> None:
        self._dag = dag
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._running: set[str] = set()
        self._event_bus = event_bus
        self._store = store
        self._all_done = asyncio.Event()

    async def run(self) -> dict[str, str]:
        """Execute all tasks in dependency order. Returns task_id -> status map."""
        # Load already-completed tasks from DB (for resume)
        if self._store:
            self._completed = await self._load_completed()

        while not self._is_finished():
            ready = self._dag.get_ready_tasks(self._completed | self._failed)
            ready = [t for t in ready if t not in self._running]
            if not ready and not self._running:
                break  # Deadlock or all done
            for task_id in ready:
                self._running.add(task_id)
                asyncio.create_task(self._execute_task(task_id))
            await self._wait_for_progress()
        return {t: "completed" for t in self._completed} | {t: "failed" for t in self._failed}
```

### Pattern 3: ContractStore -- File-Based Contract Reader/Writer
**What:** Reads and writes contract files from the `contracts/` directory relative to the project working directory. Agents call `read_contract()` before execution and `write_contract()` after making changes.
**When to use:** Before and after every agent task execution.
**Example:**
```python
import json
import yaml
from pathlib import Path

class ContractStore:
    """Read and write versioned contract files."""

    def __init__(self, project_path: str) -> None:
        self._base = Path(project_path) / "contracts"

    def read_contract(self, name: str) -> str | None:
        """Read a contract file by name. Returns None if not found."""
        path = self._base / name
        if path.exists():
            return path.read_text()
        return None

    def write_contract(self, name: str, content: str) -> Path:
        """Write a contract file. Creates parent dirs if needed."""
        path = self._base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def list_contracts(self) -> list[str]:
        """List all contract file paths relative to contracts/."""
        if not self._base.exists():
            return []
        return [str(p.relative_to(self._base)) for p in self._base.rglob("*") if p.is_file()]
```

### Pattern 4: SQLite DAG State Schema
**What:** Three tables for crash-recoverable DAG state.
**When to use:** Persist on every state transition.
**Example:**
```sql
-- DAG definitions (one row per task node)
CREATE TABLE IF NOT EXISTS task_nodes (
    id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    task_type TEXT DEFAULT 'agent',
    contract_inputs TEXT,   -- JSON array of contract file names to read
    contract_outputs TEXT,  -- JSON array of contract file names to write
    metadata TEXT,          -- JSON blob for arbitrary task config
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_nodes_dag ON task_nodes(dag_id);

-- DAG edges (dependency relationships)
CREATE TABLE IF NOT EXISTS task_edges (
    id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    from_task TEXT NOT NULL REFERENCES task_nodes(id),
    to_task TEXT NOT NULL REFERENCES task_nodes(id),
    UNIQUE(dag_id, from_task, to_task)
);
CREATE INDEX IF NOT EXISTS idx_task_edges_dag ON task_edges(dag_id);

-- Task execution records (one per attempt)
CREATE TABLE IF NOT EXISTS task_executions (
    id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    task_id TEXT NOT NULL REFERENCES task_nodes(id),
    status TEXT DEFAULT 'pending',  -- pending | running | completed | failed
    attempt INTEGER DEFAULT 1,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result_summary TEXT,            -- JSON blob for task output metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_exec_dag ON task_executions(dag_id);
CREATE INDEX IF NOT EXISTS idx_task_exec_status ON task_executions(dag_id, status);

-- DAG-level tracking
CREATE TABLE IF NOT EXISTS dag_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    status TEXT DEFAULT 'pending',  -- pending | running | completed | failed | paused
    max_concurrency INTEGER DEFAULT 10,
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Anti-Patterns to Avoid
- **Polling for task completion:** Do not use `asyncio.sleep()` loops to check if predecessors finished. Use `asyncio.Event` or callback-driven scheduling from EventBus completion events.
- **Loading full DAG into memory on every operation:** Load once at startup/resume, update incrementally. The SQLite tables are the source of truth; the in-memory NetworkX graph is a working copy.
- **Mixing DAG orchestration into existing graph.py:** The orchestrator is a SEPARATE layer above the LangGraph agent graph. It invokes `graph.ainvoke()` for each task, not modifying the graph itself.
- **Storing contracts in SQLite:** Contracts are git-tracked files (locked decision D-04). Do not duplicate them in the database.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Topological sorting | Custom DFS topo sort | `nx.topological_sort()` / `nx.topological_generations()` | Handles edge cases (disconnected components, cycle detection), battle-tested |
| Cycle detection | Manual cycle finder | `nx.is_directed_acyclic_graph()` | One-liner, handles all graph shapes |
| Ancestor/descendant queries | Recursive traversal | `nx.ancestors()` / `nx.descendants()` | Efficient, handles transitive closure |
| YAML parsing | Custom parser | `yaml.safe_load()` / `yaml.safe_dump()` | Already in project deps |
| Concurrency limiting | Manual counter | `asyncio.Semaphore` | Stdlib, handles edge cases (release-before-acquire, cancellation) |
| UUID generation | Custom ID scheme | `uuid.uuid4().hex[:12]` | Matches existing `_new_id()` pattern in store/models.py |

**Key insight:** NetworkX provides all the graph algorithms needed. The custom code should focus on the scheduling loop (connecting NetworkX outputs to asyncio task management) and persistence (SQLite round-trip), not graph theory.

## Common Pitfalls

### Pitfall 1: SQLite Write Contention Under Concurrency
**What goes wrong:** Multiple concurrent agent tasks try to update their execution status simultaneously, causing `database is locked` errors.
**Why it happens:** SQLite WAL mode allows concurrent reads but serializes writes. With 5-15 concurrent agents all completing around the same time, write contention spikes.
**How to avoid:** Use a single async write queue (or serialize all DB writes through the store's single connection). The existing `aiosqlite` connection is already single-connection -- ensure all status updates go through it, not through separate connections.
**Warning signs:** Intermittent `OperationalError: database is locked` during concurrent task execution.

### Pitfall 2: Deadlock on Circular EventBus Dependencies
**What goes wrong:** Scheduler subscribes to EventBus for `task_completed` events. If the event handler tries to emit new events (e.g., `task_started` for downstream tasks) synchronously within the callback, it can deadlock.
**Why it happens:** EventBus `emit()` is async and may involve awaiting store persistence. Nested awaits in callbacks can create circular waits.
**How to avoid:** Schedule downstream task starts with `asyncio.create_task()` rather than awaiting them directly in the completion handler. Keep EventBus handlers fast and non-blocking.
**Warning signs:** Tasks that should start after a dependency completes never begin.

### Pitfall 3: Resume Skipping In-Progress Tasks
**What goes wrong:** On crash recovery, tasks that were "running" at crash time are neither re-run nor marked failed -- they're stuck.
**Why it happens:** The resume logic only looks for "pending" tasks to schedule and "completed" tasks to skip.
**How to avoid:** On resume, mark all "running" task_executions as "failed" (or a new "interrupted" status), then let the scheduler re-evaluate from scratch. This matches the existing pattern in `server/main.py` `_resume_interrupted_runs()`.
**Warning signs:** After restart, DAG progress counter shows fewer completed than expected but no tasks are running.

### Pitfall 4: Contract File Race Conditions
**What goes wrong:** Two concurrent agents read the same contract, both modify it, and the second write overwrites the first.
**Why it happens:** File-based contracts have no locking mechanism.
**How to avoid:** For MVP, accept last-writer-wins semantics (the hardcoded test DAG should have non-overlapping contract outputs). For later phases, add file-level locking or route contract writes through a single async queue. Document this as a known limitation.
**Warning signs:** Contract file content missing expected entries after concurrent execution.

### Pitfall 5: NetworkX Graph Not Matching SQLite State
**What goes wrong:** In-memory NetworkX graph drifts from persisted SQLite state after partial failures or missed updates.
**Why it happens:** Two sources of truth (in-memory graph + SQLite tables) require careful synchronization.
**How to avoid:** SQLite is the source of truth. On resume, always rebuild the NetworkX graph from SQLite. During execution, write to SQLite FIRST, then update in-memory state. Never update in-memory only.
**Warning signs:** Tasks scheduled that should have been blocked by incomplete dependencies.

## Code Examples

### EventBus Extension for Task Lifecycle Events
```python
# New event type constants for agent/orchestrator/events.py
TASK_LIFECYCLE_EVENTS = frozenset({
    "task_started",
    "task_completed",
    "task_failed",
    "dag_started",
    "dag_completed",
    "dag_failed",
    "contract_updated",
})

# These are P0 (immediate) events -- add to _P0_TYPES in agent/events.py
# They need immediate delivery for:
# 1. Scheduler to release downstream tasks
# 2. Frontend to show real-time DAG progress
```

### Pydantic Models for DAG State
```python
# agent/orchestrator/models.py
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Literal
import uuid

def _new_id() -> str:
    return uuid.uuid4().hex[:12]

def _now() -> datetime:
    return datetime.now(timezone.utc)

class TaskNode(BaseModel):
    id: str = Field(default_factory=_new_id)
    dag_id: str
    label: str
    description: str | None = None
    task_type: str = "agent"
    contract_inputs: list[str] = Field(default_factory=list)
    contract_outputs: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)

class TaskEdge(BaseModel):
    id: str = Field(default_factory=_new_id)
    dag_id: str
    from_task: str
    to_task: str

class TaskExecution(BaseModel):
    id: str = Field(default_factory=_new_id)
    dag_id: str
    task_id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    attempt: int = 1
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)

class DAGRun(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    status: Literal["pending", "running", "completed", "failed", "paused"] = "pending"
    max_concurrency: int = 10
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

### Hardcoded Test DAG Example
```python
# Example MVP test DAG: a simple project scaffolding pipeline
def build_test_dag() -> TaskDAG:
    """Build a hardcoded 7-task test DAG for MVP proof."""
    dag = TaskDAG()

    # Wave 1: Independent setup tasks (run in parallel)
    dag.add_task("init-project", label="Initialize project structure",
                 contract_outputs=["db/schema.sql"])
    dag.add_task("init-contracts", label="Create initial contracts directory",
                 contract_outputs=["api/openapi.yaml"])

    # Wave 2: Depends on project init
    dag.add_task("create-users-table", label="Create users table SQL",
                 contract_inputs=["db/schema.sql"],
                 contract_outputs=["db/schema.sql"])
    dag.add_dependency("init-project", "create-users-table")

    dag.add_task("create-api-routes", label="Create user API routes",
                 contract_inputs=["api/openapi.yaml"],
                 contract_outputs=["api/openapi.yaml"])
    dag.add_dependency("init-contracts", "create-api-routes")

    # Wave 3: Depends on both table + routes
    dag.add_task("create-user-model", label="Create User Pydantic model",
                 contract_inputs=["db/schema.sql", "api/openapi.yaml"])
    dag.add_dependency("create-users-table", "create-user-model")
    dag.add_dependency("create-api-routes", "create-user-model")

    # Wave 4: Depends on model
    dag.add_task("create-user-service", label="Create user service layer",
                 contract_inputs=["db/schema.sql"])
    dag.add_dependency("create-user-model", "create-user-service")

    dag.add_task("create-user-tests", label="Create user test suite")
    dag.add_dependency("create-user-model", "create-user-tests")

    assert dag.validate(), "Test DAG has cycles!"
    return dag
```

### Server Integration Pattern
```python
# In server/main.py lifespan -- add orchestrator initialization
from agent.orchestrator.scheduler import DAGScheduler
from agent.orchestrator.contracts import ContractStore

# Inside lifespan():
#   1. Run DAG schema migration (add tables to existing DB)
#   2. Create orchestrator singleton on app.state
#   app.state.dag_scheduler = None  # Created per-DAG-run
#   app.state.contract_store = None  # Created per-project

# New REST endpoints:
# POST /dag/submit     -- Accept DAG definition, persist, start execution
# GET  /dag/{dag_id}   -- Get DAG status + per-task status
# POST /dag/{dag_id}/resume  -- Resume a paused/failed DAG
# GET  /dag/{dag_id}/tasks   -- List tasks with status
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential task execution (agent/parallel.py gather) | DAG-ordered parallel scheduling | Phase 12 (now) | Multiple independent tasks run concurrently |
| Single agent run per instruction | Multi-task orchestration above agent graph | Phase 12 (now) | One DAG run spawns many agent invocations |
| No contract concept | File-based versioned contracts | Phase 12 (now) | Agents share schema/API agreements |

**Deprecated/outdated:**
- `agent/parallel.py` `run_parallel_batches()`: Still used within individual agent runs for step parallelism, but DAG-level parallelism is now handled by the orchestrator. These are different layers -- parallel.py batches steps WITHIN a single agent task, orchestrator schedules ACROSS tasks.

## Open Questions

1. **Agent invocation interface for DAG tasks**
   - What we know: Each task in the DAG needs to invoke `graph.ainvoke()` with a task-specific instruction and context pack (contracts + relevant files).
   - What's unclear: Exact shape of the "context pack" -- how much context does each agent task receive? The hardcoded test DAG can use simple instructions, but the interface should be extensible for Phase 13 (planner-generated tasks).
   - Recommendation: Define a `TaskContext` dataclass with `instruction: str`, `working_directory: str`, `contracts: dict[str, str]`, `relevant_files: list[str]`. Hardcode these for MVP, make them dynamic later.

2. **DAG submission API shape**
   - What we know: Frontend needs to receive DAG structure for visualization (Phase 14, deferred). Backend needs to accept DAG definitions.
   - What's unclear: Whether DAG submission should accept a full DAG definition (nodes + edges) or just a project path that triggers analysis (Phase 13).
   - Recommendation: For MVP, accept a JSON body with explicit `tasks` and `edges` arrays. The hardcoded test DAG is constructed server-side, but the API shape should work for future phases.

3. **Contract write conflict resolution**
   - What we know: Concurrent agents could write to the same contract file. MVP uses last-writer-wins.
   - What's unclear: Whether even the MVP test DAG might hit this (if two concurrent tasks declare the same contract_output).
   - Recommendation: Design the test DAG so no two concurrent tasks write the same contract file. Add a validation check in the scheduler that flags overlapping contract_outputs in the same wave.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All | Yes | 3.11+ | -- |
| SQLite | DAG state persistence | Yes | bundled | -- |
| NetworkX | DAG operations | No (not installed) | -- | Must install: `pip install networkx==3.6.1` |
| aiosqlite | Async DB access | Yes | >=0.20.0 | -- |
| pyyaml | Contract YAML files | Yes | >=6.0 | -- |
| pytest | Test execution | Yes | >=8.0 | -- |
| pytest-asyncio | Async test support | Yes | >=0.24.0 | -- |

**Missing dependencies with no fallback:**
- `networkx` -- must be added to `pyproject.toml` and installed

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | None (uses pyproject.toml defaults) |
| Quick run command | `python -m pytest tests/test_orchestrator.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-01 | Submit codebase path, receive DAG with dependency ordering | unit | `python -m pytest tests/test_dag.py::test_dag_creation_and_ordering -x` | Wave 0 |
| ORCH-02 | Orchestrator refuses to start task with incomplete prerequisites | unit | `python -m pytest tests/test_scheduler.py::test_dependency_enforcement -x` | Wave 0 |
| ORCH-05 | Kill and restart, resume from exactly where left off | integration | `python -m pytest tests/test_dag_resume.py::test_crash_recovery -x` | Wave 0 |
| CNTR-01 | Contract store reads/writes versioned DB schema, OpenAPI, shared types | unit | `python -m pytest tests/test_contracts.py::test_contract_crud -x` | Wave 0 |
| CNTR-02 | Agents read contracts before execution and write back changes | integration | `python -m pytest tests/test_dag_contracts.py::test_agent_contract_flow -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_dag.py tests/test_scheduler.py tests/test_contracts.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dag.py` -- covers ORCH-01 (DAG creation, topological ordering, cycle detection)
- [ ] `tests/test_scheduler.py` -- covers ORCH-02 (dependency enforcement, concurrency limiting)
- [ ] `tests/test_dag_resume.py` -- covers ORCH-05 (persist state, resume after simulated crash)
- [ ] `tests/test_contracts.py` -- covers CNTR-01 (read/write/list contract files)
- [ ] `tests/test_dag_contracts.py` -- covers CNTR-02 (agent reads contract before task, writes after)
- [ ] `networkx` added to `pyproject.toml` dependencies

## Sources

### Primary (HIGH confidence)
- [NetworkX 3.6.1 DAG documentation](https://networkx.org/documentation/stable/reference/algorithms/dag.html) -- topological_sort, topological_generations, is_directed_acyclic_graph, ancestors, descendants
- Existing codebase: `agent/events.py` (EventBus), `store/sqlite.py` (SQLite schema pattern), `store/models.py` (Pydantic model pattern), `store/protocol.py` (Protocol interface pattern)
- Existing codebase: `agent/parallel.py` (asyncio.gather pattern for parallel execution)
- Existing codebase: `server/main.py` (lifespan pattern, resume pattern, REST endpoint pattern)

### Secondary (MEDIUM confidence)
- [NetworkX PyPI page](https://pypi.org/project/networkx/) -- version 3.6.1, released Dec 2025
- [Python graphlib documentation](https://docs.python.org/3.11/library/graphlib.html) -- TopologicalSorter API reference (for comparison, not used)
- [DAG scheduler patterns](https://dev.to/romank/processing-dags-with-async-python-and-graphlib-2c0g) -- async DAG execution patterns with Python

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- NetworkX is well-documented, locked decision, existing SQLite/EventBus patterns are verified from source
- Architecture: HIGH -- Module structure follows existing project conventions; patterns derived from actual codebase analysis
- Pitfalls: HIGH -- SQLite write contention and resume logic pitfalls derived from real patterns observed in store/sqlite.py and server/main.py

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain, no fast-moving dependencies)
