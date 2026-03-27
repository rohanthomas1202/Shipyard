---
phase: 01-edit-reliability
plan: 03
subsystem: agent
tags: [structured-output, error-feedback, file-freshness, pydantic, openai-parse, content-hash]

# Dependency graph
requires:
  - phase: 01-edit-reliability/01
    provides: "fuzzy matching in edit_file, content_hash, file_hashes in AgentState"
  - phase: 01-edit-reliability/02
    provides: "EditResponse schema, call_llm_structured, router.call_structured"
provides:
  - "Error feedback in editor retry prompts (edit-level and validator-level)"
  - "Structured LLM output for editor (no JSON parse failures on general tier)"
  - "File freshness checking via content_hash before edits"
  - "Structured validator error output with last_validation_error"
affects: [01-edit-reliability, planner-improvements, context-injection]

# Tech tracking
tech-stack:
  added: []
  patterns: ["_build_error_feedback() two-source error context", "structured output for general tier with string fallback for reasoning tier", "file freshness via content_hash comparison"]

key-files:
  created: []
  modified:
    - agent/nodes/editor.py
    - agent/nodes/validator.py
    - agent/prompts/editor.py
    - agent/state.py
    - tests/test_editor_node.py
    - tests/test_validator_node.py

key-decisions:
  - "String concatenation for error feedback building to avoid brace injection from code content"
  - "Reasoning tier (o3/edit_complex) falls back to router.call() with manual JSON parsing since structured outputs may not be supported"
  - "last_validation_error stored as separate dict alongside error_state string for backward compatibility with should_continue()"

patterns-established:
  - "_build_error_feedback pattern: centralized error context assembly from multiple sources"
  - "Structured output branching: call_structured for general tier, call for reasoning tier"
  - "File freshness pattern: compare stored hash vs current hash, re-read on mismatch"

requirements-completed: [EDIT-02, EDIT-04, VALID-01]

# Metrics
duration: 6min
completed: 2026-03-26
---

# Phase 01 Plan 03: Error Feedback, Structured Outputs, and File Freshness Summary

**Closed editor retry feedback loop with two error sources, migrated to structured LLM outputs via EditResponse, and added file freshness detection via content_hash**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-26T23:36:31Z
- **Completed:** 2026-03-26T23:42:55Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Editor retry prompts now include failed anchor text, best match found, similarity score (edit-level failures) AND file_path + error_message from validator (validator-level failures)
- Editor uses router.call_structured(EditResponse) for general tier edits, eliminating JSON parse failures for simple edits
- File freshness checked via content_hash before edits, with automatic re-read on stale hash
- Validator produces structured last_validation_error dict alongside backward-compatible error_state string
- 20 total tests pass across editor and validator (13 new tests added)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add error feedback template and update editor prompt** - `89c720c` (feat)
2. **Task 2: Migrate editor_node to structured outputs, error feedback, and file freshness** - `337a34d` (feat)
3. **Task 3: Enhance validator error output with structured details** - `3ec06d5` (feat)

## Files Created/Modified
- `agent/prompts/editor.py` - Added ERROR_FEEDBACK_TEMPLATE, {error_feedback} placeholder in EDITOR_USER
- `agent/nodes/editor.py` - Structured outputs, _build_error_feedback(), freshness check, file_hashes updates, structured error entries
- `agent/nodes/validator.py` - last_validation_error dict in syntax_check and LSP failure paths
- `agent/state.py` - Added last_validation_error field to AgentState
- `tests/test_editor_node.py` - 9 new tests (template, structured output, error feedback, freshness, reasoning tier fallback)
- `tests/test_validator_node.py` - 4 new tests (error details, structured validation error)

## Decisions Made
- Used string concatenation in _build_error_feedback() to avoid brace injection from code content in format strings
- Reasoning tier (o3/edit_complex) falls back to router.call() with manual JSON parsing since structured outputs may not be supported by o3
- last_validation_error stored as separate dict field alongside error_state string to maintain backward compatibility with should_continue() truthiness check in graph.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added error_feedback="" to existing EDITOR_USER.format() call**
- **Found during:** Task 1 (after adding {error_feedback} to template)
- **Issue:** Adding {error_feedback} placeholder broke existing editor_node code which didn't pass that parameter
- **Fix:** Added error_feedback="" to the format() call as a temporary fix (replaced properly in Task 2)
- **Files modified:** agent/nodes/editor.py
- **Verification:** All existing tests pass
- **Committed in:** 89c720c (Task 1 commit)

**2. [Rule 3 - Blocking] Updated make_config_with_mock_router to include call_structured mock**
- **Found during:** Task 2 (existing tests failing after structured output migration)
- **Issue:** Existing tests created mock routers without call_structured, which is now called for simple tier edits
- **Fix:** Updated helper to parse JSON response and create EditResponse for call_structured mock
- **Files modified:** tests/test_editor_node.py
- **Verification:** All 14 editor tests pass
- **Committed in:** 337a34d (Task 2 commit)

**3. [Rule 1 - Bug] Fixed test assertion for Python 3.14 JSON error message**
- **Found during:** Task 3 (test_validator_error_includes_error_message)
- **Issue:** Python 3.14 JSON parser produces "Illegal trailing comma" instead of "Expecting property name"
- **Fix:** Added "trailing comma" as acceptable assertion match
- **Files modified:** tests/test_validator_node.py
- **Verification:** All 6 validator tests pass
- **Committed in:** 3ec06d5 (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (1 bug fix, 2 blocking)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
- Pre-existing test failure in tests/test_llm.py::test_call_llm_forwards_params (asserts max_tokens but code uses max_completion_tokens). Not caused by this plan. Logged to deferred-items.md.

## Known Stubs
None - all functionality is fully wired.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 01 (edit-reliability) is now complete with all 3 plans executed
- Error feedback loop is closed: failed edits and validation errors both flow into retry prompts
- Structured outputs eliminate JSON parse failures for general tier
- File freshness prevents stale edits
- Ready for Phase 02 work

---
*Phase: 01-edit-reliability*
*Completed: 2026-03-26*
