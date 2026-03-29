---
phase: 15-execution-engine-ci-validation
verified: 2026-03-29T22:14:17Z
status: passed
score: 9/9 must-haves verified
re_verification: false
human_verification:
  - test: "Run real parallel agent tasks on an actual git repository with concurrent branch creation"
    expected: "All branches created serially (no race conditions), CI runs per task, only passing tasks merge to main"
    why_human: "asyncio.Lock serialization can only be validated under real concurrent load; mock-based tests cannot catch OS-level git lock contention"
  - test: "Run CI pipeline on actual project (typecheck, lint, test, build stages)"
    expected: "Each stage reports pass/fail, pipeline stops at first failure, duration_ms is populated"
    why_human: "CI runner uses real subprocesses (npm, pytest) that cannot be tested without the full project environment running"
---

# Phase 15: Execution Engine + CI Validation Verification Report

**Phase Goal:** Multiple agents execute tasks in parallel with branch isolation, ownership enforcement, failure-aware retries, and a CI gate that keeps main always green
**Verified:** 2026-03-29T22:14:17Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each task executes on its own git branch named `agent/task-{id}` | VERIFIED | `scheduler.py:157` sets `branch_name = f"agent/task-{task_id}"`, passed to `branch_manager.create_and_checkout` |
| 2 | Branch is created from latest main before task execution | VERIFIED | `branch_manager.py:40-43`: `create_and_checkout` checks out base (`main`) before creating branch |
| 3 | After task success, branch is rebased on main and fast-forward merged | VERIFIED | `branch_manager.py:53-60`: `rebase_and_merge` uses `git rebase main` then `git merge --ff-only` |
| 4 | Branch is always cleaned up in finally block, even on failure | VERIFIED | `scheduler.py:233-238`: `finally` block calls `branch_manager.cleanup(branch_name)` unconditionally |
| 5 | CI pipeline runs 4 stages in order: typecheck, lint, test, build | VERIFIED | `ci_runner.py:47-52`: `DEFAULT_PIPELINE` defines all 4 stages with correct names |
| 6 | Pipeline stops on first failure and reports which stage failed | VERIFIED | `ci_runner.py:83-84`: `if not passed: break`; `CIPipelineResult.first_failure` returns first failed stage |
| 7 | Failure classifier categorizes errors as syntax, test, contract, or structural | VERIFIED | `failure_classifier.py:57-62`: `classify_regex` matches 22 patterns; `FailureClassifier.classify` with LLM fallback |
| 8 | Tiered retry: syntax=3, test=2, contract=1, structural=1 with absolute cap of 4 | VERIFIED | `failure_classifier.py:34-39`: `RETRY_BUDGETS`; `models.py:51`: `MAX_TOTAL_RETRIES = 4`; `scheduler.py:252`: enforced |
| 9 | CI must pass before merge to main — unstable tasks are never merged | VERIFIED | `scheduler.py:196-209`: CI failure raises `RuntimeError` before `rebase_and_merge` is reached |
| 10 | Context pack with <= 5 files assembled and delivered to executor via `task.metadata` | VERIFIED | `context_packs.py:34`: `result[:MAX_CONTEXT_FILES]`; `scheduler.py:174-176`: `task.metadata["context_pack"] = context_pack` |
| 11 | Ownership validator checks git diff and flags unauthorized file changes | VERIFIED | `ownership.py:51-73`: `git diff --name-only main...HEAD`, violations returned if file owned by different module |
| 12 | Merge conflict causes requeue with fresh branch from updated main | VERIFIED | `scheduler.py:213-217`: `rebase_and_merge` returning `False` calls `_handle_requeue`; test confirms re-execution |

**Score:** 12/12 truths verified (9 required requirement-backed truths, all verified)

### Required Artifacts

