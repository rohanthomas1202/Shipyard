# Project Research Summary

**Project:** Shipyard v1.3 — Ship Rebuild End-to-End
**Domain:** Autonomous coding agent — persistent loop, from-scratch generation, intervention logging, comparative analysis
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

Shipyard v1.3 is a capability milestone: prove the agent can rebuild a real production app (Ship) from scratch using PRD-driven task generation, then document the process honestly with structured intervention logs and a 7-section comparative analysis. Research across all four areas converges on one clear finding — the existing infrastructure (FastAPI, EventBus, LangGraph, SQLite, DAGScheduler, BranchManager, ModelRouter) already provides every primitive needed. Zero new Python or frontend dependencies are required. The entire milestone is application code: new endpoints, new nodes, new schemas, and new prompts wired to existing machinery.

The single highest-complexity feature is from-scratch file generation. The entire agent pipeline — reader, editor, validator — assumes files already exist. The `_seed_output_from_source()` workaround in `ship_rebuild.py` exists precisely because the agent cannot generate from scratch today. Removing seeding without adding a `create` step kind and a corresponding code path (new `creator_node` or extended editor) breaks the core pipeline immediately. This must be solved before EventBus wiring or the frontend panel, because all observable rebuild progress depends on the agent actually creating files.

The second critical dependency chain is observability. The current `run_rebuild()` script uses `print()` statements and runs outside the FastAPI process. Converting it to a managed background task with EventBus streaming, proper cancellation, and persistent status is prerequisite work for every downstream feature. Railway account verification belongs in Phase 1 as a prerequisite check — discovering billing issues after a completed rebuild wastes the entire effort.

## Key Findings

### Recommended Stack

The existing stack is fully adequate for v1.3. Research explicitly identified 15+ libraries that should NOT be added (Celery, Redis, Socket.IO, SQLAlchemy, Jinja2, react-query, Pandas, Markdown parsers, etc.) and demonstrated that every capability maps to an existing primitive. The only new system dependency is the Railway CLI (`railway`) installed via npm or Homebrew — not a Python package.

Two new SQLite tables are required (`interventions`, `rebuild_runs`) following the established aiosqlite + Pydantic BaseModel pattern used by Project, Run, Event, and EditRecord. A new Zustand slice handles frontend rebuild state. All other additions are new Python modules and React components within existing library budgets.

**Core technologies:**
- `asyncio.create_task()`: Persistent rebuild loop — single-process uvicorn cannot use Celery/ARQ; established pattern already in `server/main.py`
- `EventBus` (existing `agent/events.py`): Rebuild progress streaming — add new event type strings to `_P0_TYPES`, pass server's EventBus instance into DAGScheduler
- `file_ops.write_file()` (extend `agent/tools/file_ops.py`): From-scratch file creation — distinct from `edit_file()` anchor replacement; must call `makedirs(exist_ok=True)`
- `aiosqlite` + Pydantic (existing `store/`): Intervention records — same pattern as EditRecord; no ORM needed
- `ModelRouter.call()` (existing `agent/router.py`): Analysis generation — gpt-4o general tier with pre-computed structured metrics as input, not raw logs
- Railway CLI: Deployment — `railway up` via `run_command_async()`; set `NIXPACKS_BUILD_CMD` for pnpm monorepo

### Expected Features

**Must have (table stakes) — all P1 for v1.3:**
- `POST /rebuild` endpoint with managed background task lifecycle — returns `run_id`, streams events, supports cancellation
- EventBus wired to DAGScheduler — currently disconnected in `ship_rebuild.py`; scheduler already accepts `event_bus` param
- From-scratch file creation in agent — new `create` step kind, `creator_node` or extended editor, `write_file()` tool
- Remove `_seed_output_from_source()` — rebuild must start from empty git repo
- PRD-style task descriptions — planner outputs "create" steps with explicit file paths, not "edit" steps
- `Intervention` Pydantic model + SQLite table — 9-field structured schema defined before first rebuild run
- Metric collection hooks in scheduler — timing, LOC, success rate, token usage per task
- LLM-driven CODEAGENT.md population — fill `[FILL AFTER REBUILD]` placeholders from structured metrics
- Frontend rebuild progress panel — clone/analyze/plan/execute/build/deploy stages with task-level progress
- Railway deployment — account verified early, rebuilt Ship deployed to public URL

