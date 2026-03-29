---
phase: 13-analyzer-planner-agents
plan: 02
subsystem: agent
tags: [pydantic, planner, dag, validation, prompts]

requires:
  - phase: 12-orchestrator-dag-engine
    provides: TaskDAG.from_definition() for cycle detection, TaskNode model
provides:
  - PRDOutput, TechSpecOutput, TaskDAGOutput Pydantic models for three-layer pipeline
  - Structural validation gates (cycle detection, LOC/file bounds, contract refs)
  - System prompts and user prompt builders for all three pipeline layers
  - estimate_cost function for token estimation
affects: [13-analyzer-planner-agents]

tech-stack:
  added: []
  patterns: [three-layer-pipeline-models, structural-validation-gates]

key-files:
  created:
    - agent/planner_v2/__init__.py
    - agent/planner_v2/models.py
    - agent/planner_v2/prompts.py
    - agent/planner_v2/validation.py
    - tests/test_planner_validation.py
  modified: []

key-decisions:
  - "Analyzer/orchestrator stubs created for parallel execution compatibility"
  - "TOKENS_PER_LOC = 50 for cost estimation formula"
  - "ValidationError as Pydantic BaseModel with severity field for error/warning distinction"

patterns-established:
  - "Three-layer pipeline: PRD -> Tech Spec -> Task DAG with structural validation between layers"
  - "Indivisible escape hatch: tasks can bypass LOC/file bounds with justification"

requirements-completed: [PLAN-04]

duration: 3min
completed: 2026-03-29
---

# Phase 13 Plan 02: Planner v2 Models and Validation Summary

**Three-layer pipeline Pydantic models (PRD, Tech Spec, Task DAG) with structural validation gates for cycle detection, LOC/file bounds, contract completeness, and cost estimation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T18:23:44Z
- **Completed:** 2026-03-29T18:26:54Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Defined complete Pydantic model hierarchy for three-layer planning pipeline (PRDOutput, TechSpecOutput, TaskDAGOutput, PipelineResult)
- Built structural validation gates that detect DAG cycles via TaskDAG.from_definition(), enforce LOC/file bounds with indivisible escape hatch, and flag unknown contract references
- Created system and user prompt templates for all three pipeline layers
- All 9 validation tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Planner v2 Pydantic models and prompt templates** - `9ec10fe` (feat)
2. **Task 2 RED: Add failing validation tests** - `63cb8f6` (test)
3. **Task 2 GREEN: Implement validation gates** - `703e2cc` (feat)

## Files Created/Modified
- `agent/planner_v2/__init__.py` - Package init
- `agent/planner_v2/models.py` - PRDOutput, TechSpecOutput, TaskDAGOutput, PlannedTask, PlannedEdge, PipelineResult models
- `agent/planner_v2/prompts.py` - PRD_SYSTEM_PROMPT, TECH_SPEC_SYSTEM_PROMPT, TASK_DAG_SYSTEM_PROMPT and user prompt builders
- `agent/planner_v2/validation.py` - validate_prd, validate_tech_spec, validate_task_dag, estimate_cost, ValidationError
- `tests/test_planner_validation.py` - 9 tests covering all validation behaviors
- `agent/analyzer/__init__.py` - Analyzer package stub for parallel execution
- `agent/analyzer/models.py` - ModuleMap stub for validation import
- `agent/orchestrator/models.py` - TaskNode/TaskEdge stub for DAG import
- `agent/orchestrator/dag.py` - TaskDAG stub for cycle detection

## Decisions Made
- Created analyzer/orchestrator module stubs for parallel worktree execution since phase 12 and plan 13-01 outputs not yet merged
- TOKENS_PER_LOC = 50 as the cost estimation multiplier per research recommendations
- ValidationError as Pydantic BaseModel (not Python Exception) to allow structured error reporting with severity levels

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created orchestrator and analyzer module stubs**
- **Found during:** Task 1 (model creation)
- **Issue:** agent/orchestrator/ and agent/analyzer/ directories don't exist in this worktree (created by phase 12 and plan 13-01 running in parallel)
- **Fix:** Copied orchestrator modules from main repo, created analyzer/models.py stub matching plan 13-01 spec
- **Files modified:** agent/orchestrator/models.py, agent/orchestrator/dag.py, agent/orchestrator/__init__.py, agent/analyzer/__init__.py, agent/analyzer/models.py
- **Verification:** All imports succeed, tests pass
- **Committed in:** 9ec10fe (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for parallel execution. Stub files match the contracts from phase 12 and plan 13-01.

## Issues Encountered
None beyond the dependency stubs documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Planner v2 models and validation ready for Plan 03 (LLM-powered Analyzer agent) and Plan 04 (pipeline orchestration)
- Validation functions wired to TaskDAG.from_definition() for real cycle detection
- Prompt templates ready for LLM integration

---
*Phase: 13-analyzer-planner-agents*
*Completed: 2026-03-29*
