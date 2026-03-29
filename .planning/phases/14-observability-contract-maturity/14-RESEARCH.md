# Phase 14: Observability + Contract Maturity - Research

**Researched:** 2026-03-29
**Domain:** Structured logging, progress metrics, decision tracing, contract backward compatibility
**Confidence:** HIGH

## Summary

Phase 14 extends four existing systems -- TraceLogger, EventBus, ContractStore, and the AgentPanel frontend -- rather than building new infrastructure. The work decomposes into four clean workstreams: (1) extend TraceLogger with agent_id/task_id/severity fields and unified format, (2) add progress metrics WebSocket events and a collapsible header in AgentPanel, (3) build decision trace capture on task failure with module x error-type heatmap aggregation, and (4) add contract diff/compatibility checking to ContractStore with migration doc generation.

All four workstreams build on well-established patterns in the codebase. The EventBus already has P0/P1/P2 priority routing and WebSocket streaming. The Zustand wsStore already handles event type routing. The ContractStore is a simple file-based CRUD that needs diff methods added. No new dependencies are required -- Python's `difflib` handles text diffing, and the DAGPersistence SQLite tables already store task execution data needed for metrics.

**Primary recommendation:** Build backend data models and logic first (TraceLogger extension, contract diffing, metrics computation), then wire through EventBus/WebSocket, then add frontend components last.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Extend existing TraceLogger with unified format -- add `agent_id`, `task_id`, `severity` (debug/info/warn/error), and structured data fields to the existing file-based JSON trace system. No new dependencies or persistence layers.
- **D-02:** Logs filterable by agent, task, and severity. TraceLogger already has `run_id` and `node` -- extend with DAG-level identifiers.
- **D-03:** Decision trace depth: error + LLM context -- capture error message, LLM prompt/response, files read, and final state for failed tasks. Not full step-by-step, not error-only.
- **D-04:** Failure heatmap aggregated by module x error type -- two-dimensional: module from Analyzer's module map crossed with error category (syntax, test, contract, structural). Aligns with Phase 15's A/B/C/D failure classification.
- **D-05:** Extend the existing agent activity stream panel -- add a collapsible metrics header showing DAG progress bar, task completion counts, DAG coverage percentage, and CI pass rate. No new panel or tab.
- **D-06:** Metrics pushed via WebSocket -- extend existing WS infrastructure with new event types for progress updates. Frontend subscribes via existing Zustand store.
- **D-07:** Schema diffing approach -- compare old vs new contract file content to detect removed fields, changed types, removed endpoints. Works for all contract types (.sql, .yaml, .ts, .json).
- **D-08:** Migration strategy as markdown document -- when breaking changes are detected, generate a `migration.md` file alongside the contract change listing what broke, why, and step-by-step migration instructions. Git-tracked, human-readable.

### Claude's Discretion
- TraceLogger internal refactoring to support new fields
- Specific diff algorithm for each contract type (text diff vs structural diff)
- Progress metrics WebSocket event format and update frequency
- Failure heatmap data structure and aggregation logic
- How to detect "old" vs "new" contract versions (git diff, snapshot, etc.)
- Activity stream header component design details

### Deferred Ideas (OUT OF SCOPE)
- Failure classification system A/B/C/D (Phase 15 -- heatmap error categories align with this)
- Module ownership model (Phase 15)
- DAG visualization graph/tree view in frontend (could be a future enhancement)
- Alert/notification system for CI failures
- Historical metrics trending across runs
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBSV-01 | Structured logging with unified format across all agents | TraceLogger extension with agent_id, task_id, severity fields. Unified log() method signature. |
| OBSV-02 | Progress metrics dashboard (tasks completed, DAG coverage %, CI pass rate) | DAGPersistence already tracks completed/failed/total counts. Extend with WebSocket progress events and collapsible AgentPanel header. |
| OBSV-03 | Task decision traces and failure heatmap for debugging | Decision trace model captures error + LLM context. Heatmap aggregates by ModuleInfo.name x error category from task_executions. |
| CNTR-03 | Contract changes include backward compatibility checks and migration strategy | ContractStore.check_compatibility() using difflib. Migration doc generation with template. |
</phase_requirements>

## Standard Stack