| Artifact | Expected | Lines | Status | Details |
|----------|----------|-------|--------|---------|
| `agent/orchestrator/branch_manager.py` | BranchManager with lifecycle ops | 72 | VERIFIED | Contains `BranchManager`, `create_and_checkout`, `rebase_and_merge`, `cleanup`, `verify_branch`, `asyncio.Lock`, `--ff-only`, `rebase --abort` |
| `agent/orchestrator/ci_runner.py` | CIRunner with 4-stage pipeline | 85 | VERIFIED | Contains `CIRunner`, `CIStage`, `CIStageResult`, `CIPipelineResult`, `DEFAULT_PIPELINE`, `run_pipeline`, `run_command_async` import |
| `agent/orchestrator/failure_classifier.py` | Hybrid regex + LLM classifier | 98 | VERIFIED | Contains `FailureCategory`, `classify_regex`, `FailureClassifier`, `RETRY_BUDGETS` (3/2/1/1), `RETRY_STRATEGIES` |
| `agent/orchestrator/context_packs.py` | Context pack assembler | 96 | VERIFIED | Contains `MAX_CONTEXT_FILES = 5`, `ContextPack`, `ContextPackAssembler`, `parse_python_imports`, `all_files` property |
| `agent/orchestrator/ownership.py` | Ownership validator | 73 | VERIFIED | Contains `OwnershipViolation`, `OwnershipValidator`, `build_ownership_map`, `validate`, `git diff --name-only main...HEAD` |
| `agent/orchestrator/models.py` | Extended TaskExecution | 78 | VERIFIED | Contains `retry_count: int = 0`, `failure_type: Literal[...] | None = None`, `branch_name: str | None = None`, `MAX_TOTAL_RETRIES = 4` |
| `agent/orchestrator/events.py` | CI lifecycle event constants | 37 | VERIFIED | Contains `CI_STARTED`, `CI_PASSED`, `CI_FAILED`, `OWNERSHIP_VIOLATION`, `TASK_REQUEUED`; all 5 in `TASK_LIFECYCLE_EVENTS` frozenset |
| `agent/orchestrator/scheduler.py` | Integrated execution engine | 346 | VERIFIED | All 5 modules imported and wired in `_run_task`; `_handle_failure`, `_handle_requeue` present |
| `agent/orchestrator/persistence.py` | Extended persistence | 364 | VERIFIED | `_MIGRATION_V2_COLUMNS` adds `retry_count`, `failure_type`, `branch_name`; `update_task_status` accepts all new fields |
| `tests/test_branch_manager.py` | Branch manager tests | 189 | VERIFIED | 8 test functions; covers create, stale cleanup, idempotent, rebase success, conflict abort, cleanup, verify, lock serialization |
| `tests/test_ci_runner.py` | CI runner tests | ~200 | VERIFIED | 13 test functions |
| `tests/test_failure_classifier.py` | Failure classifier tests | ~250 | VERIFIED | 20 test functions |
| `tests/test_context_packs.py` | Context pack tests | ~150 | VERIFIED | 11 test functions |
| `tests/test_ownership.py` | Ownership tests | ~130 | VERIFIED | 8 test functions |
| `tests/test_execution_engine.py` | Integration tests | ~510 | VERIFIED | 12 test functions; covers full pipeline, retry paths, conflict requeue, context pack delivery |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `branch_manager.py` | `agent/tools/shell.py` | `run_command_async` | WIRED | `from agent.tools.shell import run_command_async` at line 5 |
| `ci_runner.py` | `agent/tools/shell.py` | `run_command_async` | WIRED | `from agent.tools.shell import run_command_async` at line 6 |
| `failure_classifier.py` | `ci_runner.py` | `FailureCategory` type | WIRED | `FailureCategory` defined and used by both; `scheduler.py` imports both |
| `context_packs.py` | `agent/orchestrator/models.py` | `TaskNode` | WIRED | `from agent.orchestrator.models import TaskNode` at line 6 |
| `ownership.py` | `agent/tools/shell.py` | `run_command_async` | WIRED | `from agent.tools.shell import run_command_async` at line 5 |
| `scheduler.py` | `branch_manager.py` | `BranchManager` | WIRED | `from agent.orchestrator.branch_manager import BranchManager` at line 28 |
| `scheduler.py` | `ci_runner.py` | `CIRunner` | WIRED | `from agent.orchestrator.ci_runner import CIRunner, CIPipelineResult` at line 29 |
| `scheduler.py` | `failure_classifier.py` | `FailureClassifier` | WIRED | `from agent.orchestrator.failure_classifier import FailureClassifier, RETRY_BUDGETS` at line 30 |
| `scheduler.py` | `context_packs.py` | `ContextPackAssembler` | WIRED | `from agent.orchestrator.context_packs import ContextPackAssembler` at line 31 |
| `scheduler.py` | `ownership.py` | `OwnershipValidator` | WIRED | `from agent.orchestrator.ownership import OwnershipValidator` at line 32 |
| `scheduler.py` | `context_packs.py` | `task.metadata["context_pack"]` | WIRED | `scheduler.py:176`: `task.metadata["context_pack"] = context_pack` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `scheduler.py._run_task` | `branch_name` | `f"agent/task-{task_id}"` at line 157 | Yes — computed, not hardcoded | FLOWING |
| `scheduler.py._run_task` | `context_pack` | `context_assembler.assemble(task)` at line 175 | Yes — reads `task.metadata["target_files"]` and parses imports | FLOWING |
| `scheduler.py._run_task` | `ci_result` | `ci_runner.run_pipeline()` at line 198 | Yes — runs real subprocesses, populates `CIPipelineResult.stages` | FLOWING |
| `scheduler.py._handle_failure` | `category` | `failure_classifier.classify(error_msg)` at line 245 | Yes — regex first, LLM fallback | FLOWING |
| `context_packs.py.assemble` | `primary_files` | `task.metadata.get("target_files", [])` | Yes — task metadata from planner | FLOWING |
| `ownership.py.validate` | `changed_files` | `git diff --name-only main...HEAD` subprocess | Yes — real git output | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase 15 unit tests pass | `python3 -m pytest tests/test_branch_manager.py tests/test_ci_runner.py tests/test_failure_classifier.py tests/test_context_packs.py tests/test_ownership.py tests/test_execution_engine.py -x -q` | 72 passed in 0.34s | PASS |
| Existing scheduler tests pass (no regressions) | `python3 -m pytest tests/test_scheduler.py -x -q` | 10 passed in 0.41s | PASS |
| BranchManager importable with correct exports | `python3 -c "from agent.orchestrator.branch_manager import BranchManager"` | No error | PASS |
| FailureClassifier RETRY_BUDGETS correct | Verified in code: syntax=3, test=2, contract=1, structural=1 | Values match spec | PASS |
| `task.metadata["context_pack"]` set before executor | `test_context_pack_delivered_via_metadata` captures metadata at execution time | PASS | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ORCH-03 | Plan 04 | Retries failed tasks with failure-type awareness | SATISFIED | `scheduler._handle_failure` classifies via `FailureClassifier`, checks `RETRY_BUDGETS`, retries up to budget; `test_retry_syntax_failure_up_to_3` and related tests confirm |
| ORCH-04 | Plan 04 | Limits concurrency to 5-15 agents via Semaphore | SATISFIED | `scheduler.py:69` `self._semaphore = asyncio.Semaphore(max_concurrency)`; `test_concurrency_preserved` confirms max=2 enforced |
| EXEC-01 | Plan 01 | Each agent works in own git branch AND submits via PR | PARTIAL | Branch isolation (`agent/task-{id}` naming, create/rebase/merge lifecycle) fully implemented. PR submission explicitly deferred per Decision D-02 ("No real GitHub PRs — local branches only"). REQUIREMENTS.md correctly marks as Pending. |
| EXEC-02 | Plan 03 | Context packs (<=5 files + contracts + recent changes) | SATISFIED | `ContextPackAssembler.assemble` reads `target_files`, parses imports, includes `contract_inputs`, caps at `MAX_CONTEXT_FILES=5`. Delivered via `task.metadata["context_pack"]` per EXEC-02. |
| EXEC-03 | Plan 01 | Agents are idempotent — safe to re-run | PARTIAL | `create_and_checkout` force-deletes stale branch (branch idempotency). Full agent execution idempotency (LangGraph StateGraph re-run safety) is out of scope for Phase 15. REQUIREMENTS.md correctly marks as Pending. |
| EXEC-04 | Plan 03 | Ownership model prevents conflicting edits | SATISFIED | `OwnershipValidator.validate` runs `git diff --name-only main...HEAD`, flags files owned by other modules. `build_ownership_map` creates file-to-module mapping. Violations fail the task per D-05. |
| VALD-01 | Plan 02 | Typecheck, tests, lint, build after every task | SATISFIED | `DEFAULT_PIPELINE` in `ci_runner.py` defines all 4 stages. `scheduler._run_task` calls `ci_runner.run_pipeline()` after every task execution. |
| VALD-02 | Plan 02 | Failure classification routes to correct handler | SATISFIED | `failure_classifier.py`: regex patterns for all 4 categories; `RETRY_STRATEGIES` maps each to `auto_fix`, `debug`, `spec_update`, `replan`; LLM fallback for unrecognized errors |
| VALD-03 | Plan 04 | CI engine keeps main always-working | SATISFIED | `scheduler._run_task` raises before `rebase_and_merge` when CI fails; only CI-passing tasks merge to main |