**Should have (competitive differentiators):**
- Intervention auto-detection — detect corrective instruction after failure, auto-log as intervention
- Token cost breakdown per rebuild phase — tag ModelRouter calls with phase/task_id
- Rebuild cancellation with worktree cleanup — extend run cancellation to DAGScheduler
- Persistent loop with WebSocket reconnect and event replay — already 90% built via existing EventBus replay

**Defer to v2+:**
- Multi-project rebuild support
- Incremental rebuild (only regenerate files changed in PRD)
- Test generation as a rebuild step
- Cross-agent collaboration for module parallelism
- Live task DAG visualization (graph rendering library)
- Custom PRD editor in UI

### Architecture Approach

Extend the existing server/agent/store three-layer architecture with five new components, all fitting within established boundaries. No new layers, no new process boundaries. The rebuild pipeline uses a strictly sequential phase model (clone → analyze → plan → execute → build → deploy) wrapped in an async context manager that emits EventBus events automatically on entry, exit, and error. A single active rebuild guard (`_active_rebuild` global in `server/main.py`) prevents resource contention. Analysis generation runs as a post-processing step after the DAG completes, receiving pre-computed structured metrics as LLM input — not raw logs.

Key anti-patterns explicitly called out by research: do NOT poll `GET /rebuild/{id}` from the frontend (WebSocket already delivers push updates), do NOT store the full Markdown analysis in SQLite (write to filesystem, store path), do NOT create a separate `/ws/rebuild` WebSocket endpoint (existing `/ws` with ConnectionManager handles rebuild events via run_id subscription).

**Major components:**
1. `RebuildController` (`server/main.py` new routes) — POST /rebuild endpoint, single-active-rebuild guard, task lifecycle management with try/except and status persistence
2. `RebuildService` (`agent/orchestrator/rebuild_service.py` new) — wraps `run_rebuild()` with EventBus phase tracking via `rebuild_phase()` async context manager
3. `InterventionStore` (`store/sqlite.py` extend) — CRUD for `Intervention` records; dual-write to EventBus + SQLite for real-time UI and analysis queries
4. `AnalysisGenerator` (`agent/orchestrator/analysis.py` new) — generates 7-section comparative analysis from pre-computed structured metrics dict; validates sections before accepting output
5. `RebuildPanel` (`web/src/components/rebuild/` new) — React component + Zustand rebuild slice; subscribes to rebuild run_id via existing WebSocket subscription model

### Critical Pitfalls

1. **Background task silently dies with no status update** — wrap entire `run_rebuild()` body in try/except catching ALL exceptions; update run status to "failed" in DB; emit `rebuild_failed` event; store `asyncio.Task` reference in `app.state.rebuild_task`; replace all `print()` calls with `EventBus.emit()`; handle graceful shutdown in lifespan; use `asyncio.shield()` around critical git operations

2. **Editor node cannot create files (entire pipeline assumes files exist)** — add `PlanStep.kind = "create"`, route to a creation code path with `file_ops.write_file()` (full LLM-generated content, no anchor matching, `makedirs`); update validator to handle files with no LSP baseline; planner must output "create" steps with explicit file paths for all files in an empty output directory

3. **Intervention schema defined too late — cannot be retroactively applied** — `Intervention` Pydantic model with all 9 required fields (`trigger`, `category`, `agent_state_snapshot`, `files_affected`, `resolution`, `could_agent_have_done_this`, `time_spent_seconds`, etc.) must be finalized before the first rebuild run; free-text logs cannot be structured after the fact

4. **Comparative analysis generates hallucinated metrics** — pre-compute all hard metrics (task completion rate, build success boolean, intervention count, time per phase, LOC, token cost) before invoking LLM; feed as structured dict, not raw logs; hard-code all 7 section headings in prompt; validate generated numbers against pre-computed values; require a "Limitations and Failures" section