### Core (already in project -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `difflib` | stdlib | Text-based contract diffing | Built-in, no dependency. `unified_diff` and `SequenceMatcher` cover all contract types |
| `aiosqlite` | >=0.20.0 | Query task_executions for metrics/heatmap | Already used by DAGPersistence |
| `pydantic` | transitive via FastAPI | Data models for traces, metrics, heatmap | Already the project standard for all models |
| Zustand | via existing wsStore | Frontend state for progress metrics | Already wired for WS event handling |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` | stdlib | Structured trace file output | TraceLogger already uses this |
| `pathlib` | stdlib | Contract file operations | ContractStore already uses this |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| difflib (text diff) | deepdiff (structural) | deepdiff gives richer object diffs but adds a dependency. Text diff is simpler and works for all contract types. Use text diff per D-07. |
| Custom metrics computation | prometheus_client | Overkill for single-process SQLite app. Direct SQL queries on task_executions are simpler. |
| structlog | stdlib logging + TraceLogger | structlog was considered in Phase 01 research but TraceLogger is committed. Extend it. |

**Installation:** No new packages needed.

## Architecture Patterns

### Recommended Changes to Existing Structure
```
agent/
  tracing.py           # EXTEND: add agent_id, task_id, severity to log()
  events.py            # EXTEND: add progress event types to _P0_TYPES
  orchestrator/
    contracts.py        # EXTEND: add check_compatibility(), diff_contract()
    events.py           # EXTEND: add PROGRESS_UPDATE, DECISION_TRACE event types
    models.py           # EXTEND: add DecisionTrace, FailureHeatmapEntry models
    metrics.py          # NEW: compute_progress_metrics(), aggregate_heatmap()
    migration.py        # NEW: generate_migration_doc()
    scheduler.py        # EXTEND: emit progress events after task completion
server/
  main.py              # EXTEND: add /dag/{dag_id}/metrics endpoint
web/src/
  types/index.ts       # EXTEND: add ProgressMetrics, DecisionTrace interfaces
  stores/wsStore.ts    # EXTEND: add progressMetrics state slice
  context/WebSocketContext.tsx  # EXTEND: route progress_update events
  components/agent/
    AgentPanel.tsx      # EXTEND: add collapsible metrics header
    ProgressHeader.tsx  # NEW: collapsible DAG progress bar + metrics
    FailureHeatmap.tsx  # NEW: module x error type grid (minimal UI)
    DecisionTrace.tsx   # NEW: expandable trace view for failed tasks
```

### Pattern 1: TraceLogger Unified Format Extension
**What:** Extend the existing `log()` method to accept optional `agent_id`, `task_id`, and `severity` fields while keeping backward compatibility.
**When to use:** All agent node instrumentation calls.
**Example:**
```python
# Backward-compatible extension -- existing calls still work
class TraceLogger:
    def log(
        self,
        node: str,
        data: dict,
        *,
        agent_id: str | None = None,
        task_id: str | None = None,
        severity: Literal["debug", "info", "warn", "error"] = "info",
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "node": node,
            "agent_id": agent_id,
            "task_id": task_id,
            "severity": severity,
            "data": data,
        }
        self.entries.append(entry)
```

### Pattern 2: Progress Metrics via WebSocket Events
**What:** Scheduler emits a `progress_update` event after every task completion. Frontend renders it in a collapsible header.
**When to use:** After every task status transition in DAGScheduler.
**Example:**
```python
# In scheduler._run_task() after task completion/failure
async def _emit_progress(self) -> None:
    total = self._dag_run.total_tasks
    completed = len(self._completed)
    failed = len(self._failed)
    coverage = (completed / total * 100) if total > 0 else 0

    await self._emit("progress_update", data={
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "running_tasks": len(self._running),
        "coverage_pct": round(coverage, 1),
        "ci_pass_rate": round(completed / (completed + failed) * 100, 1) if (completed + failed) > 0 else 100.0,
    })
```

### Pattern 3: Contract Backward Compatibility Check
**What:** Before writing a contract, diff old vs new content and flag breaking changes.
**When to use:** ContractStore.write_contract() calls or as explicit check.
**Example:**
```python
import difflib

