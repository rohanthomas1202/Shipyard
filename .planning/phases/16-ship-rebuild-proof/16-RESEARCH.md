# Phase 16: Ship Rebuild Proof - Research

**Researched:** 2026-03-29
**Domain:** End-to-end autonomous pipeline execution + Railway deployment automation
**Confidence:** MEDIUM

## Summary

Phase 16 is an integration/proof phase, not a feature-building phase. It exercises the pipeline built in Phases 12-15 (analyzer, planner, DAG scheduler, execution engine, CI runner) against the real Ship app (133K LOC Express/React/Prisma monorepo) and deploys the rebuilt output to a public Railway URL. The primary risk is not code to write -- it is glue code and configuration that connects existing modules into an end-to-end flow, plus a deployment script.

The existing pipeline has all core modules: `analyze_codebase()` produces a `ModuleMap`, `run_pipeline()` generates PRD -> Tech Spec -> Task DAG, `build_orchestrator_dag()` converts planner output to a `TaskDAG`, and `DAGScheduler.run()` executes tasks with branch isolation, CI gating, and failure-aware retries. What is missing is: (1) a top-level orchestration script that chains these together end-to-end, (2) a real task executor that invokes the LangGraph agent graph (currently only a test executor exists), (3) Railway deployment automation, (4) API smoke tests and Playwright E2E tests for the rebuilt Ship, and (5) a Ship-specific CI pipeline configuration (the current `DEFAULT_PIPELINE` targets Shipyard, not a rebuilt Express/React app).

**Primary recommendation:** Build a `scripts/ship_rebuild.py` orchestration script and a `scripts/deploy_railway.py` deployment script. Create a Ship-specific CI pipeline. Write API smoke tests and Playwright E2E tests targeting the rebuilt app. The task executor bridges the LangGraph agent graph to the DAG scheduler.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Focus on core workflows (auth, CRUD, navigation) rather than all 47 routes. The pipeline's analyzer determines which routes are highest-impact -- no manual route list.
- **D-02:** "Core pass = ship it" -- if auth + CRUD + nav work and the UI renders, that's a pass. Non-critical route failures are acceptable for the demo.
- **D-03:** Full analyze-then-execute pipeline: clone Ship from GitHub -> analyze -> generate task DAG -> execute in parallel. This is what Phases 12-15 built -- use it as designed.
- **D-04:** Output is a fresh git repo (clean slate). Proves the pipeline can generate a working app from scratch, not just modify existing code.
- **D-05:** If the pipeline hits a wall, trust the failure classification + retry engine from Phase 15. No manual intervention unless the system is truly stuck.
- **D-06:** Deploy to Railway. Fully automated -- pipeline generates deploy scripts, provisions DB/secrets via Railway CLI, pushes, and verifies the URL responds.
- **D-07:** Secrets and environment config managed through Railway environment variables, provisioned automatically from a template during deploy.
- **D-08:** Belt and suspenders -- API smoke tests for route coverage (status codes + response shapes) AND Playwright E2E tests for user workflow coverage (signup, login, CRUD, navigation).
- **D-09:** Demo bar is "Green CI + live URL" -- all automated tests pass, and the live app is clickable in a browser. The demo shows both.

### Claude's Discretion
- Which specific Ship routes to prioritize (analyzer decides based on codebase analysis)
- E2E test framework details (Playwright preferred per existing Shipyard setup)
- Railway project configuration specifics
- How to handle Ship's specific tech stack dependencies during rebuild

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SHIP-01 | System rebuilds Ship's 47 API routes as functional endpoints | Pipeline (analyzer -> planner -> scheduler) generates and executes tasks to rebuild routes. Analyzer determines priority; D-01 allows partial coverage with core pass. |
| SHIP-02 | Core user workflows pass E2E tests | Playwright E2E tests targeting rebuilt app at localhost + deployed URL. Covers signup, login, CRUD, navigation. |
| SHIP-03 | UI renders without critical errors | Playwright smoke test: page loads, no console errors, key elements visible. CI build stage validates frontend compiles. |
| SHIP-04 | Rebuilt Ship deployed to a public URL | Railway CLI (`railway up`) with automated project setup, variable provisioning, and domain assignment. |
| SHIP-05 | Automated deployment scripts handle the full deploy pipeline | `scripts/deploy_railway.py` wraps Railway CLI commands: init project, set variables, deploy, verify health endpoint. |
</phase_requirements>

