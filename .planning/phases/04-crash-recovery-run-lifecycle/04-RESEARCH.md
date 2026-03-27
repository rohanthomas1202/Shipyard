# Phase 4: Crash Recovery & Run Lifecycle - Research

**Researched:** 2026-03-26
**Domain:** LangGraph checkpointing, async cancellation, LangSmith tracing
**Confidence:** HIGH

## Summary

This phase adds three capabilities to the Shipyard agent: (1) persistent checkpointing so runs survive server crashes and can resume from the last completed node, (2) graceful cancellation with clean state rollback, and (3) LangSmith tracing with shared trace links.

The LangGraph ecosystem provides `langgraph-checkpoint-sqlite` with `AsyncSqliteSaver` as a drop-in checkpointer. The project already uses `aiosqlite` and SQLite throughout, so this is a natural fit. Checkpointing is wired into `graph.compile(checkpointer=...)` and requires a `thread_id` in the config's `configurable` dict. For cancellation, the pattern is to set a cancel flag checked between nodes and cancel the running asyncio task. LangSmith tracing is already partially configured via env vars; the remaining work is capturing run IDs and generating shared trace links via `langsmith.Client.share_run()`.

**Primary recommendation:** Wire `AsyncSqliteSaver` into `build_graph()`, use `run_id` as `thread_id`, add a cancel endpoint that sets a flag + cancels the task, and use `langsmith.Client.share_run()` for shared trace links.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicitly locked -- all implementation choices at Claude's discretion per CONTEXT.md.

### Claude's Discretion
All implementation choices are at Claude's discretion -- pure infrastructure phase.

Key constraints:
- LangGraph checkpointing via AsyncSqliteSaver (or MemorySaver if SQLite checkpointer unavailable)
- Cancellation: set a cancel flag, check between nodes, roll back partial work
- LangSmith: env vars already configured (LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT)
- Need 2 shared trace links: one normal run, one error recovery path

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-04 | LangGraph uses AsyncSqliteSaver for persistent checkpointing, enabling crash recovery and run resumption | AsyncSqliteSaver verified available (v3.0.3), compile(checkpointer=...) API confirmed, thread_id resume pattern documented |
| LIFE-01 | User can gracefully cancel a running agent mid-execution with clean state rollback (no partial writes, no corrupted files) | asyncio.Task.cancel() for the running task, cancel flag in runs dict checked between nodes, existing _rollback() pattern in validator for file restoration |
| LIFE-03 | LangSmith tracing captures complete structured traces with at least two shared trace links showing different execution paths | langsmith.Client.share_run(run_id) confirmed, env vars already configured, LangGraph auto-traces when LANGCHAIN_TRACING_V2=true |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph-checkpoint-sqlite | 3.0.3 | Async SQLite checkpointer for LangGraph | Official LangGraph checkpointer for SQLite; already installed and verified |
| langsmith | 0.7.22 | Tracing client with share_run API | Already installed as langgraph transitive dep; provides share_run() for public trace links |
| aiosqlite | 0.22.1 | Async SQLite driver (already in use) | Required by AsyncSqliteSaver; already a project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langgraph-checkpoint | 4.0.1 | Base checkpoint abstractions | Already installed as langgraph dep; provides Checkpointer protocol |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AsyncSqliteSaver | MemorySaver | MemorySaver loses state on crash -- defeats the purpose; only for tests |
| AsyncSqliteSaver | PostgresSaver | Better for production but project is committed to SQLite |

**Installation:**
```bash
pip install langgraph-checkpoint-sqlite
```

Already installed (v3.0.3). Add to pyproject.toml dependencies:
```
"langgraph-checkpoint-sqlite>=3.0.0",
```

## Architecture Patterns

### Pattern 1: Checkpointer Wiring

**What:** Pass `AsyncSqliteSaver` to `graph.compile(checkpointer=...)` and include `thread_id` in every `ainvoke()` config.

**When to use:** Every graph invocation -- initial runs and resumptions.

**Current code** (`build_graph()`):
```python
def build_graph():
    graph = StateGraph(AgentState)
    _build_graph_nodes(graph)
    return graph.compile()  # No checkpointer
```

**Target pattern:**
```python
def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)
    _build_graph_nodes(graph)
    return graph.compile(checkpointer=checkpointer)
```

**Server-side wiring** (lifespan):
```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing setup ...
    async with AsyncSqliteSaver.from_conn_string("shipyard_checkpoints.db") as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer=checkpointer)
        # ... rest of lifespan ...
```

**Config for ainvoke:**
```python
config = {
    "configurable": {
        "thread_id": run_id,  # Use run_id as thread_id
        "store": store,
        "router": router,
        # ... other configurable items ...
    }
}
result = await graph.ainvoke(initial_state, config=config)
```

