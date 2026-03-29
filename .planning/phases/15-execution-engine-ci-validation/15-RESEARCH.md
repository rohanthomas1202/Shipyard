# Phase 15: Execution Engine + CI Validation - Research

**Researched:** 2026-03-29
**Domain:** Parallel agent execution, git branch isolation, failure classification, local CI pipeline
**Confidence:** HIGH

## Summary

Phase 15 builds the execution engine that runs 5-15 agents concurrently with git branch isolation, module ownership enforcement, failure-aware retry budgets, and a local CI gate that keeps main always green. The existing DAGScheduler already provides async worker pools with semaphore-based concurrency, event emission, and crash recovery via SQLite persistence. The core work is extending `_run_task()` with branch lifecycle management, adding failure classification and tiered retry logic, building a context pack assembler, implementing ownership validation, and creating a local CI runner module.

All decisions are locked in CONTEXT.md: local git branches (no GitHub PRs), fail-and-requeue on merge conflicts, hybrid context packs, soft ownership enforcement via validator, hybrid failure classification (regex + LLM), tiered retry budgets, local CI runner, and fast-forward-only merge policy. No alternative approaches need consideration.

**Primary recommendation:** Extend the existing DAGScheduler._run_task() with a branch-create/execute/CI-validate/merge pipeline, adding new modules for branch management, failure classification, context packs, ownership validation, and CI running -- all following the established Pydantic model + asyncio + EventBus patterns.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Per-task branches with auto-merge -- each task gets `agent/task-{id}` branch, CI runs on it, auto-merges to main on green. No accumulation branches.
- **D-02:** Local git branch + merge -- no real GitHub PRs. Local branches provide the same isolation and merge semantics without network latency or API rate limits. Real PRs can be added later for human-reviewed milestones.
- **D-03:** Fail-and-requeue on merge conflicts -- if two agents edit adjacent code, the later agent fails, gets requeued with updated base (main now has the conflicting changes merged). No LLM merge (unpredictable), no file locking (kills parallelism). DAG scheduler already handles requeueing.
- **D-04:** Hybrid context pack assembly -- Planner picks primary files (knows task intent), Analyzer adds transitive dependencies from import graph (knows module structure). Neither alone is sufficient.
- **D-05:** Soft enforcement via validator -- agent writes freely, validator checks the diff against the module ownership map, rejects unauthorized file changes. No filesystem sandboxing (complex for marginal benefit), no self-policing (LLMs unreliable at constraints). Simple, reliable, debuggable.
- **D-06:** Hybrid classification -- rule-based regex patterns on error output first (fast, deterministic for common patterns like syntax errors, test failures), LLM fallback (gpt-4o-mini) for novel/ambiguous errors. Matches existing ModelRouter escalation pattern.
- **D-07:** Tiered retry budget -- 3 retries for syntax (auto-fix, high fix probability), 2 for test failures (may need different approach), 1 for contract/structural (planning problem, not execution problem -- escalate to replanning). Different failure types have fundamentally different fix probabilities.
- **D-08:** Local CI runner module -- structured pipeline definition (typecheck -> lint -> test -> build) with stage-level pass/fail reporting that feeds into the failure heatmap from Phase 14. Subprocess-based but with proper stage tracking. No GitHub Actions dependency.
- **D-09:** Fast-forward only merge policy -- each task rebases on latest main before merge. Guarantees linear history, every CI run reflects true state, easier to bisect. No merge commits, no squash.

