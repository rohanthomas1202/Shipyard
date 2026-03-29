# Roadmap: Shipyard

## Milestones

- ✅ **v1.0 Agent Core MVP** -- Phases 1-7 (shipped 2026-03-27)
- ✅ **v1.1 IDE UI Rebuild** -- Phases 8-11 (shipped 2026-03-27)
- 🚧 **v1.2 Autonomous Software Factory** -- Phases 12-16 (in progress)

## Phases

<details>
<summary>✅ v1.0 Agent Core MVP (Phases 1-7) -- SHIPPED 2026-03-27</summary>

- [x] Phase 1: Edit Reliability (3/3 plans) -- completed 2026-03-26
- [x] Phase 2: Validation & Infrastructure (3/3 plans) -- completed 2026-03-27
- [x] Phase 3: Context & Token Management (3/3 plans) -- completed 2026-03-26
- [x] Phase 4: Crash Recovery & Run Lifecycle (3/3 plans) -- completed 2026-03-26
- [x] Phase 5: Agent Core Features (3/3 plans) -- completed 2026-03-27
- [x] Phase 6: Ship Rebuild (3/3 plans) -- completed 2026-03-27
- [x] Phase 7: Deliverables & Deployment (3/3 plans) -- completed 2026-03-27

</details>

<details>
<summary>✅ v1.1 IDE UI Rebuild (Phases 8-11) -- SHIPPED 2026-03-27</summary>

- [x] Phase 8: Foundation -- Layout, State Architecture, TopBar (2/2 plans) -- completed 2026-03-27
- [x] Phase 9: File Explorer & Backend APIs (2/2 plans) -- completed 2026-03-27
- [x] Phase 10: Code & Diff Viewing (2/2 plans) -- completed 2026-03-27
- [x] Phase 11: Agent Activity Stream (3/3 plans) -- completed 2026-03-27

</details>

### 🚧 v1.2 Autonomous Software Factory (In Progress)

**Milestone Goal:** Build a spec-driven, DAG-orchestrated multi-agent system proven by rebuilding Ship (133K LOC) end-to-end.

- [ ] **Phase 12: Orchestrator + DAG Engine + Contract Foundation** - Core DAG scheduler, dependency enforcement, persistent state, and versioned contract store
- [ ] **Phase 13: Analyzer + Planner Agents** - Codebase analysis into module maps, three-layer plan decomposition (PRD -> Tech Spec -> Task DAG)
- [ ] **Phase 14: Observability + Contract Maturity** - Structured logging, progress metrics, failure traces, and backward-compatible contract evolution
- [ ] **Phase 15: Execution Engine + CI Validation** - Parallel agent execution with branch-per-task, failure-aware retries, and always-green CI pipeline
- [ ] **Phase 16: Ship Rebuild Proof** - Full Ship rebuild through the autonomous pipeline, deployed to a public URL

## Phase Details

### Phase 12: Orchestrator + DAG Engine + Contract Foundation
**Goal**: User can submit a codebase and get a dependency-ordered DAG of tasks, with persistent state and a versioned contract layer agents can read from
**Depends on**: Phase 11 (v1.1 complete)
**Requirements**: ORCH-01, ORCH-02, ORCH-05, CNTR-01, CNTR-02
**Success Criteria** (what must be TRUE):
  1. User submits a codebase path and receives a DAG visualization showing tasks with dependency edges
  2. Orchestrator refuses to start a task whose prerequisites have not completed
  3. Orchestrator can be killed and restarted, resuming the DAG from exactly where it left off
  4. Agents can read versioned contracts (DB schema, OpenAPI, shared types) before executing a task and write back updates through the contract store
**Plans**: 3 plans
Plans:
- [x] 12-01-PLAN.md -- DAG engine (NetworkX wrapper) + ContractStore + Pydantic models
- [x] 12-02-PLAN.md -- DAGScheduler + SQLite persistence + EventBus extension
- [ ] 12-03-PLAN.md -- Server endpoints + test DAG factory + integration tests

### Phase 13: Analyzer + Planner Agents
**Goal**: System can analyze a codebase into a module map and decompose it into a validated, executable task DAG with bounded task sizes
**Depends on**: Phase 12
**Requirements**: ANLZ-01, ANLZ-02, PLAN-01, PLAN-02, PLAN-03, PLAN-04
**Success Criteria** (what must be TRUE):
  1. Analyzer outputs a module map with dependency graph from a real codebase (Ship repo)
  2. Planner produces PRDs, Tech Specs, and a Task DAG from the module map without manual intervention
  3. Every task in the generated DAG is bounded to 300 LOC and 3 files or fewer
  4. Plan validation detects and rejects dependency cycles, flags incomplete contracts, and reports estimated cost before execution begins
