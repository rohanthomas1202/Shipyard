# Phase 13: Analyzer + Planner Agents - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build two new agent modules — an Analyzer that parses a codebase into a structured module map with dependency graph, and a Planner that decomposes that map through a three-layer pipeline (PRD → Tech Spec → Task DAG) into bounded, executable tasks feeding the Phase 12 orchestrator. Proven with a Ship-like fixture codebase.

</domain>

<decisions>
## Implementation Decisions

### Analyzer: Module Discovery
- **D-01:** Hybrid discovery — directory-based for initial module structure, then LLM reads each module to enrich with semantic understanding (purpose, public API, inter-module dependencies)
- **D-02:** Tiered module map — lean map (name, file list, exports, dependency edges, 1-sentence summary) for all modules, with rich detail (function signatures, class hierarchies, LOC counts) only for modules the Planner flags as complex. Two-pass approach.
- **D-03:** Import edges only for dependency graph — static import/require analysis. Module A imports from module B = directed edge. Deterministic, no LLM inference for edges.
- **D-04:** Single JSON output file (module-map.json) containing all modules, edges, and summaries. Fits in context for most codebases, easy to pass to Planner as one file.

### Planner: Decomposition Pipeline
- **D-05:** Sequential single-pass pipeline — PRD from module map → Tech Spec from PRD → Task DAG from Tech Spec. One LLM call per layer. Validation gate at each transition.
- **D-06:** Structural validation only between layers — check DAG is acyclic, tasks reference valid contracts, every module is covered, LOC/file bounds met. Automated, no LLM review pass.
- **D-07:** o3 for all three layers (PRD, Tech Spec, Task DAG). Planning is the highest-reasoning task. Cost is irrelevant per project constraints (unlimited OpenAI tokens).
- **D-08:** PRDs and Tech Specs stored as git-tracked markdown files in a plans/ directory alongside contracts/. Human-readable, diffable, agents can reference them.

### Task Bounding
- **D-09:** Hard enforcement with escape hatch — validation rejects any task exceeding ≤300 LOC / ≤3 files, but Planner can mark specific tasks as "indivisible" with justification for tightly coupled code.
- **D-10:** LLM estimation for LOC per task — o3 estimates LOC based on Tech Spec description. Good enough for bounding, doesn't need to be exact.

### Test Target
- **D-11:** Fixture subset, not real Ship repo — a minimal Ship-like fixture with 5-10 files (2 Express routes, 1 Prisma schema, 2 React components, 1 shared type file) for testing module discovery, dependency edges, and decomposition.
- **D-12:** No Ship repo clone needed for Phase 13. Ship rebuild proof is Phase 16.

### Claude's Discretion
- Analyzer prompt engineering (how to instruct o3 for module summarization)
- Module map JSON schema design
- PRD and Tech Spec markdown template structure
- How the Planner invokes the Analyzer's enrichment pass for complex modules
- Validation error message format and reporting
- Cost estimation formula for the validation gate

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Orchestrator Foundation (Phase 12 — what we build on)
- `agent/orchestrator/models.py` — TaskNode, TaskEdge, TaskExecution, DAGRun Pydantic models. Planner output must produce objects compatible with these types.
- `agent/orchestrator/dag.py` — TaskDAG class wrapping NetworkX. Planner's Task DAG output must be loadable into this.
- `agent/orchestrator/contracts.py` — ContractStore for file-based contract CRUD. Planner generates contracts that get stored here.
- `agent/orchestrator/scheduler.py` — DAGScheduler. The Task DAG from Planner feeds directly into this for execution.
- `agent/orchestrator/persistence.py` — DAGPersistence for SQLite state. DAG runs created from Planner output persist through this.

### Existing Agent Architecture
- `agent/nodes/planner.py` — Current single-instruction planner node. Phase 13 Planner is a NEW module, not a modification of this.
- `agent/prompts/planner.py` — Current planner prompts. Reference for prompt engineering patterns.
- `agent/router.py` — ModelRouter with ROUTING_POLICY. New task types (analyze, plan_prd, plan_spec, plan_dag) need routing entries.
- `agent/context.py` — ContextAssembler with token budgets. Reuse for assembling module map context.

### Server & Persistence
- `server/main.py` — FastAPI server with DAG endpoints. Analyzer/Planner may need new endpoints or integration points.
- `store/sqlite.py` — SQLiteSessionStore. Module map might be persisted here.

### Requirements
- `.planning/REQUIREMENTS.md` — ANLZ-01, ANLZ-02, PLAN-01 through PLAN-04 define acceptance criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TaskDAG` (agent/orchestrator/dag.py) — Planner output loads directly into this. add_task() and add_dependency() API already defined.
- `ContractStore` (agent/orchestrator/contracts.py) — Planner generates contract files, ContractStore manages them.
- `ModelRouter` (agent/router.py) — Add new task types for analyzer and planner LLM calls. Auto-escalation built in.
- `ContextAssembler` (agent/context.py) — Token-aware context packing for module map → LLM prompt assembly.
- `parse_plan_steps()` (agent/steps.py) — Existing plan parsing with JSON fallback. Reference pattern for parsing Planner output.

### Established Patterns
- Pydantic models for all data structures (agent/orchestrator/models.py)
- Async node functions with `_node()` suffix (agent/nodes/*.py)
- LLM calls through router.call(task_type, system, user) — never direct
- Structured LLM output via JSON parsing with retry feedback loop

### Integration Points
- New `agent/analyzer/` package — module discovery, import parsing, LLM enrichment
- New `agent/planner_v2/` or `agent/orchestrator/planner.py` — three-layer pipeline (distinct from existing agent/nodes/planner.py)
- New routing entries in ModelRouter.ROUTING_POLICY for analyze/plan task types
- Module map output consumed by DAGScheduler via TaskDAG construction
- plans/ directory for PRD and Tech Spec markdown artifacts

</code_context>

<specifics>
## Specific Ideas

- The Analyzer and Planner are NEW modules in agent/ — they don't modify the existing LangGraph planner_node (which handles single-instruction decomposition)
- The Planner's Task DAG output must produce TaskNode and TaskEdge objects compatible with agent/orchestrator/models.py — no separate task model
- The fixture should mimic Ship's actual patterns: Express middleware chain, Prisma schema with relations, React components with hooks
- "Indivisible" escape hatch should require a justification string logged for observability

</specifics>

<deferred>
## Deferred Ideas

- Failure classification system A/B/C/D routing errors to handlers (Phase 15)
- Module ownership model preventing cross-agent conflicts (Phase 15)
- Contract backward compatibility checks and migration strategy (Phase 14)
- DAG visualization in frontend (Phase 14 — observability)
- Using Shipyard's own codebase as a secondary test target

</deferred>

---

*Phase: 13-analyzer-planner-agents*
*Context gathered: 2026-03-29*
