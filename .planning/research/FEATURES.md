# Feature Research

**Domain:** Autonomous coding agent -- persistent loop, from-scratch generation, intervention logging, comparative analysis
**Researched:** 2026-03-30
**Confidence:** HIGH (features are well-defined in PROJECT.md; patterns are established in industry)

## Feature Landscape

### Table Stakes (Users Expect These)

Features the v1.3 milestone must deliver. Missing any of these means the demo video cannot be recorded and CODEAGENT.md remains incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| POST /rebuild endpoint | ship_rebuild.py runs as CLI script only; the server needs a triggerable endpoint for frontend integration | MEDIUM | Wrap `run_rebuild()` in `asyncio.create_task()`, return run_id immediately. EventBus already supports DAG events (dag_started, task_completed, progress_update). Main work: wiring, not inventing. |
| EventBus streaming during rebuild | Frontend needs real-time progress; the scheduler already emits events but EventBus is not connected in ship_rebuild.py | MEDIUM | Scheduler accepts `event_bus` param (already typed). Pass server's EventBus instance into DAGScheduler. WebSocket relay already works for agent runs -- same path for rebuild events. |
| Frontend live rebuild progress panel | Users must see clone/analyze/plan/execute/build stages in real time, not wait for stdout | MEDIUM | New React component subscribing to rebuild-specific event types. Reuse existing activity stream pattern (auto-scroll, type filtering). Add progress bar driven by `progress_update` events. New Zustand slice for rebuild state. |
| From-scratch code generation (no seeding) | The current `_seed_output_from_source()` copies the entire Ship repo then edits 2-3 files. v1.3 must generate every file from PRDs -- this is the core proof-of-concept | HIGH | Requires new executor mode where tasks create files instead of editing existing ones. The LangGraph agent's `editor_node` uses anchor-based replacement which assumes files exist. Need a `create_file` tool/path or a generation-first step before the edit loop. |
| Structured intervention logging | CODEAGENT.md has [FILL AFTER REBUILD] placeholders for intervention counts, failure modes, and human time. These must be populated from structured data, not manual notes | MEDIUM | Pydantic model for InterventionRecord (timestamp, instruction_id, failure_type, human_action, time_spent, resolution). Stored in SQLite alongside run events. CRUD endpoint for manual logging + auto-detection of corrective instructions. |
| 7-section comparative analysis from rebuild data | CODEAGENT.md sections 1-7 have [FILL] placeholders. Agent must populate these from actual metrics, not hallucinate | HIGH | Requires: (a) metric collection during rebuild (LOC, time, success rate, token usage), (b) source repo analysis for comparison baseline, (c) LLM-driven narrative generation constrained by actual data. |
| Railway deployment of rebuilt Ship | Blocked on billing, but the rebuilt app must be publicly accessible at a URL for the demo | LOW | Railway deploy scripts already exist. Unblock billing, run deploy. The rebuilt Ship must pass `pnpm build` cleanly. |

### Differentiators (Competitive Advantage)