### Claude's Discretion
- Branch naming convention details (e.g., `agent/task-{id}` vs `agent/{dag_id}/task-{id}`)
- Context pack file selection algorithm (how Analyzer scores transitive dependencies for relevance)
- Failure classification regex patterns for each error category
- CI pipeline stage ordering and timeout configuration
- How rebase-on-main integrates with the scheduler's task queue
- Ownership map data structure (from module map -> which agent owns which files)
- How the CI runner reports results back to the scheduler/EventBus

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-03 | Orchestrator retries failed tasks with failure-type awareness (A/B/C/D classification) | Failure classifier module + tiered retry budget (D-06, D-07). Extend TaskExecution with retry_count, failure_type fields. |
| ORCH-04 | Orchestrator limits concurrency to 5-15 agents with queue-based scheduling | Already implemented via asyncio.Semaphore in DAGScheduler. Verify max_concurrency param wired through. |
| EXEC-01 | Each agent works in its own git branch and submits changes via PR | Branch manager module creates/checkouts per-task branches, merges locally (D-01, D-02). |
| EXEC-02 | Agents receive context packs (<=5 relevant files + contracts + recent changes) | Context pack assembler using task metadata + import graph (D-04). |
| EXEC-03 | Agents are idempotent -- safe to re-run without corrupting state | Branch cleanup on retry (delete old branch, create fresh from main), no shared mutable state between agents. |
| EXEC-04 | Module ownership model prevents conflicting edits across agents | Ownership validator checks git diff against ownership map, rejects unauthorized changes (D-05). |
| VALD-01 | Type checks, tests, lint, and build verification run after every task | Local CI runner with 4-stage pipeline (D-08). |
| VALD-02 | Failure classification routes errors to appropriate handler | Hybrid regex + LLM classifier (D-06) with 4 categories matching DecisionTrace.error_category. |
| VALD-03 | CI engine maintains always-working main branch, rejecting unstable merges | Fast-forward merge gated on CI pass (D-09). Rebase before merge ensures linear history. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib | Concurrent task execution, subprocess management | Already used throughout scheduler |
| subprocess (via shell.py) | stdlib | CI pipeline stage execution | Existing run_command_async() pattern |
| git (CLI) | 2.50.1 | Branch creation, rebase, merge, diff | Installed, already used by git_ops_node |
| networkx | (existing) | DAG dependency graph | Already in TaskDAG |
| pydantic | (existing) | Data models for all new types | Project convention |
| aiosqlite | >=0.20.0 | Persistence for retry state, CI results | Already in DAGPersistence |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re | stdlib | Regex-based failure classification | First-pass error categorization before LLM |
| openai (via router) | >=1.60.0 | LLM fallback for novel error classification | When regex patterns don't match |

### Alternatives Considered
None -- all decisions are locked. No new external dependencies needed.

**Installation:**
No new packages required. All functionality builds on existing stdlib + project dependencies.

## Architecture Patterns

### Recommended Project Structure
```
agent/orchestrator/
  branch_manager.py     # Git branch lifecycle (create, checkout, rebase, merge, cleanup)
  ci_runner.py          # Local CI pipeline (typecheck, lint, test, build stages)
  failure_classifier.py # Hybrid regex + LLM error classification
  context_packs.py      # Context pack assembly for agent execution
  ownership.py          # Module ownership map + diff validation
  scheduler.py          # EXTENDED: branch isolation, retry, CI gating in _run_task()
  models.py             # EXTENDED: new fields on TaskExecution, new CI/retry models
  events.py             # EXTENDED: CI_STARTED, CI_PASSED, CI_FAILED events
  persistence.py        # EXTENDED: retry state, CI result persistence
```

### Pattern 1: Branch-Isolated Task Execution
**What:** Each task runs inside a dedicated git branch. The scheduler wraps task execution with branch create -> execute -> CI validate -> merge-to-main.
**When to use:** Every task in the DAG.
**Example:**
```python
async def _run_task_with_isolation(self, task_id: str) -> None:
    """Extended _run_task with branch isolation and CI gating."""
    branch_name = f"agent/task-{task_id}"

    # 1. Create branch from latest main
    await self._branch_manager.create_branch(branch_name, base="main")
    await self._branch_manager.checkout(branch_name)

    try:
        # 2. Execute task (agent graph invocation)
        result = await self._task_executor(task_id, task)

        # 3. Run CI pipeline on branch
        ci_result = await self._ci_runner.run_pipeline(branch_name, self._project_path)

        if ci_result.passed:
            # 4. Rebase on latest main and merge
            rebase_ok = await self._branch_manager.rebase_on_main(branch_name)
            if not rebase_ok:
                raise MergeConflictError(task_id)
            await self._branch_manager.fast_forward_merge(branch_name)
        else:
            # 5. Classify failure and decide retry strategy
            failure_type = await self._classifier.classify(ci_result.error_output)
            raise TaskCIFailure(task_id, failure_type, ci_result)
    finally:
        # 6. Always return to main, cleanup branch
        await self._branch_manager.checkout("main")
        await self._branch_manager.delete_branch(branch_name)
```