def check_compatibility(self, name: str, new_content: str) -> dict:
    """Compare old vs new contract content. Returns breaking changes."""
    old_content = self.read_contract(name)
    if old_content is None:
        return {"compatible": True, "changes": [], "breaking": []}

    diff = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"old/{name}",
        tofile=f"new/{name}",
    ))

    # Detect removals (lines starting with '-' that aren't header)
    removals = [l.rstrip() for l in diff if l.startswith('-') and not l.startswith('---')]
    additions = [l.rstrip() for l in diff if l.startswith('+') and not l.startswith('+++')]

    breaking = _detect_breaking_changes(name, removals, additions)
    return {
        "compatible": len(breaking) == 0,
        "diff": "".join(diff),
        "changes": removals + additions,
        "breaking": breaking,
    }
```

### Pattern 4: Decision Trace Capture
**What:** When a task fails, capture the LLM context and error state for debugging.
**When to use:** In scheduler._run_task() catch block.
**Example:**
```python
class DecisionTrace(BaseModel):
    task_id: str
    dag_id: str
    error_message: str
    error_category: Literal["syntax", "test", "contract", "structural"] = "structural"
    llm_prompt: str | None = None
    llm_response: str | None = None
    files_read: list[str] = Field(default_factory=list)
    final_state: dict = Field(default_factory=dict)
    module_name: str | None = None
    timestamp: datetime = Field(default_factory=_now)
```

### Anti-Patterns to Avoid
- **Creating a new persistence layer:** TraceLogger writes to files, DAGPersistence writes to SQLite. Don't add a third storage mechanism. Decision traces go into task_executions.result_summary.
- **Polling for metrics:** Use WebSocket push via existing EventBus, not REST polling from frontend.
- **Building complex UI for heatmap:** D-04 says data model matters more than UI. A simple HTML table/grid is sufficient.
- **Replacing TraceLogger:** D-01 explicitly says "extend, don't replace." Keep backward compatibility with existing log() calls.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text diffing | Custom diff algorithm | Python `difflib.unified_diff` | Handles all contract types (.sql, .yaml, .ts, .json) as text. Edge cases around whitespace, encoding. |
| Progress percentage | Manual counter tracking | Query DAGRun.completed_tasks / total_tasks | Already tracked by DAGPersistence on every status update |
| WebSocket event routing | New event dispatch system | Existing EventBus P0/P1/P2 routing | Progress events are P0 (immediate). Existing infrastructure handles delivery. |
| Migration doc formatting | Custom template engine | f-string/template with consistent markdown sections | Simple enough. Template: What Broke / Why / Migration Steps / Verification |

**Key insight:** This phase is 90% extension of existing systems. The only truly new code is contract diffing logic, decision trace model, and the ProgressHeader component.

## Common Pitfalls

### Pitfall 1: Breaking Existing TraceLogger Callers
**What goes wrong:** Changing the `log()` signature breaks existing node calls.
**Why it happens:** Adding required parameters to an established interface.
**How to avoid:** All new parameters MUST be keyword-only with defaults. `log(node, data)` must continue working unchanged.
**Warning signs:** Test failures in existing node tests after TraceLogger changes.

### Pitfall 2: WebSocket Event Type Collision
**What goes wrong:** New event type names collide with existing ones or aren't routed properly.
**Why it happens:** _P0_TYPES frozenset in events.py needs updating, WebSocketContext.tsx needs new handlers.
**How to avoid:** Add new event types (`progress_update`, `decision_trace`) to _P0_TYPES. Update WebSocketContext.tsx event routing. Check for name collisions.
**Warning signs:** Events emitted but not reaching frontend.

### Pitfall 3: Metrics Computation Race Conditions
**What goes wrong:** Progress metrics computed from stale DAGRun counters when multiple tasks complete simultaneously.
**Why it happens:** DAGScheduler runs tasks concurrently. completed_tasks counter updates are async.
**How to avoid:** Compute metrics from scheduler's in-memory sets (`self._completed`, `self._failed`) rather than querying SQLite during the same event loop iteration.
**Warning signs:** Progress percentages that jump backward or exceed 100%.

### Pitfall 4: Contract Diff False Positives
**What goes wrong:** Whitespace changes or comment additions flagged as breaking changes.
**Why it happens:** Naive line-by-line diff treats all removals as breaking.
**How to avoid:** Breaking change detection should look for structural indicators: removed SQL columns, removed YAML paths, removed TypeScript exports, removed JSON keys. Not just any line removal.
**Warning signs:** Every contract update flagged as breaking.

### Pitfall 5: Oversized Decision Traces
**What goes wrong:** Storing full LLM prompt/response in every trace bloats SQLite and trace files.
**Why it happens:** LLM prompts can be 10-50KB each.
**How to avoid:** Truncate LLM context to reasonable limits (first 2000 chars of prompt, first 2000 chars of response). Store full traces only in TraceLogger file output.
**Warning signs:** SQLite database growing rapidly. Slow queries on task_executions.

## Code Examples

### Extending EventBus P0 Types
```python
# agent/events.py -- add new event types
_P0_TYPES = frozenset({
    "approval", "error", "stop", "review",
    "run_started", "run_completed", "run_failed", "run_waiting", "run_cancelled",
    "task_started", "task_completed", "task_failed",
    "dag_started", "dag_completed", "dag_failed",
    "contract_update_requested",
    # Phase 14 additions
    "progress_update",
    "decision_trace",
})
```

### Extending Zustand Store for Progress Metrics
```typescript
// web/src/stores/wsStore.ts -- add progress metrics slice
interface ProgressMetrics {
  totalTasks: number
  completedTasks: number
  failedTasks: number
  runningTasks: number
  coveragePct: number
  ciPassRate: number
}