Features that make Shipyard's demo stand out from other agent demos.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| PRD-to-code without seeding | Most demos (Devin, Replit Agent) start from templates or existing repos. Generating a full monorepo from PRD descriptions alone proves deeper capability | HIGH | This is the headline differentiator. Requires decomposing Ship's architecture into PRD-style task descriptions that specify file creation, not file editing. The planner already generates task DAGs -- but tasks must output `create_file` actions. |
| Intervention log as first-class data | Most agent demos hide failures. Publishing structured intervention data with root cause analysis builds trust and provides genuine comparative insight | LOW | Schema is simple. The hard part is discipline during the rebuild -- every manual fix must be logged. Automate capture where possible (detect when user sends corrective instruction after a failure). |
| Metric-driven comparative analysis | CODEAGENT.md section 3 (Performance Benchmarks) and section 6 (Trade-off Analysis) are more credible when backed by actual numbers, not estimates | MEDIUM | Token usage already tracked by ModelRouter.get_usage_summary(). LOC counted by shell. Time tracked by DAGRun timestamps. Diff against source repo for structural comparison. |
| Persistent agent loop with WebSocket reconnect | Agent stays alive between instructions, frontend reconnects and replays missed events. Not fire-and-forget | LOW | Already 90% built. POST /rebuild creates a long-running task; EventBus handles streaming. Reconnect replay via `event_bus.replay()` already works. |
| Token cost breakdown per rebuild section | Show exactly what each phase (analyze, plan, execute) cost in tokens and dollars | LOW | ModelRouter already tracks per-call usage. Tag calls with phase/task_id for grouping. |
| Rebuild cancellation with worktree cleanup | Stop a running rebuild and clean up git worktrees | LOW | Extend existing run cancellation pattern to DAGScheduler. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but would derail the v1.3 timeline or produce worse outcomes.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time interactive steering during rebuild | "Let me redirect the agent mid-task" | The DAG scheduler manages task dependencies; injecting new instructions mid-execution would corrupt the dependency graph and cause merge conflicts | Allow pausing the rebuild, reviewing progress, then resuming. Post-rebuild corrections as follow-up instructions. |
| Template-based code generation | "Start from a CRA/Vite template, then customize" | Defeats the purpose of from-scratch generation. Using templates means the agent is editing, not creating, which is what v1.2 already does | Generate package.json, tsconfig, vite.config from PRD specs. The agent describes the toolchain in its task, then creates config files as code. |
| Automated test generation during rebuild | "Generate tests alongside each feature" | Ship's original repo has minimal tests. Generating tests the original lacks makes comparison unfair and slows the rebuild significantly | Note testing as a shortcoming in comparative analysis section 4. Offer test generation as a post-rebuild enhancement. |
| Multi-provider LLM support for rebuild | "Use Claude for planning, GPT for editing" | Adds provider-switching complexity for zero demo benefit. OpenAI tokens are unlimited. | Stick with OpenAI tiered routing (o3/gpt-4o/gpt-4o-mini). Document as future consideration. |
| Automatic retry of entire failed rebuild | "If rebuild fails, restart from scratch" | A full rebuild costs significant tokens and time. Better to diagnose and fix specific failures | Use the DAG scheduler's existing retry-per-task logic. Failed tasks get retried with error context. Only manually restart if the entire approach was wrong. |
| Git-based progress persistence (Ralph Loop style) | "Save progress in git so a fresh agent can resume" | Shipyard already has SQLite persistence + LangGraph checkpointing. Adding git-based state is redundant | Use existing DAGRun persistence for crash recovery. The scheduler already tracks completed/failed tasks and skips completed ones on resume. |
| Live task DAG visualization | "Show dependency graph with real-time coloring" | Requires graph rendering library, complex layout logic, high effort for low demo ROI | Text-based progress panel with task list and status badges is sufficient. |
| Multi-project rebuild queue | "Queue multiple rebuilds" | Single rebuild at a time is fine for demo; queuing adds complexity | Return 409 if rebuild already running. |
| Custom PRD editor in UI | "Edit PRDs in the frontend" | PRDs are pre-written for the demo; building an editor is scope creep | Accept PRD path as rebuild parameter. |

## Feature Dependencies

```
[POST /rebuild endpoint]
    |
    +--requires--> [EventBus wiring to DAGScheduler]
    |                  |
    |                  +--enables--> [Frontend rebuild progress panel]
    |
    +--requires--> [From-scratch generation mode]
                       |
                       +--requires--> [File creation tool/path in agent]
                       |
                       +--requires--> [PRD-style task descriptions (not edit instructions)]

[Structured intervention logging]
    |
    +--requires--> [InterventionRecord schema in SQLite]
    |
    +--enhances--> [7-section comparative analysis]

[7-section comparative analysis]
    |
    +--requires--> [Metric collection during rebuild]
    |                  |
    |                  +--requires--> [POST /rebuild running successfully]
    |
    +--requires--> [Source repo analysis (baseline metrics)]
    |
    +--requires--> [Intervention log data]

[Railway deployment]
    |
    +--requires--> [From-scratch generation producing a buildable app]
    +--requires--> [Billing unblocked (external)]
```

### Dependency Notes

- **POST /rebuild requires EventBus wiring:** The scheduler already accepts an `event_bus` parameter. The endpoint must construct the scheduler with the server's EventBus instance (currently only `ship_rebuild.py` constructs the scheduler without EventBus).
- **From-scratch generation requires file creation tool:** The current agent pipeline assumes files exist (reader loads, editor replaces anchors). A new `create_file` action type must be added to `file_ops.py` or a new step kind must be supported in the planner/editor.
- **Comparative analysis requires all other features:** It is the final deliverable. It cannot be populated until the rebuild runs, interventions are logged, and metrics are collected.
- **Frontend panel requires EventBus wiring:** No point building the UI until events actually flow from the rebuild process.
- **Railway deployment requires buildable output:** If from-scratch generation produces broken code, deployment is meaningless.