### Pattern 2: Tiered Retry with Failure Classification
**What:** Failed tasks are classified into 4 categories, each with different retry budgets and strategies.
**When to use:** On any task failure (CI or execution).
**Example:**
```python
RETRY_BUDGETS: dict[str, int] = {
    "syntax": 3,     # Auto-fix, high success probability
    "test": 2,       # May need different approach
    "contract": 1,   # Planning problem -- escalate
    "structural": 1, # Planning problem -- escalate
}

RETRY_STRATEGIES: dict[str, str] = {
    "syntax": "auto_fix",       # Re-run with error context
    "test": "debug",            # Re-run with test output + hints
    "contract": "spec_update",  # Update contract, replan
    "structural": "replan",     # Full replan of task
}
```

### Pattern 3: Local CI Pipeline
**What:** Sequential stage execution (typecheck -> lint -> test -> build) with per-stage pass/fail tracking.
**When to use:** After every task completes, before merge to main.
**Example:**
```python
@dataclass
class CIStage:
    name: str
    command: list[str]
    timeout: int = 120

CI_PIPELINE: list[CIStage] = [
    CIStage("typecheck", ["python3", "-m", "py_compile"], timeout=30),
    CIStage("lint", ["npm", "run", "lint"], timeout=60),
    CIStage("test", ["python3", "-m", "pytest", "--tb=short", "-x"], timeout=180),
    CIStage("build", ["npm", "run", "build"], timeout=120),
]
```

### Pattern 4: Context Pack Assembly
**What:** Build a scoped file set for each agent from task metadata + transitive imports.
**When to use:** Before invoking the agent executor for a task.
**Example:**
```python
@dataclass
class ContextPack:
    task_id: str
    primary_files: list[str]        # From task metadata (planner-selected)
    dependency_files: list[str]     # From import graph analysis
    contracts: list[str]            # From task.contract_inputs
    recent_changes: list[str]       # Files changed by recently-merged tasks

    @property
    def all_files(self) -> list[str]:
        """Deduplicated, capped at limit."""
        seen: set[str] = set()
        result: list[str] = []
        for f in self.primary_files + self.dependency_files + self.contracts:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return result[:5]  # <=5 files per EXEC-02
```

### Anti-Patterns to Avoid
- **Shared working directory:** Never let two agents operate in the same git worktree simultaneously. Each agent needs its own branch checkout. Since this is single-process, serialize git operations with an asyncio.Lock.
- **LLM-based merge conflict resolution:** Decision D-03 explicitly rejects this. Fail and requeue instead.
- **Filesystem sandboxing:** Decision D-05 rejects this. Use post-hoc diff validation instead.
- **Polling for task completion:** The scheduler already uses asyncio.Event for wake-on-completion. Don't add polling.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Git operations | Custom git protocol implementation | `git` CLI via `run_command_async()` | CLI is battle-tested, handles edge cases (rebase conflicts, branch cleanup) |
| Failure regex patterns | One massive regex | Pattern list per category, checked sequentially | Maintainable, extensible, debuggable |
| Concurrency control | Custom locking primitives | `asyncio.Semaphore` (already exists) + `asyncio.Lock` for git ops | stdlib is correct by construction |
| DAG requeue | Custom queue data structure | Extend existing TaskDAG + DAGScheduler state sets | Already handles completed/failed/running tracking |

