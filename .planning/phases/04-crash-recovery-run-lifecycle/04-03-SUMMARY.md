---
phase: 04-crash-recovery-run-lifecycle
plan: 03
subsystem: observability
tags: [langsmith, tracing, langchain, observability]

requires:
  - phase: 04-02
    provides: Run model with trace_url field, cancel/resume execution paths
provides:
  - share_trace_link() async utility for generating public LangSmith trace URLs
  - Run tagging with run_id for LangSmith trace lookup
  - trace_url capture in all 4 execution paths (submit, continue, resume, checkpoint-resume)
  - trace_url in /status endpoint response
affects: [05-ship-rebuild, 06-documentation]

tech-stack:
  added: [langsmith Client API]
  patterns: [async executor wrapping for sync SDK calls, graceful degradation on missing env vars, run tagging for trace correlation]

key-files:
  created: [tests/test_tracing.py]
  modified: [agent/tracing.py, server/main.py]

key-decisions:
  - "Lazy import of langsmith.Client at module level with graceful try/except in function"
  - "asyncio.run_in_executor for sync LangSmith SDK calls to avoid blocking event loop"
  - "Tag-based lookup (run_id:{id}) for correlating Shipyard runs to LangSmith traces"

patterns-established:
  - "Trace link generation: tag runs then lookup by tag post-execution"
  - "Graceful SDK degradation: check env var, try/except, return None on any error"

requirements-completed: [LIFE-03]

duration: 9min
completed: 2026-03-27
---

# Phase 04 Plan 03: LangSmith Tracing Summary

**LangSmith shared trace links via tag-based lookup with graceful degradation when tracing unavailable**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-27T01:19:36Z
- **Completed:** 2026-03-27T01:28:15Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- share_trace_link() generates public LangSmith URLs by finding runs tagged with Shipyard run_id
- All 4 execution paths (submit_instruction, continue_run, _resume_run, _resume_from_checkpoint) tag runs and capture trace URLs
- /status endpoint returns trace_url field
- Graceful degradation: returns None when LANGCHAIN_API_KEY not set or LangSmith unavailable
- Full test coverage: 4 tests covering success, no-api-key, exception, and status endpoint

## Task Commits

Each task was committed atomically (TDD):

1. **Task 1 RED: Failing tests** - `885bee4` (test)
2. **Task 1 GREEN: Implementation** - `82498d6` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `agent/tracing.py` - Added share_trace_link() async utility, module docstring, logging
- `server/main.py` - Added tags to all config dicts, trace_url capture after execution, trace_url in /status response
- `tests/test_tracing.py` - 4 tests covering trace link generation and status endpoint

## Decisions Made
- Used module-level import of langsmith.Client with function-level graceful degradation (try/except returns None)
- Used asyncio.run_in_executor() to wrap sync LangSmith SDK calls for non-blocking async execution
- Tag-based trace lookup using `has(tags, "run_id:{id}")` filter for reliable correlation

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all functionality is fully wired.

## Issues Encountered

- Pre-existing test failures in test_ast_ops.py and test_editor_node.py (async migration issues unrelated to this plan) - logged to deferred-items.md

## User Setup Required

None - LangSmith env vars (LANGCHAIN_API_KEY, LANGCHAIN_PROJECT, LANGCHAIN_TRACING_V2) are already documented in .env.example.

## Next Phase Readiness
- LangSmith tracing fully operational for generating the two required trace links (normal + error recovery)
- Phase 04 complete: crash recovery, run cancellation, and tracing all delivered
- Ready for Phase 05 (Ship rebuild) which will exercise tracing in real runs

---
*Phase: 04-crash-recovery-run-lifecycle*
*Completed: 2026-03-27*