// Add to WSStore interface:
progressMetrics: ProgressMetrics | null
setProgressMetrics: (m: ProgressMetrics) => void
clearProgressMetrics: () => void
```

### WebSocketContext Progress Event Routing
```typescript
// web/src/context/WebSocketContext.tsx -- add handler
if (event.type === 'progress_update') {
  store.setProgressMetrics({
    totalTasks: Number(event.data.total_tasks),
    completedTasks: Number(event.data.completed_tasks),
    failedTasks: Number(event.data.failed_tasks),
    runningTasks: Number(event.data.running_tasks),
    coveragePct: Number(event.data.coverage_pct),
    ciPassRate: Number(event.data.ci_pass_rate),
  })
}
```

### Migration Doc Template
```python
MIGRATION_TEMPLATE = """# Migration: {contract_name}

**Generated:** {timestamp}
**Contract:** {contract_path}

## What Broke

{breaking_changes}

## Why

{explanation}

## Migration Steps

{steps}

## Verification

- [ ] All consuming agents updated
- [ ] Tests pass with new contract
- [ ] No runtime errors referencing old schema
"""
```

### Collapsible ProgressHeader Component Pattern
```typescript
// Follows frosted glassmorphic design system
function ProgressHeader() {
  const metrics = useWsStore((s) => s.progressMetrics)
  const [collapsed, setCollapsed] = useState(false)

  if (!metrics) return null

  return (
    <div
      className="px-4 py-2 cursor-pointer"
      style={{ borderBottom: '1px solid var(--color-border)' }}
      onClick={() => setCollapsed(!collapsed)}
    >
      {/* Always visible: progress bar + summary */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${metrics.coveragePct}%`,
              background: 'var(--color-primary)',
            }}
          />
        </div>
        <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
          {metrics.completedTasks}/{metrics.totalTasks}
        </span>
      </div>
      {/* Expanded details */}
      {!collapsed && (
        <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
          {/* coverage %, CI pass rate, failed count */}
        </div>
      )}
    </div>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| TraceLogger with run_id + node only | Extended with agent_id, task_id, severity | Phase 14 | Enables filtering by agent/task/severity |
| ContractStore write-only | Write with compatibility check | Phase 14 | Breaking changes detected before write |
| No progress visibility | WebSocket-pushed metrics | Phase 14 | Real-time DAG progress in UI |
| Error messages only | Decision traces with LLM context | Phase 14 | Debuggable failure traces |

## Open Questions

1. **CI Pass Rate Data Source**
   - What we know: DAGPersistence tracks completed/failed task counts. The "CI pass rate" metric is defined as completed / (completed + failed).
   - What's unclear: Should this track actual CI/test results per task, or is the task completion ratio sufficient?
   - Recommendation: Use task completion ratio for now. Phase 15 adds VALD-01 (CI validation after every task) -- CI pass rate can be enriched then.

2. **Old Contract Version Detection**
   - What we know: Contracts are git-tracked (Phase 12 D-04/D-05). ContractStore.read_contract() returns current file content.
   - What's unclear: Should we compare against git HEAD version or against the last-read snapshot?
   - Recommendation: Compare against current file on disk (the "old" version) before write_contract() overwrites it. Simple, no git dependency needed.

3. **Decision Trace Storage Location**
   - What we know: task_executions table has result_summary (JSON dict) and error_message fields.
   - What's unclear: Should decision traces go into result_summary or a new column?
   - Recommendation: Store in result_summary dict with a `decision_trace` key. Avoids schema migration. Query with `json_extract()` if needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 + pytest-asyncio >=0.24.0 |
| Config file | pyproject.toml (test section) |
| Quick run command | `python -m pytest tests/test_contracts.py tests/test_tracing.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBSV-01 | TraceLogger accepts agent_id, task_id, severity; entries contain unified fields | unit | `python -m pytest tests/test_tracing.py -x -q` | Exists (extend) |
| OBSV-01 | Existing log() calls without new params still work | unit | `python -m pytest tests/test_tracing.py -x -q` | Exists (extend) |
| OBSV-02 | Scheduler emits progress_update events with correct metrics | unit | `python -m pytest tests/test_scheduler.py -x -q` | Exists (extend) |
| OBSV-02 | Progress event reaches Zustand store via WebSocket | integration | `python -m pytest tests/test_event_streaming_integration.py -x -q` | Exists (extend) |
| OBSV-03 | Failed tasks produce DecisionTrace with error + LLM context | unit | `python -m pytest tests/test_observability.py -x -q` | Wave 0 |
| OBSV-03 | Heatmap aggregation groups failures by module x error type | unit | `python -m pytest tests/test_observability.py -x -q` | Wave 0 |
| CNTR-03 | check_compatibility detects removed fields as breaking | unit | `python -m pytest tests/test_contracts.py -x -q` | Exists (extend) |
| CNTR-03 | check_compatibility allows additive changes as non-breaking | unit | `python -m pytest tests/test_contracts.py -x -q` | Exists (extend) |
| CNTR-03 | Migration doc generated with correct template sections | unit | `python -m pytest tests/test_contracts.py -x -q` | Exists (extend) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_contracts.py tests/test_tracing.py tests/test_scheduler.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_observability.py` -- covers OBSV-03 (decision traces + heatmap aggregation)
- [ ] Extend `tests/test_tracing.py` with agent_id/task_id/severity test cases
- [ ] Extend `tests/test_contracts.py` with backward compatibility and migration tests
- [ ] Extend `tests/test_scheduler.py` with progress_update event emission tests

## Sources

### Primary (HIGH confidence)
- `agent/tracing.py` -- TraceLogger current implementation (85 lines, simple JSON writer)
- `agent/events.py` -- EventBus with P0/P1/P2 routing, _P0_TYPES frozenset
- `agent/orchestrator/contracts.py` -- ContractStore CRUD (52 lines)
- `agent/orchestrator/scheduler.py` -- DAGScheduler with _emit() method
- `agent/orchestrator/persistence.py` -- DAGPersistence with task_executions table
- `agent/orchestrator/models.py` -- TaskExecution with error_message, result_summary fields
- `agent/analyzer/models.py` -- ModuleInfo, ModuleMap for heatmap module dimension
- `web/src/stores/wsStore.ts` -- Zustand store with event type routing
- `web/src/context/WebSocketContext.tsx` -- WS event bridge to Zustand
- `web/src/components/agent/AgentPanel.tsx` -- Activity stream panel to extend
- `store/models.py` -- Event Pydantic model
- `server/main.py` -- DAG REST endpoints (lines 1005-1155)

### Secondary (MEDIUM confidence)
- Python difflib documentation -- unified_diff and SequenceMatcher for contract diffing

### Tertiary (LOW confidence)
- None -- all findings verified against actual codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all extensions of existing code
- Architecture: HIGH -- patterns directly observed in codebase, clear extension points
- Pitfalls: HIGH -- derived from actual code structure (race conditions in scheduler, backward compat in TraceLogger)

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable -- extending existing patterns, no external dependency changes)
