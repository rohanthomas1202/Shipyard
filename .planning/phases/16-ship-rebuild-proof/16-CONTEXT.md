# Phase 16: Ship Rebuild Proof - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Run Shipyard's autonomous pipeline (Phases 12-15) against the real Ship app (133K LOC) to rebuild its core functionality into a fresh repo and deploy to a public Railway URL. This phase proves the system works end-to-end on a real codebase — it builds no new Shipyard modules, only exercises the existing pipeline.

</domain>

<decisions>
## Implementation Decisions

### Target Scope
- **D-01:** Focus on core workflows (auth, CRUD, navigation) rather than all 47 routes. The pipeline's analyzer determines which routes are highest-impact — no manual route list.
- **D-02:** "Core pass = ship it" — if auth + CRUD + nav work and the UI renders, that's a pass. Non-critical route failures are acceptable for the demo.

### Execution Strategy
- **D-03:** Full analyze-then-execute pipeline: clone Ship from GitHub -> analyze -> generate task DAG -> execute in parallel. This is what Phases 12-15 built — use it as designed.
- **D-04:** Output is a fresh git repo (clean slate). Proves the pipeline can generate a working app from scratch, not just modify existing code.
- **D-05:** If the pipeline hits a wall, trust the failure classification + retry engine from Phase 15. No manual intervention unless the system is truly stuck.

### Deployment Pipeline
- **D-06:** Deploy to Railway. Fully automated — pipeline generates deploy scripts, provisions DB/secrets via Railway CLI, pushes, and verifies the URL responds. Zero manual steps.
- **D-07:** Secrets and environment config managed through Railway environment variables, provisioned automatically from a template during deploy.

### Validation Approach
- **D-08:** Belt and suspenders — API smoke tests for route coverage (status codes + response shapes) AND Playwright E2E tests for user workflow coverage (signup, login, CRUD, navigation).
- **D-09:** Demo bar is "Green CI + live URL" — all automated tests pass, and the live app is clickable in a browser. The demo shows both.

### Claude's Discretion
- Which specific Ship routes to prioritize (analyzer decides based on codebase analysis)
- E2E test framework details (Playwright preferred per existing Shipyard setup)
- Railway project configuration specifics
- How to handle Ship's specific tech stack dependencies during rebuild

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline Modules (what Phase 16 exercises)
- `agent/orchestrator/scheduler.py` -- DAG scheduler with branch isolation, CI gating, retry engine
- `agent/orchestrator/dag.py` -- TaskDAG definition and dependency ordering
- `agent/orchestrator/analyzer.py` -- Codebase analyzer producing module maps
- `agent/orchestrator/planner.py` -- Task DAG generation from analysis
- `agent/orchestrator/branch_manager.py` -- Per-task git branch lifecycle
- `agent/orchestrator/ci_runner.py` -- 4-stage CI pipeline (typecheck/lint/test/build)
- `agent/orchestrator/failure_classifier.py` -- Error classification + retry budgets
- `agent/orchestrator/context_packs.py` -- Scoped file delivery to agents
- `agent/orchestrator/ownership.py` -- Module boundary enforcement

### Project Context
- `.planning/PROJECT.md` -- Core value, constraints, demo target requirement
- `.planning/REQUIREMENTS.md` -- SHIP-01 through SHIP-05 acceptance criteria
- `.planning/ROADMAP.md` -- Phase 16 success criteria (47 routes, E2E, UI renders, public URL)

### Prior Phase Context
- `.planning/phases/12-orchestrator-dag-engine-contract-foundation/12-CONTEXT.md` -- DAG engine decisions
- `.planning/phases/13-analyzer-planner-agents/13-CONTEXT.md` -- Analyzer/planner architecture
- `.planning/phases/15-execution-engine-ci-validation/15-CONTEXT.md` -- Execution engine decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Full orchestrator pipeline (Phases 12-15): analyzer, planner, DAG scheduler, execution engine, CI runner
- LangGraph-based agent graph with plan-read-edit-validate cycle
- Existing Playwright setup in web/package.json for E2E testing patterns
- Railway-compatible Procfile and deployment patterns already in Shipyard

### Established Patterns
- Asyncio-based parallel execution with semaphore-bounded concurrency (5-15 agents)
- Branch-per-task isolation with ff-only merge policy
- Tiered retry: syntax=3, test=2, contract=1, structural=1
- Context packs capped at 5 files per agent

### Integration Points
- Pipeline entry: submit codebase path -> analyzer -> planner -> scheduler.execute()
- Ship's GitHub URL is the input to the analyzer
- Railway CLI for deployment automation
- Rebuilt app's public URL is the final verification target

</code_context>

<specifics>
## Specific Ideas

- Demo video shows "Green CI + live URL" — both automated test results and a clickable app
- Ship is cloned from GitHub (not local copy)
- Analyzer-driven scope selection — the pipeline itself decides which workflows matter most
- Fresh repo output proves generative capability, not just modification

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-ship-rebuild-proof*
*Context gathered: 2026-03-29*