## Standard Stack

### Core (Existing -- No New Libraries)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LangGraph | 1.1.3 | Agent graph execution (existing) | Already committed, Phase 12-15 pipeline built on it |
| NetworkX | (transitive) | DAG scheduling (existing) | Already used by TaskDAG |
| FastAPI | >=0.115.0 | Server endpoints (existing) | Already committed |
| Playwright | 1.58.2 | E2E browser tests for rebuilt Ship | Already in web/package.json devDependencies |
| pytest | >=8.0 | API smoke tests | Already in devDependencies |
| httpx | >=0.28.0 | HTTP client for API smoke tests | Already a dependency |
| Railway CLI | 4.33.0 | Deployment automation | Already installed on system |

### Supporting (New scripts only, no new packages)
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `scripts/ship_rebuild.py` | Top-level orchestration: clone -> analyze -> plan -> execute | Entry point for the full rebuild |
| `scripts/deploy_railway.py` | Railway deployment: init -> vars -> deploy -> verify | After successful rebuild |
| `tests/test_ship_smoke.py` | API smoke tests against rebuilt Ship routes | Post-rebuild validation |
| `web/e2e/ship-rebuild.spec.ts` | Playwright E2E for core Ship workflows | Post-rebuild + post-deploy validation |

**Installation:** No new packages needed. All dependencies already present.

## Architecture Patterns

### Recommended Project Structure
```
scripts/
  ship_rebuild.py          # End-to-end orchestration script
  deploy_railway.py        # Railway deployment automation
  railway_template.env     # Environment variable template for Ship on Railway
tests/
  test_ship_smoke.py       # API smoke tests for rebuilt Ship routes
  test_rebuild_pipeline.py # Integration test for the full pipeline
web/
  e2e/
    ship-rebuild.spec.ts   # Playwright E2E tests for rebuilt Ship
```

### Pattern 1: End-to-End Orchestration Script
**What:** A single Python script that chains clone -> analyze -> plan -> execute -> validate.
**When to use:** This is the primary entry point for Phase 16.
**Key insight:** The script stitches existing modules together -- it does NOT reimplement pipeline logic.

```python
# scripts/ship_rebuild.py (simplified flow)
async def run_ship_rebuild(ship_repo_url: str, output_dir: str):
    # 1. Clone Ship from GitHub
    await run_command_async(["git", "clone", ship_repo_url, clone_dir])

    # 2. Initialize fresh output repo
    os.makedirs(output_dir, exist_ok=True)
    await run_command_async(["git", "init"], cwd=output_dir)

    # 3. Analyze Ship codebase
    router = ModelRouter()
    module_map = await analyze_codebase(clone_dir, router)

    # 4. Generate task DAG via planner pipeline
    pipeline_result = await run_pipeline(module_map, router)

    # 5. Convert to orchestrator DAG
    dag = build_orchestrator_dag(pipeline_result.dag, dag_id="ship-rebuild")
    dag_run = DAGRun(id="ship-rebuild", project_id="ship", total_tasks=dag.task_count)

    # 6. Execute with real agent executor
    scheduler = DAGScheduler(
        dag, dag_run,
        task_executor=build_agent_executor(output_dir, router),
        branch_manager=BranchManager(output_dir),
        ci_runner=CIRunner(output_dir, pipeline=SHIP_CI_PIPELINE),
        failure_classifier=FailureClassifier(router),
        context_assembler=ContextPackAssembler(output_dir),
        ownership_validator=OwnershipValidator(output_dir, build_ownership_map(dag)),
    )
    results = await scheduler.run()
    return results
```

