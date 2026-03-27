---
phase: 04-crash-recovery-run-lifecycle
plan: 01
subsystem: infra
tags: [langgraph, checkpoint, sqlite, crash-recovery, asyncsqlitesaver]

# Dependency graph
requires: []
provides:
  - "build_graph(checkpointer) accepts optional AsyncSqliteSaver checkpointer"
  - "Server lifespan manages AsyncSqliteSaver lifecycle with shipyard_checkpoints.db"
  - "thread_id in all ainvoke configurable dicts for checkpoint keying"
  - "list_runs_by_status() query for finding interrupted runs"
  - "_resume_interrupted_runs() background task on server startup"
  - "trace_url field on Run model"
affects: [04-02, 04-03, 05-tracing]

# Tech tracking
tech-stack:
  added: [langgraph-checkpoint-sqlite (AsyncSqliteSaver)]
  patterns: [checkpoint-per-node, thread_id-keyed-resume, crash-recovery-on-startup]

key-files:
  created:
    - tests/test_checkpoint.py
  modified:
    - agent/graph.py
    - server/main.py
    - store/sqlite.py
    - store/models.py
    - tests/test_graph.py

key-decisions:
  - "AsyncSqliteSaver uses separate shipyard_checkpoints.db to isolate checkpoint data from application DB"
  - "Resume passes None as input to ainvoke() to trigger LangGraph checkpoint resume"
  - "Resume runs as background asyncio tasks so server startup is not blocked"
  - "trace_url added to Run model now to prevent schema migration conflicts with Plan 03"

patterns-established:
  - "Checkpoint resume pattern: ainvoke(None, config={thread_id: run_id}) resumes from last node"
  - "Crash recovery: query runs by status on startup, create background tasks for each"

requirements-completed: [INFRA-04]

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 04 Plan 01: Checkpoint Crash Recovery Summary

**AsyncSqliteSaver checkpointing wired into LangGraph graph with automatic crash recovery resuming interrupted runs on server restart**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T01:07:29Z
- **Completed:** 2026-03-27T01:12:41Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- build_graph() accepts optional checkpointer, enabling per-node checkpoint persistence to shipyard_checkpoints.db
- All 3 ainvoke call sites (submit_instruction, continue_run, _resume_run) include thread_id for checkpoint keying
- Server detects interrupted runs (status="running") on startup and resumes them from last checkpoint
- Added list_runs_by_status() query and trace_url field to support future tracing plan

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire AsyncSqliteSaver into graph compilation and server lifespan** - `deacf0e` (feat)
2. **Task 2: Implement crash recovery - resume interrupted runs on server restart** - `8f718b3` (feat)

_Note: TDD tasks had RED/GREEN phases within each commit_

## Files Created/Modified
- `agent/graph.py` - build_graph() now accepts optional checkpointer parameter
- `server/main.py` - AsyncSqliteSaver lifecycle in lifespan, thread_id in configs, crash recovery functions
- `store/sqlite.py` - list_runs_by_status() method, trace_url in create_run/update_run, migration
- `store/models.py` - trace_url field added to Run model
- `tests/test_graph.py` - Checkpointer compilation tests
- `tests/test_checkpoint.py` - Checkpoint persistence and crash recovery resume tests

## Decisions Made
- Used separate `shipyard_checkpoints.db` file to isolate checkpoint data from application `shipyard.db`
- Resume passes `None` as input to `ainvoke()` which tells LangGraph to resume from last checkpoint
- Background `asyncio.create_task` for resume so server startup is not blocked by potentially long-running resumes
- Added `trace_url` to Run model proactively to avoid schema migration conflicts with Plan 03

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Checkpoint infrastructure ready for Plan 02 (run lifecycle state machine) and Plan 03 (LangSmith tracing)
- list_runs_by_status() available for any status-based queries
- trace_url field ready for Plan 03 to populate with LangSmith trace links

---
*Phase: 04-crash-recovery-run-lifecycle*
*Completed: 2026-03-27*
