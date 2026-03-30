# Architecture Patterns: Ship Rebuild End-to-End (v1.3)

**Domain:** Autonomous coding agent -- persistent loop, from-scratch generation, intervention logging, comparative analysis
**Researched:** 2026-03-30

## Recommended Architecture

Extend the existing server/agent/store layered architecture. No new layers needed.

### New Component Boundaries

| Component | Responsibility | Location | Communicates With |
|---|---|---|---|
| RebuildController | POST /rebuild endpoint, rebuild lifecycle management | `server/main.py` (new routes) | EventBus, RebuildService |
| RebuildService | Wraps `run_rebuild()` with EventBus phase tracking | `agent/orchestrator/rebuild_service.py` (new) | EventBus, ship_rebuild, InterventionStore |
| InterventionStore | CRUD for intervention records | `store/sqlite.py` (extend) | SQLite |
| AnalysisGenerator | Generates 7-section comparative analysis from data | `agent/orchestrator/analysis.py` (new) | ModelRouter, InterventionStore, TokenUsage |
| RebuildPanel | Frontend rebuild progress visualization | `web/src/components/rebuild/` (new) | Zustand rebuild slice, WebSocket |

### Data Flow

```
Frontend                    Server                         Agent/Orchestrator
--------                    ------                         ------------------
POST /rebuild          ->   RebuildController
  or WS "rebuild"      ->     creates background task  ->  RebuildService
                                                            |
                              EventBus  <-  phase events  <-+
                                |                           |
WS event stream        <-   ConnectionManager              clone_repo()
  rebuild_phase_changed                                    analyze_codebase()
  task_started/completed                                   run_pipeline()
  progress_update                                          DAGScheduler.run()
  intervention_needed                                       |
                                                           generate_analysis()
POST /rebuild/{id}/    ->   RebuildController               |
  intervention              InterventionStore  <--------->  AnalysisGenerator
                                                            |
GET /rebuild/{id}/     ->   RebuildController               v
  analysis                  reads from filesystem      analysis.md on disk
```

## Patterns to Follow

### Pattern 1: Phase-Tracking Wrapper

**What:** Wrap each rebuild stage in a context manager that emits EventBus events on entry/exit/error.

**When:** Every rebuild phase transition (clone, analyze, plan, execute, build, deploy).

**Example:**
```python
@asynccontextmanager
async def rebuild_phase(event_bus: EventBus, rebuild_id: str, phase: str, project_id: str):
    """Emit phase events and handle errors for a rebuild stage."""
    await event_bus.emit(Event(
        project_id=project_id, run_id=rebuild_id,
        type="rebuild_phase_changed",
        data={"phase": phase, "status": "started"},
    ))
    try:
        yield
    except Exception as e:
        await event_bus.emit(Event(
            project_id=project_id, run_id=rebuild_id,
            type="rebuild_failed",
            data={"phase": phase, "error": str(e)},
        ))
        raise
    else:
        await event_bus.emit(Event(
            project_id=project_id, run_id=rebuild_id,
            type="rebuild_phase_changed",
            data={"phase": phase, "status": "completed"},
        ))
```

**Why:** Clean separation of phase tracking from business logic. The rebuild pipeline code stays focused on its job while events flow automatically.

### Pattern 2: Single Active Rebuild Guard

**What:** Only one rebuild can run at a time. Return 409 Conflict if a rebuild is already in progress.

**When:** POST /rebuild or WS "rebuild" action.

**Example:**
```python
_active_rebuild: str | None = None

@app.post("/rebuild")
async def start_rebuild(req: RebuildRequest):
    global _active_rebuild
    if _active_rebuild is not None:
        raise HTTPException(409, f"Rebuild {_active_rebuild} already running")
    rebuild_id = _new_id()
    _active_rebuild = rebuild_id
    asyncio.create_task(_run_and_clear(rebuild_id, req))
    return {"rebuild_id": rebuild_id}
```

**Why:** The agent uses significant resources (LLM calls, git worktrees, disk I/O). Running two rebuilds concurrently would create resource contention and confusing event streams.

### Pattern 3: Intervention as Event + Record

**What:** Interventions are both real-time events (for the UI) and persistent records (for analysis).

