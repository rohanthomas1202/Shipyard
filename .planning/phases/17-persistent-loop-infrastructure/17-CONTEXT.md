# Phase 17: Persistent Loop Infrastructure - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert the fire-and-forget `ship_rebuild.py` script into a managed, streamable background task accessible from both the frontend (via POST /rebuild + WebSocket streaming) and CLI. The agent stays alive and accepts rebuild triggers without restarting. Includes rebuild history, cancel/retry controls, and a frontend progress panel.

</domain>

<decisions>
## Implementation Decisions

### Progress Granularity
- **D-01:** Per-task granular streaming. Every task start/complete/fail, CI results per task, token usage per task. ~50+ events for a full rebuild. Matches what DAGScheduler already emits internally.
- **D-02:** New `rebuild_*` event types (rebuild_started, rebuild_stage, rebuild_task_started, rebuild_task_completed, rebuild_failed, rebuild_complete). Clean separation from agent run events -- do NOT reuse existing run_started/node_started types.

### Rebuild Controls
- **D-03:** Cancel + retry + history. User can cancel a running rebuild, re-trigger from scratch after failure, and view past rebuild attempts with results/metrics.
- **D-04:** One rebuild at a time. Reject new rebuild if one is already running. Matches single-process uvicorn constraint.
- **D-05:** Rebuild history needs a `rebuilds` table in SQLite (or equivalent persistence).

### Frontend Panel Design
- **D-06:** When a rebuild is active, the right-side agent activity panel switches to show rebuild progress instead. No layout changes -- reuse the existing panel slot.
- **D-07:** TopBar button to trigger rebuild. Add a "Rebuild Ship" button in the existing TopBar, always visible.

### Error Handling
- **D-08:** On failure: show error + detailed task-level log leading up to failure. User can diagnose before retrying.
- **D-09:** Keep partial output on failure. Do not clean up the output directory -- leave it for debugging.

### Claude's Discretion
- Event priority levels (P0/P1/P2) for rebuild events -- Claude picks based on existing EventBus patterns
- Exact rebuild_* event data payloads
- SQLite schema for rebuilds table
- How to handle server shutdown during active rebuild (graceful cancel)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Rebuild Script
- `scripts/ship_rebuild.py` -- The current rebuild pipeline. Contains `run_rebuild()` function with ~8 print() calls to convert to EventBus emissions. Also contains `_seed_output_from_source()` which Phase 18 will remove.

### Server Patterns
- `server/main.py` lines 335-450 -- `submit_instruction()` endpoint. The exact pattern to follow for POST /rebuild (asyncio.create_task, EventBus emit, runs dict tracking).
- `server/main.py` lines 527+ -- POST /instruction/{run_id} for follow-up instructions (persistent loop pattern).

### EventBus
- `agent/events.py` -- EventBus class with P0/P1/P2 priority routing. New rebuild_* event types will be added here.

### DAG Scheduler
- `agent/orchestrator/scheduler.py` -- DAGScheduler accepts `event_bus` parameter. Currently ship_rebuild.py passes None -- needs to pass the server's EventBus.

### Frontend WebSocket
- `web/src/` -- Zustand wsStore subscribes to WebSocket events by type. New rebuild_* event handlers needed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `submit_instruction()` pattern: asyncio.create_task + EventBus emit + runs dict tracking -- exact blueprint for POST /rebuild
- `EventBus` with P0/P1/P2 priorities -- ready for rebuild events
- `DAGScheduler` already accepts `event_bus` parameter -- just needs wiring
- `/runs/{run_id}/cancel` endpoint -- pattern for rebuild cancellation
- `wsStore` in Zustand -- event subscription by type, ready for rebuild_* events
- `AgentPanel` component -- will be conditionally replaced by RebuildPanel when rebuild is active

### Established Patterns
- Background task lifecycle: `asyncio.create_task(execute())` with try/except and status tracking in `runs` dict
- Event emission: `await event_bus.emit(Event(project_id=..., run_id=..., type=..., node=..., data=...))`
- Cancel pattern: `task.cancel()` + CancelledError handling + status update to "cancelled"
- SQLite persistence: Pydantic model + SessionStore Protocol method + SQLiteSessionStore implementation

### Integration Points
- `server/main.py` -- New POST /rebuild endpoint, new GET /rebuilds endpoint for history
- `agent/events.py` -- New rebuild_* event type constants
- `scripts/ship_rebuild.py` -- `run_rebuild()` accepts optional `event_bus` parameter, falls back to print() for CLI
- `store/models.py` -- New Rebuild Pydantic model
- `store/protocol.py` -- New rebuild CRUD methods on SessionStore Protocol
- `store/sqlite.py` -- SQLite implementation of rebuild persistence
- `web/src/components/` -- New RebuildPanel component, TopBar button addition

</code_context>

<specifics>
## Specific Ideas

- User described the integration as: "A 'Rebuild Ship' action in the frontend that hits POST /rebuild with config (repo URL, concurrency, etc.), server calls run_rebuild() as background task, progress streams to frontend over existing WebSocket"
- Script stays as-is for CLI usage -- server just calls the same run_rebuild() function
- The changes should be small: one new endpoint, swap print() for event_bus.emit(), one new frontend panel

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 17-persistent-loop-infrastructure*
*Context gathered: 2026-03-30*