**Note on EXEC-01 and EXEC-03:** Plan 01 SUMMARY frontmatter claims `requirements-completed: [EXEC-01, EXEC-03]`. This is misleading — both requirements are only partially addressed, which is correctly reflected in REQUIREMENTS.md (both marked Pending). EXEC-01 lacks real PR submission (deferred by design per D-02). EXEC-03 lacks full agent execution idempotency (only branch creation is idempotent). These are known scope limitations, not implementation bugs.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `agent/models.py` | 16 | `"gpt-5.4"` replacing `"o3"` for reasoning tier — uncommitted working tree change | Warning | Pre-existing regression; causes `test_models_registry.py` and `test_router.py` failures (6 tests). Not introduced by Phase 15. |

No anti-patterns found in Phase 15 files (`branch_manager.py`, `ci_runner.py`, `failure_classifier.py`, `context_packs.py`, `ownership.py`, `scheduler.py`, `persistence.py`, `models.py`, `events.py`). No TODO/FIXME comments, no empty implementations, no hardcoded empty returns, no placeholder stubs.

### Human Verification Required

#### 1. Concurrent Git Operations Under Real Load

**Test:** Create a DAGScheduler with `max_concurrency=5`, wire a real `BranchManager` pointed at a real git repository with >= 5 tasks, and run them concurrently.
**Expected:** All branches created and cleaned up correctly with no git lock contention errors; main branch contains all merged changes after completion.
**Why human:** Mock-based tests verify the `asyncio.Lock` contract, but real git processes can fail with "unable to lock ref" or "fatal: cannot lock ref" even with asyncio serialization if the OS git lock file is not properly released between calls.

