---
phase: 15-execution-engine-ci-validation
plan: 02
subsystem: orchestrator
tags: [ci-pipeline, failure-classification, regex, retry-budgets, dataclass]

requires:
  - phase: 13-analyzer-planner-agents
    provides: orchestrator module structure and models
provides:
  - CIRunner with 4-stage local CI pipeline (typecheck, lint, test, build)
  - FailureClassifier with hybrid regex + LLM classification
  - Tiered retry budgets and strategies per failure category
affects: [15-04-scheduler-integration, 15-03-contract-validation]

tech-stack:
  added: []
  patterns: [dataclass-based pipeline stages, hybrid regex-then-LLM classification, stop-on-first-failure pipeline]

key-files:
  created:
    - agent/orchestrator/ci_runner.py
    - agent/orchestrator/failure_classifier.py
    - tests/test_ci_runner.py
    - tests/test_failure_classifier.py
  modified: []

key-decisions:
  - "Dataclasses for CI pipeline models (lightweight, no Pydantic overhead for internal-only structures)"
  - "Regex-first classification with LLM fallback preserves speed for known patterns"
  - "Error output truncated to 2000 chars for LLM calls to prevent token bloat"

patterns-established:
  - "Stop-on-first-failure pipeline: CIRunner breaks on first non-zero exit code"
  - "Hybrid classification: deterministic regex patterns first, LLM fallback for unknowns"
  - "Tiered retry budgets: syntax=3, test=2, contract=1, structural=1"

requirements-completed: [VALD-01, VALD-02]

duration: 2min
completed: 2026-03-29
---

# Phase 15 Plan 02: CI Runner and Failure Classifier Summary

**Local CI pipeline with 4-stage stop-on-failure execution and hybrid regex/LLM failure classification with tiered retry budgets**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-29T22:00:28Z
- **Completed:** 2026-03-29T22:02:21Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- CIRunner executes typecheck, lint, test, build stages sequentially with stop-on-first-failure
- FailureClassifier categorizes errors as syntax/test/contract/structural via regex patterns
- LLM fallback for unrecognized errors via ModelRouter integration
- Tiered retry budgets (3/2/1/1) and strategies (auto_fix/debug/spec_update/replan)
- 33 tests covering both modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CI Runner with 4-stage pipeline** - `ffc0460` (feat)
2. **Task 2: Create Failure Classifier with regex patterns and tiered retry budgets** - `619b6dd` (feat)

## Files Created/Modified
- `agent/orchestrator/ci_runner.py` - Local CI pipeline runner with CIStage, CIStageResult, CIPipelineResult, CIRunner
- `agent/orchestrator/failure_classifier.py` - Hybrid regex + LLM failure classifier with retry budgets and strategies
- `tests/test_ci_runner.py` - 13 tests for CI runner (all-pass, failure, timeout, cwd_suffix, duration)
- `tests/test_failure_classifier.py` - 20 tests for classifier (regex categories, LLM fallback, budgets, strategies)

## Decisions Made
- Used dataclasses (not Pydantic) for CI pipeline models -- lightweight internal-only structures
- Regex-first classification preserves deterministic speed for known error patterns
- Error output truncated to 2000 chars before LLM call to prevent token bloat
- Optional router parameter allows tests to run without LLM dependency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- CI runner and failure classifier ready for scheduler integration (Plan 04)
- CIPipelineResult.error_output feeds directly into FailureClassifier.classify()
- Retry budgets and strategies ready for orchestrator consumption

---
*Phase: 15-execution-engine-ci-validation*
*Completed: 2026-03-29*