**Key insight:** The existing scheduler infrastructure (DAGScheduler, TaskDAG, DAGPersistence, EventBus) is specifically designed for extension. The Phase 15 work is wrapping `_run_task()` with branch/CI/retry logic, not replacing the scheduling core.

## Common Pitfalls

### Pitfall 1: Git Race Conditions in Single Worktree
**What goes wrong:** Two concurrent tasks both try to checkout different branches. Git rejects the second checkout because the worktree is dirty.
**Why it happens:** asyncio runs tasks concurrently in one process with one working directory.
**How to avoid:** Use an asyncio.Lock for ALL git operations (checkout, rebase, merge). Serialize git mutations while allowing task execution (LLM calls) to remain parallel. The semaphore limits concurrent _executions_, the lock serializes _git state changes_.
**Warning signs:** "fatal: cannot switch branches" or "error: Your local changes would be overwritten" in CI output.

### Pitfall 2: Stale Main After Concurrent Merges
**What goes wrong:** Task A merges to main. Task B, which started before A merged, rebases on stale main and gets conflicts.
**Why it happens:** Fast-forward merge changes main's HEAD between rebase and merge.
**How to avoid:** Hold the git lock through the entire rebase-then-merge sequence. Check that HEAD hasn't moved between rebase completion and ff-merge. If it has, re-rebase.
**Warning signs:** "fatal: Not possible to fast-forward" errors.

### Pitfall 3: Retry Without Branch Cleanup
**What goes wrong:** A retried task tries to create a branch that already exists from the failed attempt.
**Why it happens:** The failed branch wasn't cleaned up before retry.
**How to avoid:** Always delete the task branch in the finally block of _run_task, and verify branch doesn't exist before creating. Use `git branch -D` (force delete) to handle partially-merged branches.
**Warning signs:** "fatal: A branch named 'agent/task-X' already exists."

### Pitfall 4: CI Running Against Wrong Branch
**What goes wrong:** CI runs type checks against main instead of the task branch because checkout didn't complete.
**Why it happens:** Git checkout failed silently or another task switched branches between checkout and CI run.
**How to avoid:** Verify current branch before CI execution (`git rev-parse --abbrev-ref HEAD`). Include branch verification as CI stage 0.
**Warning signs:** CI passes on tasks that should fail, or vice versa.

### Pitfall 5: SQLite Write Contention Under Concurrency
**What goes wrong:** Multiple async tasks try to write persistence updates simultaneously, causing "database is locked" errors.
**Why it happens:** WAL mode handles concurrent reads but serializes writes. Many rapid status updates from parallel tasks can queue up.
**How to avoid:** The existing DAGPersistence uses WAL mode + NORMAL synchronous, which is good. For additional safety, batch persistence updates or use a dedicated writer task with an asyncio.Queue.
**Warning signs:** aiosqlite timeout errors, "database is locked" messages.

### Pitfall 6: Infinite Retry Loops
**What goes wrong:** A task keeps failing with a "novel" error that the LLM classifier categorizes inconsistently, causing retries to exceed budget.
**Why it happens:** LLM classification is non-deterministic. The same error might be classified as "syntax" (3 retries) one time and "test" (2 retries) another.
**How to avoid:** Track total retries regardless of classification. Set an absolute max (e.g., 4) across all categories. Use the FIRST classification for a task, not re-classify on each retry.
**Warning signs:** Tasks stuck in retry loops, retry_count climbing without convergence.

## Code Examples