### Pattern 2: Crash Recovery / Resume

**What:** On server restart, detect interrupted runs and re-invoke the graph with the same `thread_id`. LangGraph automatically resumes from the last completed checkpoint.

**How it works:**
1. Server starts, queries SQLite for runs with `status='running'`
2. For each interrupted run, calls `graph.ainvoke(None, config={"configurable": {"thread_id": run_id}})` -- passing `None` as input tells LangGraph to resume from checkpoint
3. LangGraph loads the last checkpoint for that thread_id and continues from the next node

**Key detail:** When a node fails mid-execution, LangGraph stores checkpoint writes from any other nodes that completed at that superstep, so successful work is not re-run on resume.

### Pattern 3: Graceful Cancellation

**What:** Cancel a running agent via API endpoint. Set a flag, cancel the asyncio task, roll back any in-progress edits.

**Implementation approach:**
1. Store the asyncio.Task reference in the `runs` dict alongside status
2. Add a `POST /runs/{run_id}/cancel` endpoint
3. On cancel: set `runs[run_id]["status"] = "cancelling"`, then `task.cancel()`
4. In the `execute()` coroutine, catch `asyncio.CancelledError`, set status to "cancelled"
5. Add a cancel-check function called at node boundaries (between nodes) that raises if cancelled

**File rollback on cancel:**
- The existing `_rollback()` pattern in `validator.py` writes snapshots before edits
- If cancelled mid-edit, the snapshot in `edit_history` can restore the file
- The `CancelledError` handler should iterate `edit_history` and rollback any entries with snapshots that have no corresponding successful validation

### Pattern 4: LangSmith Shared Trace Links

**What:** After a run completes, use `langsmith.Client.share_run()` to generate a public URL for the trace.

**API:**
```python
from langsmith import Client

client = Client()  # Uses LANGCHAIN_API_KEY from env

# After run completes, get the LangSmith run ID and share it
shared_url = client.share_run(langsmith_run_id)
# Returns a public URL like: https://smith.langchain.com/public/...
```

**Getting the LangSmith run ID:**
- When `LANGCHAIN_TRACING_V2=true`, LangGraph automatically creates traces
- The trace run_id can be obtained via callback: `langchain.callbacks.tracing_v2_enabled` context manager provides `cb.get_run_url()`
- Alternatively, use `langsmith.Client.list_runs(project_name=..., filter=...)` to find the run after completion

**Storing trace links:**
- Add `trace_url: str | None` field to the `Run` model in `store/models.py`
- After graph execution completes, share the run and store the URL
- Return trace_url in status API responses

### Recommended Project Structure Changes
```
agent/
  graph.py          # Add checkpointer param to build_graph()
  state.py          # No changes needed (TypedDict is checkpoint-compatible)
  tracing.py        # Enhance with LangSmith shared link generation
server/
  main.py           # Add checkpointer lifecycle, cancel endpoint, resume on restart
store/
  models.py         # Add trace_url field to Run model
  sqlite.py         # Add query for interrupted runs
```

### Anti-Patterns to Avoid
- **Separate checkpoint DB from app DB:** Use a DIFFERENT SQLite file for checkpoints (`shipyard_checkpoints.db`) -- the checkpoint schema is managed by LangGraph, not our migrations. Mixing them causes schema conflicts.
- **Don't store large blobs in AgentState:** The checkpointer serializes the entire state at each node boundary. If `file_buffer` contains many large files, checkpoints will be huge. Consider clearing file_buffer of files no longer needed.
- **Don't use MemorySaver in production:** It defeats the purpose of crash recovery. Only use in tests.
- **Don't poll for cancellation inside nodes:** Check at node boundaries (between nodes), not inside nodes. Nodes should complete atomically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Checkpoint persistence | Custom state serialization to SQLite | `AsyncSqliteSaver` from `langgraph-checkpoint-sqlite` | Handles serialization, versioning, channel management automatically |
| Trace sharing | Manual LangSmith API calls | `langsmith.Client.share_run()` | Handles token generation, public URL creation, permissions |
| Graph resume logic | Custom "find last node, re-run from there" | LangGraph's built-in resume via `thread_id` | Checkpointer handles superstep tracking, partial writes, channel restoration |
| Async task cancellation | Signal-based or threading cancellation | `asyncio.Task.cancel()` + `CancelledError` handling | Native to Python's async model, cooperative cancellation is clean |

## Common Pitfalls