**Plans**: TBD

### Phase 14: Observability + Contract Maturity
**Goal**: Operators can monitor multi-agent execution with structured logs and metrics, and contracts evolve safely with backward compatibility checks
**Depends on**: Phase 13
**Requirements**: CNTR-03, OBSV-01, OBSV-02, OBSV-03
**Success Criteria** (what must be TRUE):
  1. All agents emit structured logs in a unified format that can be filtered by agent, task, and severity
  2. A progress view shows tasks completed, DAG coverage percentage, and CI pass rate in real time
  3. Failed tasks have decision traces showing what the agent attempted and a failure heatmap identifies recurring problem areas
  4. Contract changes are validated for backward compatibility, and breaking changes require an explicit migration strategy
**Plans**: TBD
**UI hint**: yes

### Phase 15: Execution Engine + CI Validation
**Goal**: Multiple agents execute tasks in parallel with branch isolation, ownership enforcement, failure-aware retries, and a CI gate that keeps main always green
**Depends on**: Phase 14
**Requirements**: ORCH-03, ORCH-04, EXEC-01, EXEC-02, EXEC-03, EXEC-04, VALD-01, VALD-02, VALD-03
**Success Criteria** (what must be TRUE):
  1. 5-15 agents execute concurrently, each on its own git branch, submitting PRs for completed work
  2. Agents receive scoped context packs (relevant files + contracts + recent changes) and never touch files outside their module ownership
  3. Failed tasks are classified (syntax/contract/test/structural) and routed to the correct retry strategy -- auto-fix, spec update, debug, or replan
  4. CI runs type checks, tests, lint, and build after every task; unstable PRs are rejected and main branch stays green
  5. Agents are idempotent -- re-running a failed task produces the same result without corrupting shared state
**Plans**: TBD

### Phase 16: Ship Rebuild Proof
**Goal**: The autonomous pipeline rebuilds Ship's core functionality end-to-end and deploys it to a public URL, proving the system works on a real 133K LOC codebase
**Depends on**: Phase 15
**Requirements**: SHIP-01, SHIP-02, SHIP-03, SHIP-04, SHIP-05
**Success Criteria** (what must be TRUE):
  1. All 47 Ship API routes respond with correct status codes and expected payloads
  2. Core user workflows (signup, login, create/edit/delete content, navigation) pass E2E tests
  3. Ship UI renders in a browser without critical JavaScript errors or blank screens
  4. Rebuilt Ship is accessible at a public URL via automated deployment scripts
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 12 -> 13 -> 14 -> 15 -> 16

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Edit Reliability | v1.0 | 3/3 | Complete | 2026-03-26 |
| 2. Validation & Infrastructure | v1.0 | 3/3 | Complete | 2026-03-27 |
| 3. Context & Token Management | v1.0 | 3/3 | Complete | 2026-03-26 |
| 4. Crash Recovery & Run Lifecycle | v1.0 | 3/3 | Complete | 2026-03-26 |
| 5. Agent Core Features | v1.0 | 3/3 | Complete | 2026-03-27 |
| 6. Ship Rebuild | v1.0 | 3/3 | Complete | 2026-03-27 |
| 7. Deliverables & Deployment | v1.0 | 3/3 | Complete | 2026-03-27 |
| 8. Foundation -- Layout, State Architecture, TopBar | v1.1 | 2/2 | Complete | 2026-03-27 |
| 9. File Explorer & Backend APIs | v1.1 | 2/2 | Complete | 2026-03-27 |
| 10. Code & Diff Viewing | v1.1 | 2/2 | Complete | 2026-03-27 |
| 11. Agent Activity Stream | v1.1 | 3/3 | Complete | 2026-03-27 |
| 12. Orchestrator + DAG Engine + Contract Foundation | v1.2 | 2/3 | In Progress|  |
| 13. Analyzer + Planner Agents | v1.2 | 0/0 | Not started | - |
| 14. Observability + Contract Maturity | v1.2 | 0/0 | Not started | - |
| 15. Execution Engine + CI Validation | v1.2 | 0/0 | Not started | - |
| 16. Ship Rebuild Proof | v1.2 | 0/0 | Not started | - |

---
*Full v1.0 details archived in `.planning/milestones/v1.0-ROADMAP.md`*
*Full v1.1 details archived in `.planning/milestones/v1.1-ROADMAP.md`*