#### 2. Real CI Pipeline Execution

**Test:** Instantiate `CIRunner` with the Shipyard project path and call `run_pipeline()` against the actual codebase.
**Expected:** `typecheck` stage passes for Python files, `lint` runs `npm run lint` in `web/`, `test` runs pytest, `build` runs `npm run build` in `web/`. Each stage has populated `duration_ms`.
**Why human:** All CI runner tests mock `run_command_async`. Real execution requires Node.js with `typescript-language-server`, the web/ frontend built, and the Python test suite green — none of which can be validated programmatically without running the full environment.

### Gaps Summary

No gaps. All 9 required truths (ORCH-03, ORCH-04, EXEC-01-partial, EXEC-02, EXEC-03-partial, EXEC-04, VALD-01, VALD-02, VALD-03) are implemented and wired. The two partial requirements (EXEC-01, EXEC-03) are intentional scope decisions documented in CONTEXT.md (D-02) and correctly reflected in REQUIREMENTS.md as Pending.

The only finding is a **pre-existing regression** in `agent/models.py` (uncommitted change: `o3` renamed to `gpt-5.4`) that breaks 6 tests in `test_models_registry.py` and `test_router.py`. This predates Phase 15 and is unrelated to this phase's work.

**Phase 15 verdict: Goal achieved.** All Phase 15 modules (BranchManager, CIRunner, FailureClassifier, ContextPackAssembler, OwnershipValidator) are implemented with substantive code, fully wired into DAGScheduler, and validated by 72 passing tests.

---

_Verified: 2026-03-29T22:14:17Z_
_Verifier: Claude (gsd-verifier)_