### Pitfall 1: AsyncSqliteSaver requires async context manager
**What goes wrong:** Creating `AsyncSqliteSaver.from_conn_string()` without `async with` -- it's an async generator.
**Why it happens:** Easy to forget it needs context management.
**How to avoid:** Always use `async with AsyncSqliteSaver.from_conn_string(path) as checkpointer:` inside the lifespan.
**Warning signs:** `TypeError: 'async_generator' object is not callable`

### Pitfall 2: Missing thread_id causes no checkpointing
**What goes wrong:** If `thread_id` is not in `config["configurable"]`, the checkpointer silently does nothing.
**Why it happens:** The thread_id is what keys the checkpoint storage.
**How to avoid:** Always include `"thread_id": run_id` in the configurable dict.
**Warning signs:** Runs don't survive restarts despite checkpointer being set up.

### Pitfall 3: Checkpoint state must be serializable
**What goes wrong:** If AgentState contains non-serializable objects (open file handles, asyncio locks, etc.), checkpointing fails.
**Why it happens:** The checkpointer serializes the entire state dict.
**How to avoid:** AgentState currently uses only primitives, lists, dicts, strings -- this is safe. Keep it that way.
**Warning signs:** Serialization errors at node boundaries.

### Pitfall 4: Task cancellation during file write
**What goes wrong:** If `asyncio.Task.cancel()` fires while a file write is in progress, the file could be corrupted.
**Why it happens:** CancelledError is raised at the next await point, which might be inside a file operation.
**How to avoid:** Use `asyncio.shield()` around critical file write operations, or check cancellation only at node boundaries (not mid-node). The LangGraph node model naturally provides this boundary -- nodes run to completion between checkpoints.
**Warning signs:** Partial file writes after cancellation.

### Pitfall 5: LangSmith run ID vs Shipyard run ID
**What goes wrong:** Confusing the Shipyard run_id (e.g., "a1b2c3d4") with the LangSmith trace run UUID.
**Why it happens:** Both are called "run_id" in different contexts.
**How to avoid:** LangSmith's run_id comes from the tracing callback or by querying the LangSmith API. Tag Shipyard run_id as metadata so you can find the LangSmith trace later.
**Warning signs:** `share_run()` returns 404 because wrong ID was passed.

### Pitfall 6: Checkpoint DB file contention with app DB
**What goes wrong:** Using the same SQLite file for checkpoints and app data causes schema conflicts.
**Why it happens:** LangGraph manages its own table schema in the checkpoint DB.
**How to avoid:** Use a separate file: `shipyard_checkpoints.db` vs `shipyard.db`.
**Warning signs:** Table schema errors, migration conflicts.

## Code Examples

### AsyncSqliteSaver Setup (verified import)
```python
# Verified: this import works with langgraph-checkpoint-sqlite 3.0.3
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async with AsyncSqliteSaver.from_conn_string("shipyard_checkpoints.db") as checkpointer:
    await checkpointer.setup()
    graph = build_graph(checkpointer=checkpointer)
```

### LangSmith share_run (verified signature)
```python
from langsmith import Client

# Client.share_run signature (verified):
#   share_run(self, run_id: ID_TYPE, *, share_id: Optional[ID_TYPE] = None) -> str
# Client.read_run_shared_link signature (verified):
#   read_run_shared_link(self, run_id: ID_TYPE) -> Optional[str]

client = Client()
shared_url = client.share_run(langsmith_run_id)  # Returns public URL string
```

### Cancellation Pattern
```python
# In server/main.py

@app.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run_entry = runs[run_id]
    if run_entry["status"] not in ("running",):
        raise HTTPException(status_code=409, detail=f"Cannot cancel run in state: {run_entry['status']}")

    run_entry["status"] = "cancelling"
    task = run_entry.get("task")
    if task and not task.done():
        task.cancel()
    return {"run_id": run_id, "status": "cancelling"}
```

