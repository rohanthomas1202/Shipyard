---
phase: 12-orchestrator-dag-engine-contract-foundation
plan: 02
subsystem: orchestrator
tags: [dag, scheduler, asyncio, sqlite, persistence, crash-recovery, event-bus]

requires:
  - phase: 12-01
    provides: TaskDAG, TaskNode, TaskExecution, DAGRun models and DAG graph wrapper
provides:
  - DAGScheduler async engine with dependency enforcement and concurrency control
  - DAGPersistence SQLite layer for crash recovery and resume
  - Task lifecycle event constants for EventBus integration
  - Four new SQLite tables (dag_runs, task_nodes, task_edges, task_executions)
affects: [12-03, orchestrator-integration, agent-graph]

tech-stack:
  added: []
  patterns: [asyncio.Semaphore for concurrency control, asyncio.Event for non-polling wake, crash recovery via mark_interrupted]

key-files:
  created:
    - agent/orchestrator/scheduler.py
    - agent/orchestrator/persistence.py
    - agent/orchestrator/events.py
    - tests/test_scheduler.py
    - tests/test_dag_resume.py
  modified:
    - agent/events.py
    - store/sqlite.py

key-decisions:
  - "Failed predecessors block downstream tasks -- not treated as completed (prevents invalid task execution)"
  - "load_failed_tasks added to DAGPersistence for crash recovery to prevent re-execution of failed tasks"
  - "Event-driven scheduling loop via asyncio.Event (no polling) to wake main loop on task completion"

patterns-established:
  - "Semaphore-based concurrency: asyncio.Semaphore(max_concurrency) gates _run_task for bounded parallelism"
  - "Progress event pattern: asyncio.Event set on task completion, cleared before wait in scheduling loop"
  - "Crash recovery pattern: mark_interrupted() + load_failed_tasks() + load_completed_tasks() on scheduler startup"

requirements-completed: [ORCH-02, ORCH-05]

duration: 6min
completed: 2026-03-29
---

# Phase 12 Plan 02: Scheduler + Persistence Summary

**Async DAG scheduler with dependency-enforced task execution, SQLite crash recovery, and EventBus lifecycle events**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-29T09:21:59Z
- **Completed:** 2026-03-29T09:28:43Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- DAGScheduler enforces dependency ordering -- no task starts before all predecessors complete
- Concurrency bounded by configurable asyncio.Semaphore (max_concurrency parameter)
- Full SQLite persistence on every status transition enables crash recovery
- Crash recovery marks interrupted (running) tasks as failed and skips completed tasks on resume
- EventBus extended with 7 P0 task lifecycle event types including contract_update_requested (D-07)
- Four new SQLite tables added to store schema for DAG state persistence

## Task Commits

Each task was committed atomically:

1. **Task 1: DAG persistence layer, event types, and SQLite schema** - `893828a` (test), `f1a9d2d` (feat)
2. **Task 2: DAGScheduler with dependency enforcement and concurrency** - `c812d5b` (test), `9d1524b` (feat)

_TDD tasks have RED (test) and GREEN (feat) commits_

## Files Created/Modified
- `agent/orchestrator/scheduler.py` - DAGScheduler class with async scheduling loop, concurrency control, crash recovery
- `agent/orchestrator/persistence.py` - DAGPersistence class for SQLite save/load/update of DAG state
- `agent/orchestrator/events.py` - Task lifecycle event type constants (TASK_STARTED, TASK_COMPLETED, etc.)
- `agent/events.py` - Extended _P0_TYPES with task lifecycle events
- `store/sqlite.py` - Added dag_runs, task_nodes, task_edges, task_executions tables
- `tests/test_scheduler.py` - 8 scheduler tests (dependency, concurrency, failure, recovery, events)
- `tests/test_dag_resume.py` - 5 persistence tests (save/load, status updates, crash recovery)

## Decisions Made
- Failed predecessors block downstream tasks -- get_ready_tasks only considers completed predecessors, not failed ones. This prevents cascading invalid executions.
- Added load_failed_tasks() to DAGPersistence beyond the plan spec, needed so crash recovery correctly prevents re-execution of interrupted-then-failed tasks.
- Event-driven wake pattern (asyncio.Event) instead of polling -- main loop sets/clears event on task completion for efficient coordination.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Failed predecessors incorrectly treated as completed**
- **Found during:** Task 2 (DAGScheduler implementation)
- **Issue:** Initial implementation passed `self._completed | self._failed` to get_ready_tasks(), causing downstream tasks to run even when predecessors failed
- **Fix:** Changed to only pass `self._completed` to get_ready_tasks(), filter ready list to exclude failed tasks
- **Files modified:** agent/orchestrator/scheduler.py
- **Verification:** test_task_failure_does_not_block_independent passes
- **Committed in:** 9d1524b

**2. [Rule 1 - Bug] Event model missing required project_id field**
- **Found during:** Task 2 (EventBus integration)
- **Issue:** Event constructor called without project_id which is a required field on store.models.Event
- **Fix:** Added project_id=self._dag_run.project_id to Event creation in _emit()
- **Files modified:** agent/orchestrator/scheduler.py
- **Verification:** test_events_emitted passes
- **Committed in:** 9d1524b

**3. [Rule 2 - Missing Critical] Added load_failed_tasks to DAGPersistence**
- **Found during:** Task 2 (crash recovery implementation)
- **Issue:** Crash recovery marked interrupted tasks as failed in DB but scheduler had no way to load those failures into self._failed set, causing re-execution
- **Fix:** Added load_failed_tasks() method to DAGPersistence, called during scheduler startup
- **Files modified:** agent/orchestrator/persistence.py, agent/orchestrator/scheduler.py
- **Verification:** test_crash_recovery_marks_interrupted passes
- **Committed in:** 9d1524b

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Scheduler and persistence ready for Plan 03 integration proof (DAG execution test with contracts)
- All 36 tests pass (13 from Plan 01 + 13 from Plan 02)
- DAGScheduler injectable with custom task_executor for Plan 03 agent node integration

---
*Phase: 12-orchestrator-dag-engine-contract-foundation*
*Completed: 2026-03-29*