## MVP Definition

### Launch With (v1.3)

Minimum viable set to record the demo video and fill CODEAGENT.md.

- [ ] POST /rebuild endpoint with asyncio.create_task -- wraps run_rebuild() as a background task returning run_id
- [ ] EventBus connected to DAGScheduler -- pass server's EventBus into the scheduler so rebuild events stream to WebSocket
- [ ] From-scratch file creation in agent -- add `create_file` step kind or tool that writes new files (not anchor-replace)
- [ ] PRD-style task descriptions for Ship -- rewrite planner output to describe file creation, not editing of existing files
- [ ] Remove _seed_output_from_source -- rebuild must start from empty git repo + minimal scaffolding only
- [ ] InterventionRecord Pydantic model + SQLite table -- capture every human intervention with structured fields
- [ ] Metric collection hooks in scheduler -- capture timing, LOC, success rate, token usage per task
- [ ] LLM-driven CODEAGENT.md population -- agent fills [FILL AFTER REBUILD] placeholders from collected metrics and intervention logs
- [ ] Frontend rebuild progress panel -- show clone/analyze/plan/execute/build stages with task-level progress
- [ ] Railway deployment -- unblock billing, deploy rebuilt Ship to public URL

### Add After Validation (v1.3.x)

Features to add if the core rebuild works but needs polish.

- [ ] Intervention auto-detection -- detect when a corrective instruction follows a failure and auto-log as intervention
- [ ] Comparative analysis diff viewer -- side-by-side view of original Ship file vs agent-generated file in the frontend
- [ ] Rebuild replay -- replay a completed rebuild's events in the frontend for demo recording
- [ ] Cost analysis population -- fill CODEAGENT.md cost section from LangSmith API data

### Future Consideration (v2+)

Features to defer until the core proof-of-concept is validated.

- [ ] Multi-project rebuild support -- rebuild different apps, not just Ship
- [ ] Incremental rebuild -- only regenerate files that changed in the PRD
- [ ] Test generation as rebuild step -- generate tests alongside each feature module
- [ ] Cross-agent collaboration -- multiple Shipyard instances working on different modules with shared context

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Depends On |
|---------|------------|---------------------|----------|------------|
| From-scratch file creation | HIGH | HIGH | P1 | file_ops.py changes, planner changes |
| POST /rebuild endpoint | HIGH | LOW | P1 | Existing run_rebuild() |
| EventBus wiring to scheduler | HIGH | LOW | P1 | Existing EventBus + scheduler params |
| Frontend rebuild progress panel | HIGH | MEDIUM | P1 | EventBus wiring |
| PRD-style task descriptions | HIGH | MEDIUM | P1 | Planner modifications |
| Remove seeding, scaffold-only start | HIGH | LOW | P1 | From-scratch generation working |
| InterventionRecord schema | MEDIUM | LOW | P1 | SQLite migration |
| Metric collection hooks | MEDIUM | LOW | P1 | Scheduler instrumentation |
| 7-section comparative analysis | HIGH | MEDIUM | P1 | All above features |
| Railway deployment | HIGH | LOW | P1 | Billing + buildable output |

**Priority key:**
- P1: Must have for v1.3 launch (all features are P1 -- this is a focused milestone with a hard demo deadline)

## Competitor Feature Analysis

| Feature | Devin (Cognition) | Replit Agent | Claude Code | Shipyard (Our Approach) |
|---------|-------------------|--------------|-------------|------------------------|
| From-scratch generation | Yes, from prompts | Yes, from descriptions | No (edits existing) | Adding in v1.3 -- PRD-driven task DAG decomposition |
| Persistent agent loop | Yes, long-running VM | Yes, in-browser | No (single invocation) | Adding in v1.3 -- FastAPI background task with EventBus |
| Intervention logging | Not published | Not published | Not applicable | Adding in v1.3 -- structured InterventionRecord with root cause |
| Comparative analysis | Not applicable | Not applicable | Not applicable | Unique to Shipyard's demo -- 7-section CODEAGENT.md |
| Live progress UI | Browser-based IDE | In-browser | Terminal output | Adding in v1.3 -- WebSocket-streamed progress panel |
| Branch isolation | Yes (VM per task) | No (single workspace) | No | Already built -- git worktrees per task via BranchManager |
| CI gating | Unknown | Basic build check | No | Already built -- CIRunner with typecheck/lint/build stages |