**When:** Any human intervention during rebuild.

**Example:**
```python
async def log_intervention(store, event_bus, rebuild_id, project_id, intervention):
    # Persist
    await store.save_intervention(intervention)
    # Stream
    await event_bus.emit(Event(
        project_id=project_id, run_id=rebuild_id,
        type="intervention_logged",
        data=intervention.model_dump(),
    ))
```

**Why:** The UI needs to show interventions in real-time (EventBus), and the analysis generator needs to query them later (SQLite). Dual-write keeps both consumers happy.

### Pattern 4: Analysis as Post-Processing

**What:** Generate the comparative analysis as a post-processing step after the rebuild completes, not during it.

**When:** After `DAGScheduler.run()` returns and before `rebuild_completed` event.

**Example:**
```python
async def generate_analysis(router, store, rebuild_id, source_dir, output_dir):
    # Gather data
    interventions = await store.get_interventions(rebuild_id)
    task_results = await store.get_task_executions(rebuild_id)
    token_usage = await store.get_token_usage(rebuild_id)

    # Generate each section via LLM
    sections = []
    for section_name, data in section_inputs.items():
        content = await router.call(
            task_type="analysis",
            system=ANALYSIS_SYSTEM_PROMPT,
            user=f"Generate the {section_name} section:\n{json.dumps(data)}",
        )
        sections.append(f"## {section_name}\n\n{content}")

    analysis_md = "\n\n".join(sections)
    # Write to disk
    Path(f"{output_dir}/ANALYSIS.md").write_text(analysis_md)
    return analysis_md
```

**Why:** Analysis needs complete data. Running it mid-rebuild would produce incomplete results. The LLM calls for analysis are separate from the rebuild LLM calls and use the `general` tier (gpt-4o).

## Anti-Patterns to Avoid

### Anti-Pattern 1: Polling for Rebuild Status

**What:** Frontend polling `GET /rebuild/{id}` every N seconds.

**Why bad:** Wastes HTTP requests when WebSocket already provides real-time updates.

**Instead:** Use WebSocket `rebuild_phase_changed` events. Frontend subscribes to the rebuild's run_id and receives push updates.

### Anti-Pattern 2: Storing Analysis in SQLite

**What:** Putting the full Markdown analysis document in a SQLite column.

**Why bad:** Large text blobs in SQLite are inefficient to query. The analysis is read-once, not queried.

**Instead:** Write analysis to filesystem (`{output_dir}/ANALYSIS.md`). Store the file path in the `rebuild_runs` table. Serve via `GET /rebuild/{id}/analysis` which reads the file.

### Anti-Pattern 3: Separate WebSocket for Rebuild

**What:** Creating a new WebSocket endpoint `/ws/rebuild` separate from the existing `/ws`.

**Why bad:** The existing WebSocket infrastructure (ConnectionManager, subscription model, reconnect/replay) works perfectly. A separate endpoint duplicates all that logic.

**Instead:** Use the existing `/ws` with rebuild events flowing through the same EventBus. The client subscribes to the rebuild's run_id just like any other run.

### Anti-Pattern 4: Complex State Machine for Rebuild Phases

**What:** Building a formal state machine (like the EditRecord approval FSM) for rebuild phase transitions.

**Why bad:** Rebuild phases are strictly linear (clone -> analyze -> plan -> execute -> build -> deploy). A state machine adds complexity for a flow that never branches or backtracks.

**Instead:** Simple sequential execution with phase tracking via the context manager pattern above.

## Scalability Considerations

Not applicable for v1.3 -- this is a single-user demo tool running one rebuild at a time. The architecture choices (single active rebuild, asyncio.create_task, in-process EventBus) are correct for this scale and would need rethinking only if Shipyard becomes multi-tenant.

## Sources

- Project codebase analysis: `server/main.py`, `agent/events.py`, `server/websocket.py`, `agent/orchestrator/scheduler.py`, `scripts/ship_rebuild.py`
- FastAPI background tasks documentation
- Existing project architectural patterns (v1.0-v1.2)

---
*Architecture patterns for: Shipyard v1.3 Ship Rebuild End-to-End*
*Researched: 2026-03-30*
