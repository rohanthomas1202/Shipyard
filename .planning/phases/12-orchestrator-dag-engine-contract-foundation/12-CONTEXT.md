# Phase 12: Orchestrator + DAG Engine + Contract Foundation - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the core DAG-based orchestrator that accepts a task graph, schedules tasks respecting dependencies, persists state for crash recovery, and provides a versioned contract store that agents read from and write back to. Proven with a hardcoded test DAG that runs real agents writing real files.

</domain>

<decisions>
## Implementation Decisions

### DAG Engine
- **D-01:** Use NetworkX for DAG representation and topological sorting — mature, no new dependencies, standard Python graph library
- **D-02:** Custom async scheduler on top of NetworkX — manages a worker pool, checks dependency completion before releasing tasks, limits concurrency (configurable 5-15)
- **D-03:** DAG state persisted to SQLite — task status, completion timestamps, error details, retry counts — enables resume from failure without restart

### Contract Store
- **D-04:** Contracts stored as git-tracked files in a `contracts/` directory (JSON/YAML/SQL) — human-readable, diffable, agents treat them like any other file
- **D-05:** Versioning through git history — no separate version numbers. Each commit to a contract file is a version. Agents read current state from disk.
- **D-06:** Contract types: DB schema (`.sql`), API definitions (OpenAPI `.yaml`), shared TypeScript types (`.ts`), design system rules (`.json`)

### Agent Communication
- **D-07:** Extend existing EventBus with task lifecycle events (`task_started`, `task_completed`, `task_failed`, `contract_update_requested`) — reuses P0/P1/P2 priority routing and WebSocket streaming
- **D-08:** Agents report progress through EventBus, orchestrator subscribes and reacts — scheduling next tasks when dependencies complete

### MVP Proof
- **D-09:** Hardcoded test DAG with 5-10 tasks (e.g., "create schema.sql", "create users table", "create API route") with explicit dependencies — no LLM-based planning needed
- **D-10:** Test DAG runs real agents that write real files, proving the full loop: scheduling → agent execution → event reporting → contract read/write → state persistence → resume from failure

### Claude's Discretion
- SQLite schema design for DAG state tables (task_nodes, task_edges, task_executions)
- NetworkX integration details (DiGraph vs custom wrapper)
- Worker pool implementation (asyncio semaphore vs task queue)
- Contract file directory structure and naming conventions
- EventBus event type definitions for task lifecycle

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Agent Architecture
- `agent/graph.py` — Current LangGraph StateGraph (11 nodes, conditional edges) — new orchestrator sits above this
- `agent/state.py` — AgentState TypedDict — reference for how state flows through agents
- `agent/parallel.py` — Existing asyncio.gather batch execution — pattern to extend for DAG-scheduled parallelism
- `agent/events.py` — EventBus with P0/P1/P2 priority routing — extend with task lifecycle events

### Server & Persistence
- `server/main.py` — FastAPI server, run lifecycle, WebSocket gateway — orchestrator integrates here
- `store/sqlite.py` — SQLiteSessionStore with WAL mode — add DAG state tables alongside existing schema
- `store/protocol.py` — SessionStore Protocol — reference for persistence interface pattern
- `store/models.py` — Pydantic models for Project, Run, Event, EditRecord — pattern for new DAG models

### Frontend (for event streaming)
- `web/src/stores/wsStore.ts` — Zustand store receiving WebSocket events — will need new event types for DAG progress
- `web/src/context/WebSocketContext.tsx` — WebSocket bridge to Zustand — routes new event types

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EventBus` (agent/events.py) — priority-based event dispatch with batching, directly extensible for task lifecycle events
- `SQLiteSessionStore` (store/sqlite.py) — async SQLite with WAL mode, add new tables for DAG state
- `asyncio.gather` pattern (agent/parallel.py) — existing parallel execution, replace with DAG-aware scheduling
- `ModelRouter` (agent/router.py) — tiered LLM routing, reuse for agent task execution
- `TraceLogger` (agent/tracing.py) — structured JSON tracing, extend for DAG-level traces

### Established Patterns
- Pydantic models for data structures (store/models.py)
- Protocol-based interfaces for swappable backends (store/protocol.py)
- FastAPI lifespan for initialization (server/main.py)
- Config via `config["configurable"]` dict for dependency injection into graph nodes

### Integration Points
- New `/dag` API endpoints in server/main.py (submit DAG, get status, resume)
- New SQLite tables alongside existing schema (task_nodes, task_edges, task_executions)
- New EventBus event types for frontend DAG visualization
- Orchestrator as a new top-level module (`agent/orchestrator/` or `orchestrator/`)

</code_context>

<specifics>
## Specific Ideas

- The orchestrator is a NEW layer above the existing LangGraph agent — it doesn't replace the current graph, it manages multiple invocations of it
- Each "agent" in the DAG is fundamentally a function that receives a task description + context pack and produces file changes
- The hardcoded test DAG should prove: dependency ordering, concurrent execution (2-3 tasks at once), failure + retry, kill + resume, contract read before execution + write after

</specifics>

<deferred>
## Deferred Ideas

- Analyzer agent that parses codebases into module maps (Phase 13)
- Planner agent that generates PRDs/specs/DAGs from analysis (Phase 13)
- Failure classification system A/B/C/D (Phase 15)
- Module ownership model (Phase 15)
- DAG visualization in the frontend (Phase 14 — observability)

</deferred>

---

*Phase: 12-orchestrator-dag-engine-contract-foundation*
*Context gathered: 2026-03-29*