5. **Memory leak over multi-hour rebuild** — each DAG task must use a fresh `AgentState` (current `ship_executor.py` does this — verify it stays true on any changes); after task completion, store only summary data (edit count, files modified, success/failure), discard full state; limit `runs` dict to sliding window of 50; `add_messages` reducer in `AgentState` appends without bound — state reuse across tasks would exhaust memory within 50 tasks

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Persistent Loop Infrastructure
**Rationale:** Everything downstream depends on the rebuild being observable, cancellable, and survivable across server restarts. This is the plumbing phase. Railway account verification belongs here as a prerequisite check — not a final step.
**Delivers:** `POST /rebuild` endpoint with managed task lifecycle; EventBus wired to DAGScheduler; WebSocket streaming of rebuild events; task cancellation (`POST /rebuild/{id}/cancel`); memory management strategy (fresh state per task, runs dict window); git worktree cleanup in scheduler `finally` block; phase-weighted progress reporting; Railway "hello world" deployed to verify account
**Addresses:** POST /rebuild endpoint, EventBus wiring, persistent loop with WebSocket reconnect
**Avoids:** Background task silent failure (Pitfall 1), memory leak (Pitfall 7), git worktree accumulation (Pitfall 9), erratic progress display (Pitfall 8), Railway billing surprise (Pitfall 6)

### Phase 2: From-Scratch Code Generation
**Rationale:** The headline capability and highest technical risk. Must be proven functional before the full rebuild pipeline runs. Planner, editor, and validator all need changes that are foundational to Phase 4.
**Delivers:** `PlanStep.kind = "create"` with creator code path; `file_ops.write_file()` tool; planner prompt changes for `generation_mode: from_scratch`; `_seed_output_from_source()` removed; DAG ordering enforcing foundational files (types, models, utils) before consumers; post-merge import validation
**Uses:** Existing LangGraph graph extended; existing `file_ops.py` extended; existing planner with new prompts
**Implements:** Creator node or extended editor; file creation tool path; PRD-style task descriptions
**Avoids:** Editor "file must exist" assumption (Pitfall 2), planner edit-vs-create confusion (Pitfall 10), cross-module circular imports (Pitfall 11)

### Phase 3: Intervention Logging
**Rationale:** Schema must be locked before the first real rebuild run. Unstructured logs cannot be retroactively structured. Low implementation cost but permanent consequences if skipped.
**Delivers:** `Intervention` Pydantic model with all required fields; SQLite `interventions` table + index; `POST /rebuild/{id}/intervention` and `GET /rebuild/{id}/interventions` endpoints; auto-context snapshot on log (current DAG state, recent events); dual-write (EventBus + SQLite); floating "Log Intervention" button always visible during rebuild
**Uses:** Existing aiosqlite + Pydantic pattern; existing EventBus emit; existing SQLite store
**Avoids:** Wrong intervention granularity (Pitfall 4), SQLite write contention from separate table (Pitfall 3 partial)

### Phase 4: Full Rebuild Pipeline Run
**Rationale:** First end-to-end run of the rebuild against the real Ship repo. Phases 1-3 provide the infrastructure; this phase executes it and validates that PRD-driven generation produces a buildable app.
**Delivers:** Complete Ship rebuild from empty repo; structured intervention log from the actual run; all metric collection working (timing, LOC, tokens, task success rate); CODEAGENT.md `[FILL AFTER REBUILD]` placeholders populated with real data
**Uses:** All infrastructure from Phases 1-3; existing DAGScheduler; existing BranchManager; existing CIRunner

### Phase 5: Comparative Analysis Generation
**Rationale:** Final deliverable. Requires complete data from Phase 4. Analysis quality is determined by pre-computed metrics, not LLM inference from raw logs.
**Delivers:** `AnalysisGenerator` component; 7-section ANALYSIS.md with all sections non-empty; quantitative claims verified against pre-computed metrics; `GET /rebuild/{id}/analysis` endpoint serving the file; `analysis_ready` EventBus event
**Uses:** Existing ModelRouter (gpt-4o general tier); structured metrics dict from Phase 4; intervention records from Phase 3
**Avoids:** Comparative analysis fiction (Pitfall 5), missing analysis sections (Pitfall 12)

### Phase 6: Railway Deployment
**Rationale:** Final demo requirement. Account verified in Phase 1; this phase executes actual deployment of the rebuilt Ship app to a public URL.
**Delivers:** Rebuilt Ship deployed to public Railway URL; `pnpm build` clean pass; `PORT` binding correct; `railway.toml` or `NIXPACKS_BUILD_CMD` configured for pnpm monorepo
**Avoids:** Railway trial expiry surprise (Pitfall 6 — already handled by Phase 1 verification)

### Phase Ordering Rationale

