# Roadmap: Shipyard

## Milestones

- ✅ **v1.0 Agent Core MVP** -- Phases 1-7 (shipped 2026-03-27)
- ✅ **v1.1 IDE UI Rebuild** -- Phases 8-11 (shipped 2026-03-27)
- ✅ **v1.2 Autonomous Software Factory** -- Phases 12-16 (shipped 2026-03-30)
- 🚧 **v1.3 Ship Rebuild End-to-End** -- Phases 17-21 (in progress)

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

<details>
<summary>✅ v1.2 Autonomous Software Factory (Phases 12-16) -- SHIPPED 2026-03-30</summary>

- [x] Phase 12: Orchestrator + DAG Engine + Contract Foundation (3/3 plans) -- completed 2026-03-29
- [x] Phase 13: Analyzer + Planner Agents (4/4 plans) -- completed 2026-03-29
- [x] Phase 14: Observability + Contract Maturity (4/4 plans) -- completed 2026-03-29
- [x] Phase 15: Execution Engine + CI Validation (4/4 plans) -- completed 2026-03-29
- [x] Phase 16: Ship Rebuild Proof (4/4 plans) -- completed 2026-03-30

</details>

### 🚧 v1.3 Ship Rebuild End-to-End (In Progress)

**Milestone Goal:** Prove the autonomous pipeline by rebuilding Ship entirely from scratch -- no seeding -- with a persistent agent loop, live UI integration, structured intervention logging, and a 7-section comparative analysis.

- [ ] **Phase 17: Persistent Loop Infrastructure** - POST /rebuild endpoint, EventBus streaming, frontend progress panel, and CLI compatibility
- [ ] **Phase 18: From-Scratch Code Generation** - Create-step kind in planner, file creation tool, DAG dependency ordering, seeding removal
- [ ] **Phase 19: Intervention Logging** - Structured intervention schema, SQLite persistence, REST endpoints for capture and retrieval
- [ ] **Phase 20: Rebuild Execution & Comparative Analysis** - End-to-end Ship rebuild from scratch, metric collection, and 7-section analysis generation
- [ ] **Phase 21: Railway Deployment** - Billing resolution and rebuilt Ship deployed to public URL

## Phase Details

### Phase 17: Persistent Loop Infrastructure
**Goal**: Users can trigger, observe, and cancel a Ship rebuild from both the frontend and CLI, with real-time progress streaming through the existing WebSocket infrastructure
**Depends on**: Phase 16 (v1.2 complete)
**Requirements**: LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05
**Success Criteria** (what must be TRUE):
  1. User clicks "Rebuild Ship" in the frontend and sees a live progress panel updating through pipeline stages (cloning, analyzing, planning, executing, building)
  2. POST /rebuild returns a run_id and the rebuild executes as a managed background task that survives WebSocket disconnects
  3. Rebuild progress events stream through the existing WebSocket connection -- no polling, no separate endpoint
  4. User can run the rebuild CLI script standalone in a terminal and see equivalent progress output
  5. A crashed or cancelled rebuild updates its status to failed/cancelled in the database -- no silent deaths
**Plans**: TBD
**UI hint**: yes

### Phase 18: From-Scratch Code Generation
**Goal**: The agent generates every file in a codebase from PRD context alone -- no seeding, no copying from source -- with dependency-aware ordering so foundational files exist before their consumers
**Depends on**: Phase 17
**Requirements**: GEN-01, GEN-02, GEN-03, GEN-04, GEN-05
**Success Criteria** (what must be TRUE):
  1. Planner emits "create" tasks (distinct from "edit") for files that do not yet exist, with explicit file paths and PRD context
  2. Executor generates complete file contents from PRD descriptions using a write_file/create_file tool -- not anchor-based editing
  3. DAG execution creates foundational files (types, models, shared utilities) before files that import them
  4. The _seed_output_from_source() workaround is removed and the rebuild starts from an empty output directory
  5. Validator does not fail on import errors for files that are scheduled to be created later in the DAG
**Plans**: TBD

### Phase 19: Intervention Logging
**Goal**: Every human intervention during a rebuild is captured with structured context so it can be analyzed after the run completes
**Depends on**: Phase 18
**Requirements**: INTV-01, INTV-02, INTV-03
**Success Criteria** (what must be TRUE):
  1. User can log an intervention with structured fields (timestamp, phase, task, type, description, resolution) via a REST endpoint or frontend control
  2. Intervention records persist in SQLite and are retrievable via GET endpoint filtered by rebuild run
  3. Each intervention captures enough context (current DAG state, affected files, agent state) to understand why human help was needed
**Plans**: TBD

### Phase 20: Rebuild Execution & Comparative Analysis
**Goal**: The autonomous pipeline rebuilds Ship from scratch end-to-end, collects structured metrics, and generates a 7-section comparative analysis with evidence-backed claims
**Depends on**: Phase 19
**Requirements**: ANAL-01, ANAL-02, ANAL-03
**Success Criteria** (what must be TRUE):
  1. Ship rebuild completes from an empty repo using PRD-driven generation with all interventions logged
  2. Agent generates all 7 analysis sections (Executive Summary, Architectural Comparison, Performance Benchmarks, Shortcomings, Advances, Trade-off Analysis, If You Built It Again) with no empty sections
  3. Analysis cites pre-computed metrics (task success rate, build pass/fail, intervention count, token usage, time per phase) -- not hallucinated numbers from raw logs
  4. CODEAGENT.md comparative analysis section is populated with specific claims and evidence from the actual rebuild
**Plans**: TBD

### Phase 21: Railway Deployment
**Goal**: The rebuilt Ship app is deployed to a public URL where anyone can access it, proving the autonomous pipeline produces deployable software
**Depends on**: Phase 20
**Requirements**: DEPL-01, DEPL-02
**Success Criteria** (what must be TRUE):
  1. Railway account billing is resolved and the account is active (verified before deployment attempt)
  2. Rebuilt Ship is accessible at a public Railway URL with working routes and no critical errors
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 17 -> 18 -> 19 -> 20 -> 21

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
| 12. Orchestrator + DAG Engine + Contract Foundation | v1.2 | 3/3 | Complete | 2026-03-29 |
| 13. Analyzer + Planner Agents | v1.2 | 4/4 | Complete | 2026-03-29 |
| 14. Observability + Contract Maturity | v1.2 | 4/4 | Complete | 2026-03-29 |
| 15. Execution Engine + CI Validation | v1.2 | 4/4 | Complete | 2026-03-29 |
| 16. Ship Rebuild Proof | v1.2 | 4/4 | Complete | 2026-03-30 |
| 17. Persistent Loop Infrastructure | v1.3 | 0/0 | Not started | - |
| 18. From-Scratch Code Generation | v1.3 | 0/0 | Not started | - |
| 19. Intervention Logging | v1.3 | 0/0 | Not started | - |
| 20. Rebuild Execution & Comparative Analysis | v1.3 | 0/0 | Not started | - |
| 21. Railway Deployment | v1.3 | 0/0 | Not started | - |

---
*Full v1.0 details archived in `.planning/milestones/v1.0-ROADMAP.md`*
*Full v1.1 details archived in `.planning/milestones/v1.1-ROADMAP.md`*
