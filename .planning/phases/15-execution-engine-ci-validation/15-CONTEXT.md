# Phase 15: Execution Engine + CI Validation - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the parallel execution engine that runs 5-15 agents concurrently on isolated git branches, enforces module ownership through validator rejection, classifies and retries failures with tiered budgets, and gates all merges to main through a local CI pipeline that keeps main always green.

</domain>

<decisions>
## Implementation Decisions

### Branch Isolation + PR Strategy
- **D-01:** Per-task branches with auto-merge — each task gets `agent/task-{id}` branch, CI runs on it, auto-merges to main on green. No accumulation branches.
- **D-02:** Local git branch + merge — no real GitHub PRs. Local branches provide the same isolation and merge semantics without network latency or API rate limits. Real PRs can be added later for human-reviewed milestones.
- **D-03:** Fail-and-requeue on merge conflicts — if two agents edit adjacent code, the later agent fails, gets requeued with updated base (main now has the conflicting changes merged). No LLM merge (unpredictable), no file locking (kills parallelism). DAG scheduler already handles requeueing.

### Context Packs + Module Ownership
- **D-04:** Hybrid context pack assembly — Planner picks primary files (knows task intent), Analyzer adds transitive dependencies from import graph (knows module structure). Neither alone is sufficient.
- **D-05:** Soft enforcement via validator — agent writes freely, validator checks the diff against the module ownership map, rejects unauthorized file changes. No filesystem sandboxing (complex for marginal benefit), no self-policing (LLMs unreliable at constraints). Simple, reliable, debuggable.

### Failure Classification + Retry Strategy
- **D-06:** Hybrid classification — rule-based regex patterns on error output first (fast, deterministic for common patterns like syntax errors, test failures), LLM fallback (gpt-4o-mini) for novel/ambiguous errors. Matches existing ModelRouter escalation pattern.
- **D-07:** Tiered retry budget — 3 retries for syntax (auto-fix, high fix probability), 2 for test failures (may need different approach), 1 for contract/structural (planning problem, not execution problem — escalate to replanning). Different failure types have fundamentally different fix probabilities.

### CI Gate + Main Branch Protection
- **D-08:** Local CI runner module — structured pipeline definition (typecheck -> lint -> test -> build) with stage-level pass/fail reporting that feeds into the failure heatmap from Phase 14. Subprocess-based but with proper stage tracking. No GitHub Actions dependency.
- **D-09:** Fast-forward only merge policy — each task rebases on latest main before merge. Guarantees linear history, every CI run reflects true state, easier to bisect. No merge commits, no squash.

### Claude's Discretion
- Branch naming convention details (e.g., `agent/task-{id}` vs `agent/{dag_id}/task-{id}`)
- Context pack file selection algorithm (how Analyzer scores transitive dependencies for relevance)
- Failure classification regex patterns for each error category
- CI pipeline stage ordering and timeout configuration
- How rebase-on-main integrates with the scheduler's task queue
- Ownership map data structure (from module map → which agent owns which files)
- How the CI runner reports results back to the scheduler/EventBus

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Orchestrator Foundation (Phase 12)
- `agent/orchestrator/scheduler.py` — DAGScheduler with async worker pool, `_run_task()`, `_emit_progress()`. Extend with branch isolation, retry logic, CI gating.
- `agent/orchestrator/dag.py` — TaskDAG wrapping NetworkX. Task dependency graph — requeue logic hooks into this.
- `agent/orchestrator/models.py` — TaskNode, TaskEdge, TaskExecution, DAGRun, DecisionTrace Pydantic models. Extend TaskExecution with retry_count, failure_type, branch_name.
- `agent/orchestrator/persistence.py` — DAGPersistence for SQLite state. Persist retry state and branch associations.
- `agent/orchestrator/events.py` — Task lifecycle event constants (TASK_STARTED/COMPLETED/FAILED, etc.). Add CI events.
- `agent/orchestrator/contracts.py` — ContractStore with backward compatibility checks (Phase 14). CI pipeline validates contract changes.

### Observability (Phase 14)
- `agent/orchestrator/metrics.py` — build_decision_trace(), aggregate_heatmap(). CI failures feed into heatmap.
- `agent/tracing.py` — TraceLogger with agent_id, task_id, severity. Execution agents use this for structured logging.

### Analyzer + Planner (Phase 13)
- `agent/orchestrator/analyzer.py` — Module map with dependency graph. Source for context pack assembly and ownership map.
- `agent/orchestrator/planner.py` — Task DAG generation. Planner picks primary files for context packs.

### Existing Agent Architecture
- `agent/graph.py` — Current LangGraph StateGraph. Execution agents run through this.
- `agent/parallel.py` — Existing asyncio.gather batch execution. Pattern for concurrent agent execution.
- `agent/tools/shell.py` — run_command_async() for subprocess execution. CI runner uses this.
- `agent/github.py` — GitHub API client. Not used for Phase 15 PRs (local only) but reference for future real PR support.

### Server + Persistence
- `store/sqlite.py` — SQLiteSessionStore with WAL mode. Add execution state tables.
- `store/models.py` — Pydantic models. Pattern for new execution models.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DAGScheduler` (scheduler.py): Already has async worker pool with configurable concurrency, task state management, event emission. Core extension point for branch isolation and retry logic.
- `TaskExecution` (models.py): Has error_message, result_summary fields. Extend with failure_type, retry_count, branch_name.
- `aggregate_heatmap()` (metrics.py): Already groups failures by module x error_category. CI failures feed directly into this.
- `run_command_async()` (shell.py): Async subprocess execution. CI runner builds on this.
- `_emit_progress()` (scheduler.py): Already emits 6 metrics via EventBus. Extend with CI stage status.

### Established Patterns
- EventBus P0/P1/P2 priority routing for real-time event streaming
- Pydantic BaseModel for all data models
- SQLite persistence with WAL mode for concurrent access
- asyncio.Semaphore for concurrency limiting (already in scheduler)

### Integration Points
- DAGScheduler._run_task() — wrap with branch creation/checkout before execution, CI validation after
- DAGScheduler worker loop — add requeue-on-conflict logic
- EventBus — add CI_STARTED, CI_PASSED, CI_FAILED event types
- Frontend wsStore — add CI pipeline status to progress metrics

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 15-execution-engine-ci-validation*
*Context gathered: 2026-03-29*