- Phase 1 before everything: silent background task failures cascade into every observable feature; memory management and cancellation cannot be retrofitted
- Phase 2 before Phase 4: the rebuild pipeline is meaningless if the agent cannot create files; seeding is a v1.2 workaround, not a fallback for v1.3
- Phase 3 before Phase 4: intervention schema cannot be retroactively applied to logs from a completed rebuild; this has no recovery path
- Phase 5 after Phase 4: comparative analysis requires completed rebuild data; cannot be generated speculatively
- Phase 6 last: depends on Phase 4 producing a buildable app; Railway account verification (Phase 1 check) separates infrastructure readiness from final deployment

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** From-scratch generation is the least-charted territory in this codebase — `creator_node` design, DAG ordering for dependency satisfaction, contract-first generation pattern, and planner prompt engineering all need implementation research before coding starts; the existing `ContractStore` reference (Pitfall 11) needs investigation
- **Phase 4:** First real rebuild run will surface unknown failure modes; plan for at least one iteration cycle

Phases with standard patterns (skip research-phase):
- **Phase 1:** AsyncIO background task lifecycle, EventBus wiring, and WebSocket streaming are well-documented patterns already established in the codebase
- **Phase 3:** Pydantic model + SQLite table + CRUD endpoint is a direct repeat of existing store patterns (EditRecord, Project, Run)
- **Phase 5:** LLM-driven analysis with structured input is a standard prompt-engineering task; data collection patterns are established
- **Phase 6:** Railway CLI deployment is a single command; configuration is table-stakes Node.js deployment

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations traced directly to specific files and line numbers in the existing codebase; zero new dependencies means no external verification needed |
| Features | HIGH | Features defined in PROJECT.md with explicit CODEAGENT.md deliverables; dependency graph is unambiguous; all P1 features required for demo |
| Architecture | HIGH | Extends existing patterns without new layers; component boundaries and data flow are well-defined; anti-patterns explicitly documented |
| Pitfalls | HIGH | Pitfalls grounded in specific line numbers (`print()` calls in `ship_rebuild.py` lines 252/263/278/283, `add_messages` reducer in `agent/state.py`, `runs` dict in `server/main.py` line 27); not speculative |

**Overall confidence:** HIGH

### Gaps to Address

- **Creator node design decision:** Research identifies what must change but the exact implementation — extend `editor_node` vs build a separate `creator_node` — requires a design decision during Phase 2 planning; either path is valid but must be chosen before coding
- **ContractStore investigation:** Pitfall 11 references an existing `ContractStore` for cross-module contract sharing; this component needs investigation before Phase 2 planning to confirm it exists and is usable for dependency ordering
- **SQLite write contention threshold:** Research recommends write batching at 100ms windows under 10x concurrent load, but the actual contention threshold for this codebase's event volume is unknown; measure during Phase 4 rather than preemptively optimizing
- **Intervention auto-detection mechanism:** Detecting that a user instruction is a "corrective intervention" (vs a new instruction) is not designed; deferred to v1.3.x but needs acknowledgment as a gap in the auto-logging story

## Sources

### Primary (HIGH confidence)

- Codebase audit: `scripts/ship_rebuild.py`, `agent/nodes/editor.py`, `agent/state.py`, `server/main.py`, `agent/orchestrator/scheduler.py`, `agent/orchestrator/ship_executor.py`, `agent/events.py`, `store/models.py`, `agent/router.py` — all recommendations traced to specific files and line numbers
- FastAPI official documentation — background task pattern with `asyncio.create_task()`, lifespan context manager
- SQLite official documentation — WAL mode concurrency, write serialization characteristics
- Python asyncio documentation — task exception handling, `asyncio.shield()`, task cancellation

### Secondary (MEDIUM confidence)

- Railway CLI documentation — `RAILWAY_TOKEN`, `railway up`, `NIXPACKS_BUILD_CMD` for pnpm monorepos, ephemeral filesystem behavior
- Oracle: What Is the AI Agent Loop — persistent loop architecture patterns
- LoginRadius: Auditing and Logging AI Agent Activity — intervention log schema design
- IEEE: Comparative Analysis between AI Generated Code and Human Written Code — analysis section framing and metrics selection
- ChatPRD: Writing PRDs for AI Code Generation Tools — PRD-style task description format for from-scratch generation

### Tertiary (LOW confidence)

- ASDLC.io: Ralph Loop Pattern — referenced for comparison; deliberately not adopted in favor of existing DAGRun persistence (existing pattern is sufficient)
- Anthropic: Measuring Agent Autonomy — `could_agent_have_done_this` field inspiration in Intervention schema (validate against final CODEAGENT.md requirements)

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