### Branch Manager Core Operations
```python
# agent/orchestrator/branch_manager.py
"""Git branch lifecycle management for isolated task execution."""
import asyncio
import logging
from agent.tools.shell import run_command_async

logger = logging.getLogger(__name__)

class BranchManager:
    """Manage git branches for task isolation.

    All git operations are serialized via an asyncio.Lock to prevent
    race conditions in the single-worktree environment.
    """

    def __init__(self, project_path: str) -> None:
        self._cwd = project_path
        self._lock = asyncio.Lock()

    async def _git(self, *args: str) -> dict:
        """Run a git command under the lock."""
        result = await run_command_async(
            ["git", *args], cwd=self._cwd, timeout=30,
        )
        if result["exit_code"] != 0:
            logger.warning("git %s failed: %s", args[0], result["stderr"])
        return result

    async def create_and_checkout(self, branch: str, base: str = "main") -> bool:
        """Create a new branch from base and checkout."""
        async with self._lock:
            # Ensure we're on base first
            await self._git("checkout", base)
            # Delete stale branch if exists
            await self._git("branch", "-D", branch)
            # Create and checkout
            result = await self._git("checkout", "-b", branch)
            return result["exit_code"] == 0

    async def rebase_and_merge(self, branch: str) -> bool:
        """Rebase branch on main, then fast-forward merge to main.

        Returns True on success, False on conflict.
        Holds lock through entire operation to prevent HEAD races.
        """
        async with self._lock:
            # Checkout branch
            await self._git("checkout", branch)
            # Rebase on main
            rebase = await self._git("rebase", "main")
            if rebase["exit_code"] != 0:
                await self._git("rebase", "--abort")
                return False
            # Fast-forward merge
            await self._git("checkout", "main")
            merge = await self._git("merge", "--ff-only", branch)
            return merge["exit_code"] == 0

    async def cleanup(self, branch: str) -> None:
        """Delete a task branch after completion or failure."""
        async with self._lock:
            await self._git("checkout", "main")
            await self._git("branch", "-D", branch)
```

### Failure Classifier
```python
# agent/orchestrator/failure_classifier.py
"""Hybrid regex + LLM failure classification."""
import re
from typing import Literal

FailureCategory = Literal["syntax", "test", "contract", "structural"]

# Ordered: check most specific patterns first
_PATTERNS: list[tuple[str, FailureCategory]] = [
    # Syntax errors
    (r"SyntaxError:", "syntax"),
    (r"IndentationError:", "syntax"),
    (r"TabError:", "syntax"),
    (r"TS\d+:", "syntax"),          # TypeScript compiler errors
    (r"error TS\d+", "syntax"),
    (r"Unexpected token", "syntax"),
    (r"unterminated string", "syntax"),

    # Test failures
    (r"FAILED tests/", "test"),
    (r"AssertionError", "test"),
    (r"pytest.*\d+ failed", "test"),
    (r"FAIL\s+.*\.test\.", "test"),
    (r"expected .* to equal", "test"),

    # Contract violations
    (r"ImportError:", "contract"),
    (r"ModuleNotFoundError:", "contract"),
    (r"Cannot find module", "contract"),
    (r"is not assignable to type", "contract"),
    (r"Property .* does not exist on type", "contract"),

    # Structural (catch-all is in LLM fallback)
    (r"RecursionError:", "structural"),
    (r"maximum call stack", "structural"),
    (r"circular dependency", "structural"),
]

def classify_regex(error_output: str) -> FailureCategory | None:
    """Classify error by regex patterns. Returns None if no match."""
    for pattern, category in _PATTERNS:
        if re.search(pattern, error_output, re.IGNORECASE):
            return category
    return None
```

### CI Runner Pipeline
```python
# agent/orchestrator/ci_runner.py
"""Local CI pipeline with stage-level tracking."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent.tools.shell import run_command_async

logger = logging.getLogger(__name__)

@dataclass
class CIStageResult:
    name: str
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

@dataclass
class CIPipelineResult:
    stages: list[CIStageResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.stages)

    @property
    def first_failure(self) -> CIStageResult | None:
        return next((s for s in self.stages if not s.passed), None)

    @property
    def error_output(self) -> str:
        failure = self.first_failure
        if failure is None:
            return ""
        return failure.stderr or failure.stdout

@dataclass
class CIStage:
    name: str
    command: list[str]
    timeout: int = 120
    cwd_suffix: str = ""  # e.g. "web/" for frontend commands

# Default pipeline -- configurable per project
DEFAULT_PIPELINE: list[CIStage] = [
    CIStage("typecheck", ["python3", "-m", "py_compile"], timeout=30),
    CIStage("lint", ["npm", "run", "lint"], timeout=60, cwd_suffix="web/"),
    CIStage("test", ["python3", "-m", "pytest", "--tb=short", "-x", "-q"], timeout=180),
    CIStage("build", ["npm", "run", "build"], timeout=120, cwd_suffix="web/"),
]
```