### Pattern 2: Real Task Executor (Bridge to LangGraph Agent)
**What:** An async callable matching `Callable[[str, TaskNode], Awaitable[dict]]` that invokes the LangGraph agent graph with the task's description and context pack.
**When to use:** Replaces `build_test_task_executor` for production runs.
**Key insight:** The executor translates a `TaskNode` into an instruction + working directory, then calls `graph.ainvoke()`.

```python
def build_agent_executor(output_dir: str, router: ModelRouter):
    async def execute(task_id: str, task: TaskNode) -> dict:
        # Build instruction from task description + context
        instruction = task.description or task.label
        context_pack = task.metadata.get("context_pack")

        # Invoke the LangGraph agent graph
        state = {
            "instruction": instruction,
            "working_directory": output_dir,
            "context": {"spec": ..., "schema": ...},  # from contracts
            # ... minimal AgentState fields
        }
        result = await graph.ainvoke(state, config={"configurable": {"router": router}})

        if result.get("error_state"):
            raise RuntimeError(result["error_state"])
        return {"success": True, "edits": len(result.get("edit_history", []))}
    return execute
```

### Pattern 3: Ship-Specific CI Pipeline
**What:** Custom `CIStage` list for validating a rebuilt Express/React/Prisma app (not Shipyard's own CI).
**When to use:** Passed to `CIRunner` when executing Ship rebuild tasks.

```python
SHIP_CI_PIPELINE = [
    CIStage("typecheck", ["npx", "tsc", "--noEmit"], timeout=60),
    CIStage("lint", ["npx", "eslint", "src/", "--max-warnings=0"], timeout=60),
    CIStage("test", ["npm", "test", "--", "--watchAll=false"], timeout=180),
    CIStage("build", ["npm", "run", "build"], timeout=120),
]
```

### Pattern 4: Railway Deployment Script
**What:** Python script wrapping Railway CLI for fully automated deployment.
**When to use:** After rebuild passes CI.

```python
# scripts/deploy_railway.py (simplified)
async def deploy_to_railway(project_dir: str, env_template: str):
    # 1. Create Railway project (or link existing)
    await run_command_async(["railway", "init"], cwd=project_dir)

    # 2. Set environment variables from template
    with open(env_template) as f:
        for line in f:
            key, val = line.strip().split("=", 1)
            await run_command_async(
                ["railway", "variable", "set", f"{key}={val}"],
                cwd=project_dir,
            )

    # 3. Deploy
    result = await run_command_async(
        ["railway", "up", "--detach", "--ci"],
        cwd=project_dir, timeout=300,
    )

    # 4. Generate domain
    await run_command_async(["railway", "domain"], cwd=project_dir)

    # 5. Verify health endpoint
    # Poll the deployed URL until it responds with 200
```

### Anti-Patterns to Avoid
- **Building new pipeline modules:** Phase 16 exercises existing Phases 12-15 code. Do not rewrite the analyzer, planner, or scheduler.
- **Manual route selection:** D-01 says the analyzer decides which routes matter. Do not hardcode a route list.
- **Modifying Shipyard's own CI pipeline:** Ship's CI pipeline is separate from Shipyard's. Create a new `SHIP_CI_PIPELINE`, don't modify `DEFAULT_PIPELINE`.
- **Deploying Shipyard to Railway:** The deployed app is the rebuilt Ship, not Shipyard itself.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DAG scheduling | Custom task runner | `DAGScheduler` from Phase 12 | Already handles dependencies, retries, concurrency |
| Codebase analysis | Manual file listing | `analyze_codebase()` from Phase 13 | Handles module discovery + LLM enrichment |
| Plan decomposition | Hardcoded task list | `run_pipeline()` from Phase 13 | PRD -> Tech Spec -> Task DAG with validation |
| Git branch isolation | Manual git commands | `BranchManager` from Phase 15 | Handles create/rebase/merge/cleanup with locks |
| CI validation | Inline shell checks | `CIRunner` from Phase 15 | Stage-level tracking with failure output |
| Failure classification | If/else error matching | `FailureClassifier` from Phase 15 | Regex + LLM hybrid with retry budgets |
| Railway deployment | Manual CLI steps | Script wrapping `railway` CLI | Railway CLI 4.33.0 handles all deployment concerns |

**Key insight:** Phase 16 is an integration phase. Every pipeline component already exists. The new code is glue + configuration + tests.

## Common Pitfalls

### Pitfall 1: Test Executor vs Real Executor
**What goes wrong:** The existing DAG endpoint (`/dag/submit`) uses `build_test_task_executor()` which writes dummy content. Running the Ship rebuild through it would produce empty files, not actual code.
**Why it happens:** Phase 12-15 built the pipeline with test executors as placeholders.
**How to avoid:** Build a real `build_agent_executor()` that invokes the LangGraph graph (`graph.ainvoke()`) with task instructions. Wire it into the rebuild script.
**Warning signs:** Output directory has stub files instead of real code.

### Pitfall 2: CI Pipeline Mismatch
**What goes wrong:** `DEFAULT_PIPELINE` runs `python3 -m py_compile` and Shipyard's pytest suite. Ship is an Express/React app needing `tsc`, `eslint`, `npm test`, `npm run build`.
**Why it happens:** CI pipeline was designed for Shipyard, not for arbitrary target projects.
**How to avoid:** Define a `SHIP_CI_PIPELINE` with the correct commands for Ship's tech stack. Pass it to `CIRunner` constructor.
**Warning signs:** CI stages fail immediately with "command not found" or wrong project structure.

### Pitfall 3: Fresh Repo Has No Git History
**What goes wrong:** `BranchManager.create_and_checkout()` does `git checkout main` then creates a branch. A freshly initialized repo has no commits, so `main` doesn't exist yet.
**Why it happens:** D-04 specifies output is a fresh git repo, but BranchManager assumes `main` branch exists.
**How to avoid:** Create an initial commit in the output repo before starting the scheduler (e.g., `git commit --allow-empty -m "Initial commit"`).
**Warning signs:** First task fails with "fatal: invalid reference: main".

### Pitfall 4: Ship's 133K LOC Overwhelms Context Windows
**What goes wrong:** The analyzer tries to read all files for LLM enrichment. 133K LOC exceeds any model's context window.
**Why it happens:** `analyze_codebase()` reads every file in every module for enrichment.
**How to avoid:** Context packs cap at 5 files (already enforced by `ContextPackAssembler`). The analyzer enriches module-by-module, not the whole codebase at once. But monitor token usage -- the analyzer's per-module enrichment should stay within gpt-4o's 128K window. Very large modules may need to be split.
**Warning signs:** OpenAI API returns token limit errors during analysis phase.

### Pitfall 5: Railway Authentication
**What goes wrong:** `railway init` and `railway up` fail because the CLI is not logged in.
**Why it happens:** Railway CLI requires authentication (`railway login`) before any project operations.
**How to avoid:** Script should check `railway whoami` first and fail fast with a clear message if not authenticated. Authentication is a manual prerequisite, not something the script automates.
**Warning signs:** "Not logged in" error from Railway CLI.

### Pitfall 6: TaskDAG.from_definition Mutates Input
**What goes wrong:** `t.pop("id")` in `from_definition()` mutates the input dicts.
**Why it happens:** Known issue documented in Phase 13 decisions.
**How to avoid:** `build_orchestrator_dag()` in `dag_builder.py` already copies dicts. Use that function, don't call `from_definition()` directly.
**Warning signs:** KeyError on second access to task dict.

### Pitfall 7: Express App Needs node_modules
**What goes wrong:** The rebuilt Ship app has no `node_modules/` directory. All npm commands fail.
**Why it happens:** The agent generates source files but may not run `npm install`.
**How to avoid:** Ensure a task early in the DAG (or the rebuild script itself) runs `npm install` in the output directory after `package.json` is created. The CI pipeline's first stage should also check for this.
**Warning signs:** "Module not found" errors in CI or at runtime.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (Python) + Playwright 1.58.2 (E2E) |
| Config file | `pyproject.toml` (pytest), `web/playwright.config.ts` (Playwright) |
| Quick run command | `python3 -m pytest tests/test_ship_smoke.py -x -q` |
| Full suite command | `python3 -m pytest tests/test_ship_smoke.py tests/test_rebuild_pipeline.py -x -q && npx playwright test web/e2e/ship-rebuild.spec.ts` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SHIP-01 | API routes respond correctly | smoke | `python3 -m pytest tests/test_ship_smoke.py -x -q` | Wave 0 |
| SHIP-02 | Core workflows pass E2E | e2e | `npx playwright test web/e2e/ship-rebuild.spec.ts` | Wave 0 |
| SHIP-03 | UI renders without errors | e2e | `npx playwright test web/e2e/ship-rebuild.spec.ts --grep "renders"` | Wave 0 |
| SHIP-04 | Deployed to public URL | smoke | `python3 -m pytest tests/test_ship_smoke.py::test_deployed_url -x -q` | Wave 0 |
| SHIP-05 | Deploy scripts work | integration | `python3 -m pytest tests/test_rebuild_pipeline.py::test_deploy_script -x -q` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_ship_smoke.py -x -q`
- **Per wave merge:** Full suite including E2E
- **Phase gate:** Full suite green + live URL responding before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ship_smoke.py` -- API smoke tests for rebuilt Ship routes (covers SHIP-01, SHIP-04)
- [ ] `tests/test_rebuild_pipeline.py` -- Integration test for orchestration script (covers SHIP-05)
- [ ] `web/e2e/ship-rebuild.spec.ts` -- Playwright E2E for core workflows (covers SHIP-02, SHIP-03)

## Code Examples

### Orchestration Script Entry Point
```python
# scripts/ship_rebuild.py
"""End-to-end Ship rebuild orchestration script."""
import asyncio
import logging
import os
import sys
from pathlib import Path

from agent.analyzer.analyzer import analyze_codebase
from agent.planner_v2.pipeline import run_pipeline
from agent.planner_v2.dag_builder import build_orchestrator_dag
from agent.orchestrator.scheduler import DAGScheduler
from agent.orchestrator.models import DAGRun
from agent.orchestrator.branch_manager import BranchManager
from agent.orchestrator.ci_runner import CIRunner, CIStage
from agent.orchestrator.failure_classifier import FailureClassifier
from agent.orchestrator.context_packs import ContextPackAssembler
from agent.orchestrator.ownership import OwnershipValidator, build_ownership_map
from agent.router import ModelRouter
from agent.tools.shell import run_command_async

logger = logging.getLogger(__name__)

SHIP_REPO_URL = "https://github.com/{owner}/ship.git"  # Fill in actual URL

SHIP_CI_PIPELINE = [
    CIStage("typecheck", ["npx", "tsc", "--noEmit"], timeout=60),
    CIStage("lint", ["npx", "eslint", "src/"], timeout=60),
    CIStage("test", ["npm", "test", "--", "--watchAll=false"], timeout=180),
    CIStage("build", ["npm", "run", "build"], timeout=120),
]


async def main():
    ship_clone_dir = "/tmp/ship-source"
    output_dir = "/tmp/ship-rebuilt"

    # Clone
    await run_command_async(["git", "clone", SHIP_REPO_URL, ship_clone_dir])

    # Init fresh output repo
    os.makedirs(output_dir, exist_ok=True)
    await run_command_async(["git", "init"], cwd=output_dir)
    await run_command_async(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=output_dir)

    # Analyze
    router = ModelRouter()
    module_map = await analyze_codebase(ship_clone_dir, router)
    logger.info("Analyzed %d modules", len(module_map.modules))

    # Plan
    pipeline_result = await run_pipeline(module_map, router)
    logger.info("Generated %d tasks", len(pipeline_result.dag.tasks))

    # Build orchestrator DAG
    dag = build_orchestrator_dag(pipeline_result.dag, dag_id="ship-rebuild")
    dag_run = DAGRun(id="ship-rebuild", project_id="ship", total_tasks=dag.task_count)

    # Execute
    scheduler = DAGScheduler(
        dag, dag_run,
        task_executor=build_agent_executor(output_dir, router),
        branch_manager=BranchManager(output_dir),
        ci_runner=CIRunner(output_dir, pipeline=SHIP_CI_PIPELINE),
        failure_classifier=FailureClassifier(router),
        context_assembler=ContextPackAssembler(output_dir),
        max_concurrency=10,
    )
    results = await scheduler.run()

    completed = sum(1 for s in results.values() if s == "completed")
    failed = sum(1 for s in results.values() if s == "failed")
    logger.info("Rebuild complete: %d/%d tasks succeeded, %d failed", completed, dag.task_count, failed)


if __name__ == "__main__":
    asyncio.run(main())
```

### Railway Deployment Script
```python
# scripts/deploy_railway.py
"""Automated Railway deployment for rebuilt Ship app."""
import asyncio
import time
from agent.tools.shell import run_command_async

async def deploy(project_dir: str, env_template: str = "scripts/railway_template.env"):
    # Verify authentication
    whoami = await run_command_async(["railway", "whoami"], cwd=project_dir)
    if whoami["exit_code"] != 0:
        raise RuntimeError("Railway CLI not authenticated. Run 'railway login' first.")

    # Initialize project
    await run_command_async(["railway", "init"], cwd=project_dir)

    # Set environment variables
    with open(env_template) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                await run_command_async(
                    ["railway", "variable", "set", line],
                    cwd=project_dir,
                )

    # Deploy
    result = await run_command_async(
        ["railway", "up", "--detach", "--ci"],
        cwd=project_dir, timeout=300,
    )
    if result["exit_code"] != 0:
        raise RuntimeError(f"Deploy failed: {result['stderr']}")

    # Generate public domain
    domain_result = await run_command_async(["railway", "domain"], cwd=project_dir)
    public_url = domain_result["stdout"].strip()

    # Verify health
    import httpx
    async with httpx.AsyncClient() as client:
        for _ in range(30):  # 5 minutes max
            try:
                resp = await client.get(f"https://{public_url}/health", timeout=10)
                if resp.status_code == 200:
                    return public_url
            except Exception:
                pass
            await asyncio.sleep(10)

    raise RuntimeError(f"Deployed but health check failed after 5 minutes: {public_url}")
```

### API Smoke Test Pattern
```python
# tests/test_ship_smoke.py
"""API smoke tests for rebuilt Ship routes."""
import httpx
import pytest

BASE_URL = "http://localhost:3000"  # or from env

@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_auth_signup():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/api/auth/signup", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "token" in data or "user" in data
```

### Playwright E2E Pattern
```typescript
// web/e2e/ship-rebuild.spec.ts
import { test, expect } from '@playwright/test'

test('Ship UI renders without errors', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(err.message))

  await page.goto('http://localhost:3000')
  await expect(page).toHaveTitle(/.+/)
  await expect(page.locator('body')).toBeVisible()
  expect(errors).toHaveLength(0)
})

test('signup flow works', async ({ page }) => {
  await page.goto('http://localhost:3000/signup')
  await page.fill('[name="email"]', 'test@example.com')
  await page.fill('[name="password"]', 'testpass123')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL(/dashboard|home/)
})
```

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Pipeline execution | Partial | 3.14 (homebrew) | Should work -- but pyproject.toml pins 3.11 |
| Node.js | Ship rebuild + CI | Yes | (via npx 11.9.0) | -- |
| Railway CLI | Deployment (SHIP-04, SHIP-05) | Yes | 4.33.0 | -- |
| Playwright | E2E tests (SHIP-02, SHIP-03) | Yes | 1.58.2 | -- |
| git | Clone + branch management | Yes | 2.50.1 | -- |
| gh CLI | GitHub operations | Yes | 2.87.2 | -- |
| OpenAI API | LLM calls for analyzer/planner/agents | Requires OPENAI_API_KEY | -- | Blocks without key |

**Missing dependencies with no fallback:**
- OpenAI API key must be set in environment (OPENAI_API_KEY) -- blocks all LLM operations
- Railway authentication (`railway login`) must be completed before deployment

**Missing dependencies with fallback:**
- None identified

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Test executor (dummy content) | Real agent executor (LangGraph graph.ainvoke) | Phase 16 | Actually generates code instead of stubs |
| Shipyard CI pipeline | Ship-specific CI pipeline | Phase 16 | Validates Express/React, not Python/Shipyard |
| Manual deployment | Railway CLI automation | Phase 16 | Zero-touch deploy + verify |

## Open Questions

1. **Ship GitHub repo URL**
   - What we know: Ship is a 133K LOC Express/React/Prisma monorepo owned by the user
   - What's unclear: The exact GitHub URL for cloning
   - Recommendation: The orchestration script should accept the URL as a parameter, defaulting to a configurable constant

2. **Ship's Database in Production**
   - What we know: Ship fixture uses Prisma. Production Ship likely uses PostgreSQL.
   - What's unclear: Whether Railway should provision a Postgres addon or use SQLite
   - Recommendation: Railway supports Postgres addons. The deploy script should provision one and set DATABASE_URL.

3. **Agent Executor Fidelity**
   - What we know: The LangGraph agent graph exists and works for single-instruction tasks
   - What's unclear: Whether a single `graph.ainvoke()` per task can reliably generate complete files from scratch (vs editing existing files)
   - Recommendation: Start with the existing graph. If tasks fail on generation (not editing), add a "generate" mode to the editor node that creates files from scratch instead of anchor-based editing.

4. **Railway Project Quotas**
   - What we know: Railway CLI v4.33.0 is installed and functional
   - What's unclear: Whether the user's Railway account has sufficient resources (free tier limits)
   - Recommendation: Deploy script should check project limits and report clearly if quota is exceeded

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `agent/orchestrator/scheduler.py`, `dag.py`, `models.py`
- Direct code inspection of `agent/analyzer/analyzer.py`, `agent/planner_v2/pipeline.py`
- Direct code inspection of `agent/orchestrator/branch_manager.py`, `ci_runner.py`
- Direct code inspection of `agent/orchestrator/failure_classifier.py`, `context_packs.py`
- Direct code inspection of `server/main.py` DAG endpoints (lines 993-1158)
- Direct code inspection of `tests/test_ship_integration.py`, `tests/test_execution_engine.py`
- Direct code inspection of `tests/fixtures/ship_fixture/` (Ship app structure)
- Direct code inspection of `web/playwright.config.ts` (Playwright setup)
- Railway CLI help output (v4.33.0 commands verified locally)

### Secondary (MEDIUM confidence)
- Phase 12-15 CONTEXT.md files for architectural decisions
- `.planning/PROJECT.md` for constraints and decisions

### Tertiary (LOW confidence)
- Ship's exact tech stack details (inferred from fixture, may not match real 133K LOC repo)
- Railway deployment behavior (verified CLI is installed, not tested end-to-end)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, no new dependencies
- Architecture: MEDIUM - orchestration script pattern is clear but agent executor fidelity for code generation (vs editing) is unvalidated
- Pitfalls: HIGH - identified from direct code inspection of existing modules
- Deployment: MEDIUM - Railway CLI available and verified, but end-to-end deploy untested

**Research date:** 2026-03-29
**Valid until:** 2026-04-15 (stable -- existing pipeline, no fast-moving dependencies)