**Key insight:** The comparative analysis and intervention logging are genuinely unique to Shipyard. No competitor publishes structured data about their failures and limitations. This is the strongest differentiator for a demo/submission context.

## Implementation Complexity Assessment

### From-Scratch Generation (HIGH complexity)

This is the hardest feature because it requires changing a fundamental assumption: the agent edits existing files.

**What must change:**
1. `file_ops.py` needs a `create_file(path, content)` tool alongside the existing `apply_edit()`
2. The planner must generate "create" steps, not "edit" steps, for files that do not yet exist
3. The editor node must handle a code path where `file_buffer` is empty (file does not exist yet) and produce full file content instead of anchor-replacement
4. The coordinator must order file creation tasks so dependencies are satisfied (e.g., shared/ types before api/ routes that import them)
5. The validator must handle new files that may have import errors because peer files do not exist yet

**Risk:** The agent may produce files that individually pass syntax checks but fail when composed (import resolution errors, missing type definitions). Mitigation: run CI after each task merge, not just per-file.

### Comparative Analysis (HIGH complexity)

Complexity is in data collection and narrative quality, not code.

**What must work:**
1. Metrics must be collected automatically during rebuild (not manually noted)
2. Source repo must be analyzed for baseline comparison (LOC, file count, structure)
3. The LLM must generate honest, specific narrative -- not generic boilerplate
4. [FILL AFTER REBUILD] placeholders must be replaced with actual data

**Risk:** The LLM may produce flattering but inaccurate analysis. Mitigation: constrain generation with structured data (metrics dict) and validate that all numbers in the narrative match the collected data.

### 7-Section Comparative Analysis Structure

The analysis document (CODEAGENT.md sections) maps to these data sources:

| Section | Content | Data Source |
|---------|---------|-------------|
| 1. Executive Summary | Key metrics, success rate, intervention count | DAGRun results + intervention table |
| 2. Architectural Comparison | Structure of rebuilt vs original | Git diff of directory trees, file counts |
| 3. Performance Benchmarks | Time, LOC, tokens, retries | DAGRun timestamps + ModelRouter usage |
| 4. Shortcomings | Where agent failed or produced inferior code | Intervention logs + failed task analysis |
| 5. Advances Over Original | Where agent excelled | Task completion metrics + consistency analysis |
| 6. Trade-off Analysis | Human vs agent dimension comparison | Synthesized from sections 2-5 |
| 7. If You Built It Again | Lessons learned, what to redesign | LLM synthesis of failure patterns + intervention root causes |

### Everything Else (LOW-MEDIUM complexity)

The remaining features are integration work using existing infrastructure:
- POST /rebuild: wrap existing function, return run_id
- EventBus wiring: pass existing object to existing parameter
- Frontend panel: new component using existing WebSocket subscription pattern
- Intervention logging: new Pydantic model + SQLite table + manual discipline
- Railway: unblock billing + run existing scripts

## Sources

- [Oracle: What Is the AI Agent Loop?](https://blogs.oracle.com/developers/what-is-the-ai-agent-loop-the-core-architecture-behind-autonomous-ai-systems)
- [ASDLC.io: Ralph Loop Pattern](https://asdlc.io/patterns/ralph-loop/)
- [ChatPRD: Writing PRDs for AI Code Generation Tools](https://www.chatprd.ai/learn/prd-for-ai-codegen)
- [Addy Osmani: How to Write a Good Spec for AI Agents](https://addyosmani.com/blog/good-spec/)
- [LoginRadius: Auditing and Logging AI Agent Activity](https://www.loginradius.com/blog/engineering/auditing-and-logging-ai-agent-activity/)
- [Anthropic: Measuring Agent Autonomy](https://www.anthropic.com/research/measuring-agent-autonomy)
- [CodeRabbit: AI vs Human Code Generation Report](https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report)
- [IEEE: Comparative Analysis between AI Generated Code and Human Written Code](https://ieeexplore.ieee.org/document/10825958)
- Existing codebase: `scripts/ship_rebuild.py`, `agent/orchestrator/scheduler.py`, `agent/orchestrator/ship_executor.py`, `agent/events.py`, `server/main.py`, `CODEAGENT.md`

---
*Feature research for: Shipyard v1.3 -- persistent agent loop, from-scratch generation, intervention logging, comparative analysis*
*Researched: 2026-03-30*