### Ownership Validator
```python
# agent/orchestrator/ownership.py
"""Module ownership enforcement via post-hoc diff validation."""
from __future__ import annotations

from dataclasses import dataclass
from agent.tools.shell import run_command_async

@dataclass
class OwnershipViolation:
    file_path: str
    owning_module: str | None
    task_module: str
    reason: str

async def validate_ownership(
    task_id: str,
    task_module: str,
    ownership_map: dict[str, str],  # file_path -> module_name
    project_path: str,
) -> list[OwnershipViolation]:
    """Check git diff for files changed outside the task's module ownership."""
    result = await run_command_async(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd=project_path,
        timeout=10,
    )
    if result["exit_code"] != 0:
        return []

    changed_files = result["stdout"].strip().splitlines()
    violations: list[OwnershipViolation] = []

    for file_path in changed_files:
        owner = ownership_map.get(file_path)
        if owner is not None and owner != task_module:
            violations.append(OwnershipViolation(
                file_path=file_path,
                owning_module=owner,
                task_module=task_module,
                reason=f"File belongs to module '{owner}', not '{task_module}'",
            ))

    return violations
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DAGScheduler with no retry | Tiered retry with failure classification | Phase 15 | Failed tasks get intelligent retry instead of permanent failure |
| Single branch execution | Per-task branch isolation | Phase 15 | Agents can't corrupt each other's work |
| No CI gate | Local CI pipeline before merge | Phase 15 | Main branch stays green |
| No ownership enforcement | Post-hoc diff validation | Phase 15 | Agents can't accidentally modify other modules |

## Open Questions

1. **Single worktree vs git worktrees**
   - What we know: Python's `git worktree` command allows multiple checkouts of the same repo. This would eliminate the need for a git lock since each agent could have its own worktree.
   - What's unclear: Whether the overhead of creating/managing 5-15 worktrees is worth the parallelism gain vs. serializing just git operations.
   - Recommendation: Start with single worktree + asyncio.Lock. Git operations are fast (<100ms). The bottleneck is LLM calls (seconds), not git. If profiling shows git serialization as a bottleneck, migrate to worktrees later.

2. **CI pipeline scoping**
   - What we know: Running full test suite + build after every task is thorough but slow.
   - What's unclear: Whether to scope CI to only affected modules (faster but might miss cross-module regressions).
   - Recommendation: Start with full CI. Add scoped CI as optimization if pipeline time exceeds 60s.

3. **Analyzer module doesn't exist yet**
   - What we know: CONTEXT.md references `agent/orchestrator/analyzer.py` for import graph analysis, but this file does not exist. Phase 13 CONTEXT referenced it as a planned output.
   - What's unclear: Whether the analyzer was created outside the orchestrator directory or deferred.
   - Recommendation: Context pack assembly needs a simplified version. Build a basic import parser in `context_packs.py` that extracts Python imports from files. Don't depend on a full analyzer module.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | Branch management | Yes | 2.50.1 | -- |
| Python | CI typecheck, tests | Yes | 3.14.3 | -- |
| Node.js | CI lint, build | Yes | v25.6.1 | -- |
| pytest | CI test stage | Yes | 9.0.2 | -- |
| npm | CI lint/build | Yes | (bundled with Node) | -- |
| asyncio | Concurrency | Yes | stdlib | -- |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `python3 -m pytest tests/test_scheduler.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORCH-03 | Retry with failure-type awareness | unit | `python3 -m pytest tests/test_retry_engine.py -x` | No -- Wave 0 |
| ORCH-04 | Concurrency limit 5-15 | unit | `python3 -m pytest tests/test_scheduler.py::test_concurrency_limit -x` | Yes |
| EXEC-01 | Per-task git branch isolation | integration | `python3 -m pytest tests/test_branch_manager.py -x` | No -- Wave 0 |
| EXEC-02 | Context packs <=5 files | unit | `python3 -m pytest tests/test_context_packs.py -x` | No -- Wave 0 |
| EXEC-03 | Idempotent re-runs | integration | `python3 -m pytest tests/test_idempotent_execution.py -x` | No -- Wave 0 |
| EXEC-04 | Module ownership enforcement | unit | `python3 -m pytest tests/test_ownership.py -x` | No -- Wave 0 |
| VALD-01 | CI pipeline runs 4 stages | unit | `python3 -m pytest tests/test_ci_runner.py -x` | No -- Wave 0 |
| VALD-02 | Failure classification routing | unit | `python3 -m pytest tests/test_failure_classifier.py -x` | No -- Wave 0 |
| VALD-03 | Main stays green (reject unstable) | integration | `python3 -m pytest tests/test_ci_gate.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_scheduler.py tests/test_retry_engine.py tests/test_branch_manager.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_branch_manager.py` -- covers EXEC-01, EXEC-03 (branch create/cleanup/idempotency)
- [ ] `tests/test_ci_runner.py` -- covers VALD-01 (stage execution, pass/fail tracking)
- [ ] `tests/test_failure_classifier.py` -- covers VALD-02 (regex patterns, category routing)
- [ ] `tests/test_context_packs.py` -- covers EXEC-02 (file assembly, cap enforcement)
- [ ] `tests/test_ownership.py` -- covers EXEC-04 (diff validation, violation detection)
- [ ] `tests/test_retry_engine.py` -- covers ORCH-03 (tiered budgets, requeue on conflict)
- [ ] `tests/test_ci_gate.py` -- covers VALD-03 (merge rejection on CI failure)