### Resume on Restart
```python
# In server/main.py lifespan, after checkpointer is ready

async def _resume_interrupted_runs():
    """Find runs marked 'running' in DB (from before crash) and resume them."""
    store = app.state.store
    interrupted = await store.list_runs_by_status("running")
    for run in interrupted:
        asyncio.create_task(_resume_from_checkpoint(run.id))

async def _resume_from_checkpoint(run_id: str):
    """Resume a run from its last checkpoint."""
    graph = app.state.graph
    config = {"configurable": {"thread_id": run_id, ...}}
    # Passing None as input tells LangGraph to resume from checkpoint
    result = await graph.ainvoke(None, config=config)
    # Update run status based on result
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | pyproject.toml (no [tool.pytest] section yet -- uses defaults) |
| Quick run command | `.venv311/bin/pytest tests/test_graph.py -x -q` |
| Full suite command | `.venv311/bin/pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-04 | Graph compiles with AsyncSqliteSaver checkpointer | unit | `.venv311/bin/pytest tests/test_graph.py::test_graph_compiles_with_checkpointer -x` | Wave 0 |
| INFRA-04 | Checkpoint is written after node execution | integration | `.venv311/bin/pytest tests/test_checkpoint.py::test_checkpoint_written -x` | Wave 0 |
| INFRA-04 | Graph resumes from checkpoint after simulated crash | integration | `.venv311/bin/pytest tests/test_checkpoint.py::test_resume_from_checkpoint -x` | Wave 0 |
| LIFE-01 | Cancel endpoint sets status and cancels task | unit | `.venv311/bin/pytest tests/test_server.py::test_cancel_run -x` | Wave 0 |
| LIFE-01 | Cancelled run rolls back in-progress edits | integration | `.venv311/bin/pytest tests/test_cancel.py::test_cancel_rollback -x` | Wave 0 |
| LIFE-03 | LangSmith trace link is generated after run | unit | `.venv311/bin/pytest tests/test_tracing.py::test_share_trace_link -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv311/bin/pytest tests/test_graph.py tests/test_server.py -x -q`
- **Per wave merge:** `.venv311/bin/pytest tests/ -x -q`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_checkpoint.py` -- covers INFRA-04 (checkpoint write + resume)
- [ ] `tests/test_cancel.py` -- covers LIFE-01 (cancel + rollback)
- [ ] `tests/test_tracing.py` -- covers LIFE-03 (shared trace link generation)
- [ ] Update `tests/test_graph.py` -- add test_graph_compiles_with_checkpointer
- [ ] Update `tests/test_server.py` -- add test_cancel_run endpoint test

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `langgraph.checkpoint.sqlite` (built-in) | `langgraph-checkpoint-sqlite` (separate package) | LangGraph v0.2 (2024) | Must install separate package |
| `SqliteSaver` (sync) | `AsyncSqliteSaver` (async) | langgraph-checkpoint-sqlite 2.x | Required for async graph execution with ainvoke |
| Manual trace URL construction | `langsmith.Client.share_run()` | langsmith 0.1+ | Returns public shareable URL |

## Open Questions

1. **Checkpoint DB size management**
   - What we know: Every node boundary writes a full state snapshot to SQLite
   - What's unclear: How fast will checkpoint DB grow? Is cleanup needed?
   - Recommendation: Add a cleanup step that deletes checkpoints for completed runs (after extracting trace links). Not urgent for v1.

2. **LangSmith run_id retrieval**
   - What we know: LangGraph auto-traces when env vars set. `share_run()` needs the LangSmith UUID.
   - What's unclear: Exact mechanism to get the LangSmith run UUID from within a LangGraph ainvoke call.
   - Recommendation: Use `langchain.callbacks.tracing_v2_enabled` context manager or tag runs with Shipyard run_id metadata and query LangSmith API post-execution. Test both approaches.

3. **File buffer checkpoint bloat**
   - What we know: `file_buffer` in AgentState stores full file contents for all read files.
   - What's unclear: Whether this causes unacceptable checkpoint sizes.
   - Recommendation: Monitor checkpoint DB size during testing. If large, consider clearing file_buffer entries that are no longer needed at each checkpoint boundary.

## Sources

### Primary (HIGH confidence)
- langgraph-checkpoint-sqlite 3.0.3 -- verified installed, AsyncSqliteSaver import confirmed
- langsmith 0.7.22 -- verified installed, share_run() signature confirmed via inspection
- LangGraph StateGraph.compile() -- checkpointer parameter confirmed via signature inspection
- AsyncSqliteSaver.from_conn_string() -- async context manager pattern confirmed

### Secondary (MEDIUM confidence)
- [LangGraph checkpoint blog](https://blog.langchain.com/langgraph-v0-2/) -- separate package architecture confirmed
- [LangSmith trace API docs](https://docs.langchain.com/langsmith/trace-with-api) -- tracing_v2_enabled callback pattern
- [LangGraph forum](https://forum.langchain.com/t/can-we-resume-from-the-checkpoint-and-continue-running-at-the-interruption-point-instead-of-starting-from-the-first-node/1240) -- resume from checkpoint pattern with thread_id

### Tertiary (LOW confidence)
- Checkpoint resume with `None` input -- referenced in multiple sources but exact behavior for custom StateGraph with TypedDict state needs testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified installed, imports confirmed
- Architecture: HIGH -- compile(checkpointer=...) and thread_id pattern verified via code inspection
- Pitfalls: MEDIUM -- based on documentation and common patterns, some need runtime verification
- LangSmith integration: MEDIUM -- share_run() verified, but getting LangSmith run UUID from ainvoke needs testing

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable infrastructure, 30-day window)
