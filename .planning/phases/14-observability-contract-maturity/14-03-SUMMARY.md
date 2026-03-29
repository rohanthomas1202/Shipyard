---
phase: 14-observability-contract-maturity
plan: 03
subsystem: observability
tags: [pydantic, decision-trace, heatmap, react, zustand]

requires:
  - phase: 14-02
    provides: "DECISION_TRACE event constant, DecisionTraceData interface, wsStore decisionTraces slice"
provides:
  - "DecisionTrace Pydantic model for failure context capture"
  - "build_decision_trace() and aggregate_heatmap() metrics helpers"
  - "Scheduler emits decision_trace events on task failure"
  - "DecisionTrace React component with expandable error details"
  - "FailureHeatmap React component with module x error category table"
  - "EventCard renders DecisionTrace inline for decision_trace events"
  - "AgentPanel renders FailureHeatmap below activity stream"
affects: [14-04, observability, debugging]

tech-stack:
  added: []
  patterns: ["TDD for observability metrics", "heatmap aggregation pattern"]

key-files:
  created:
    - agent/orchestrator/metrics.py
    - web/src/components/agent/DecisionTrace.tsx
    - web/src/components/agent/FailureHeatmap.tsx
    - tests/test_observability.py
  modified:
    - agent/orchestrator/models.py
    - agent/orchestrator/scheduler.py
    - web/src/components/agent/EventCard.tsx
    - web/src/components/agent/AgentPanel.tsx

key-decisions:
  - "LLM context truncated to 2000 chars in build_decision_trace to prevent event bloat"
  - "FailureHeatmap placed below activity stream in bordered section per UI-SPEC guidance"

patterns-established:
  - "Observability metrics module pattern: model in models.py, helpers in metrics.py"
  - "Heatmap aggregation: module_name x error_category with unknown fallback"

requirements-completed: [OBSV-03]

duration: 3min
completed: 2026-03-29
---

# Phase 14 Plan 03: Decision Traces + Failure Heatmap Summary

**Decision trace capture on task failure with LLM context truncation, heatmap aggregation by module x error category, and frontend components for inline trace display and color-coded failure table**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T21:06:38Z
- **Completed:** 2026-03-29T21:09:57Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- DecisionTrace Pydantic model with error_category, llm_prompt/response, files_read, module_name fields
- build_decision_trace() truncates LLM context to 2000 chars; aggregate_heatmap() groups failures by module x error category
- Scheduler emits decision_trace events on task failure with full trace data persisted in result_summary
- DecisionTrace React component renders expandable error details with category badge and LLM context preview
- FailureHeatmap React component renders module x error type table with color-coded cells
- EventCard renders DecisionTrace inline for decision_trace events; AgentPanel renders FailureHeatmap below activity stream

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend -- DecisionTrace model + metrics module + scheduler integration** - `d4a9606` (test: RED), `03ddfe6` (feat: GREEN)
2. **Task 2: Frontend -- DecisionTrace + FailureHeatmap components** - `378c567` (feat)
3. **Task 3: Wire DecisionTrace into EventCard and FailureHeatmap into AgentPanel** - `07b8c1d` (feat)

## Files Created/Modified
- `agent/orchestrator/models.py` - Added DecisionTrace Pydantic model
- `agent/orchestrator/metrics.py` - build_decision_trace() and aggregate_heatmap() helpers
- `agent/orchestrator/scheduler.py` - Emits decision_trace event on task failure, persists trace in result_summary
- `tests/test_observability.py` - 6 tests for decision trace construction and heatmap aggregation
- `web/src/components/agent/DecisionTrace.tsx` - Expandable error details with category badge, files list, LLM context
- `web/src/components/agent/FailureHeatmap.tsx` - Module x error type table with color-coded cells
- `web/src/components/agent/EventCard.tsx` - Added decision_trace case to EventBody and ExpandedDetail
- `web/src/components/agent/AgentPanel.tsx` - Added FailureHeatmap below activity stream

## Decisions Made
- LLM context truncated to 2000 chars in build_decision_trace to prevent event payload bloat
- FailureHeatmap placed below activity stream in a bordered section per UI-SPEC guidance (visible to operators but out of main event flow)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all components are fully wired with real data sources.

## Next Phase Readiness
- Decision traces and heatmap aggregation ready for Plan 04 consumption
- Frontend components render live data from wsStore decisionTraces slice

## Self-Check: PASSED

All 8 files verified present. All 4 commit hashes verified in git log.

---
*Phase: 14-observability-contract-maturity*
*Completed: 2026-03-29*