## Project Constraints (from CLAUDE.md)

- **LLM Provider:** OpenAI only (o3/gpt-4o/gpt-4o-mini). Failure classifier LLM fallback uses gpt-4o-mini via existing ModelRouter.
- **Framework:** LangGraph 1.1.3 -- agent graph invocation unchanged.
- **File editing:** Anchor-based string replacement -- agents still use this within their branches.
- **Observability:** LangSmith tracing required -- new modules must support TraceLogger.
- **Naming:** snake_case.py for modules, PascalCase for classes, UPPER_SNAKE_CASE for constants.
- **Module docstrings:** Required at top of every Python module.
- **Type hints:** Modern Python 3.11+ syntax (str | None, etc.)
- **Error handling:** Follow existing patterns (dict returns with success/error keys for tools).
- **Imports:** Prefer `from X import Y`.
- **Pydantic:** BaseModel for all data models.
- **Testing:** pytest + pytest-asyncio for async tests.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `agent/orchestrator/scheduler.py`, `models.py`, `dag.py`, `persistence.py`, `events.py`, `metrics.py` -- direct code inspection
- Existing codebase: `agent/tools/shell.py` -- run_command_async pattern
- Existing codebase: `agent/parallel.py` -- asyncio.gather pattern for concurrent execution
- Existing codebase: `tests/test_scheduler.py` -- existing test patterns

### Secondary (MEDIUM confidence)
- Git CLI behavior for branch/rebase/merge operations -- well-documented, stable interface
- Python asyncio.Lock semantics for serializing git operations -- stdlib documentation

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing patterns
- Architecture: HIGH -- clear extension points in existing scheduler, locked decisions constrain design
- Pitfalls: HIGH -- git concurrency issues are well-understood, SQLite WAL behavior documented

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable domain, no fast-moving dependencies)
