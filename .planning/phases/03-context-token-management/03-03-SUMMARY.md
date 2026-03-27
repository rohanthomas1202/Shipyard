---
phase: 03-context-token-management
plan: 03
subsystem: agent
tags: [context-assembly, token-tracking, model-routing, prompt-construction]

requires:
  - phase: 03-01
    provides: "TokenTracker, ModelRouter with usage tracking, resolve_model()"
  - phase: 03-02
    provides: "ContextAssembler pipeline, reader_node skeleton support"
provides:
  - "Planner and editor nodes use ContextAssembler with model-aware budgets"
  - "Reporter node emits token usage summary in traces and model_usage state"
  - "ContextAssembler system_prompt_reserve parameter for budget accuracy"
affects: [04-resilience, ship-rebuild]

tech-stack:
  added: []
  patterns: ["ContextAssembler instantiation from resolve_model() budget in nodes"]

key-files:
  created: []
  modified:
    - agent/context.py
    - agent/nodes/planner.py
    - agent/nodes/editor.py
    - agent/nodes/reporter.py
    - tests/test_context.py

key-decisions:
  - "system_prompt_reserve default 500 tokens -- balances budget accuracy without over-reserving"
  - "Assembler build() output replaces inline context_section; EDITOR_USER template still wraps it"
  - "max(0, ...) guard prevents negative budget when reserve exceeds max_tokens"

patterns-established:
  - "Node-level ContextAssembler: resolve model, compute budget, assemble, build"

requirements-completed: [CTX-01, LIFE-02]

duration: 3min
completed: 2026-03-27
---

# Phase 03 Plan 03: Wire ContextAssembler into Nodes Summary

**ContextAssembler with model-aware budgets in planner/editor nodes, token usage reporting in reporter traces**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T00:36:15Z
- **Completed:** 2026-03-27T00:39:15Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Planner and editor nodes construct prompts via ContextAssembler with model-specific token budgets
- ContextAssembler budget = model.context_window - model.max_output - system_prompt_reserve
- Reporter node surfaces accumulated token usage from ModelRouter in traces and model_usage state field
- All existing prompt templates (PLANNER_SYSTEM, EDITOR_SYSTEM, PLANNER_USER, EDITOR_USER) preserved as wrappers

## Task Commits

Each task was committed atomically:

1. **Task 1: Enhance ContextAssembler and wire into planner + editor** - `6352a75` (feat)
2. **Task 2: Reporter emits token usage summary** - `4e3c2f8` (feat)

## Files Created/Modified
- `agent/context.py` - Added system_prompt_reserve parameter with max(0) guard
- `agent/nodes/planner.py` - Refactored to use ContextAssembler with resolve_model budget
- `agent/nodes/editor.py` - Refactored to use ContextAssembler with priority-ranked assembly
- `agent/nodes/reporter.py` - Added config param, extracts token usage from router
- `tests/test_context.py` - Added tests for reserve, default reserve, large context window

## Decisions Made
- system_prompt_reserve default of 500 tokens balances accuracy without over-reserving for typical system prompts
- Added max(0, ...) guard so ContextAssembler gracefully handles cases where reserve exceeds max_tokens
- Editor passes assembled context through context_section field of EDITOR_USER template, with numbered_content/edit_instruction/error_feedback set to empty (assembler handles them)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added max(0) guard for negative budget**
- **Found during:** Task 1 (test_assembler_prioritizes_working_set)
- **Issue:** Small max_tokens (200) with default reserve (500) produced negative max_chars
- **Fix:** Wrapped budget calculation in max(0, ...) and adjusted test token values
- **Files modified:** agent/context.py, tests/test_context.py
- **Verification:** All 10 tests pass
- **Committed in:** 6352a75 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for correctness with small budgets. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 03 plans complete (01: token tracking + router, 02: context assembly + reader, 03: node wiring + reporting)
- Ready for Phase 04 (resilience hardening)

---
*Phase: 03-context-token-management*
*Completed: 2026-03-27*
