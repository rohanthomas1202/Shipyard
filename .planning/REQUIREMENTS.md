# Requirements: Shipyard

**Defined:** 2026-03-30
**Core Value:** The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

## v1.3 Requirements

Requirements for Ship Rebuild End-to-End milestone. Each maps to roadmap phases.

### Persistent Loop

- [ ] **LOOP-01**: User can trigger a Ship rebuild from the frontend via a "Rebuild Ship" action
- [ ] **LOOP-02**: Server exposes POST /rebuild endpoint that wraps run_rebuild() as a background task
- [ ] **LOOP-03**: run_rebuild() streams progress via EventBus emissions instead of print() statements
- [ ] **LOOP-04**: Frontend displays a live rebuild progress panel showing pipeline stages (cloning... analyzing N modules... executing 14/47... done)
- [ ] **LOOP-05**: CLI script continues to work standalone for terminal usage

### From-Scratch Generation

- [ ] **GEN-01**: Planner emits "create" task type for files that don't exist yet, distinct from "edit" tasks
- [ ] **GEN-02**: Executor has a write_file() / create_file() tool that generates complete files from PRD context
- [ ] **GEN-03**: File creation follows DAG dependency ordering — dependencies generate before dependents
- [ ] **GEN-04**: Seeding (_seed_output_from_source) is removed — all source code generated from PRDs
- [ ] **GEN-05**: Validator tolerates incomplete codebases during build (import errors for not-yet-created files)

### Intervention Logging

- [ ] **INTV-01**: Interventions are logged with structured schema (timestamp, phase, task, type, description, resolution)
- [ ] **INTV-02**: Intervention data persists in SQLite with Pydantic model and REST endpoints
- [ ] **INTV-03**: Rebuild log captures every human intervention with enough context for analysis

### Comparative Analysis

- [ ] **ANAL-01**: Agent generates all 7 sections (Executive Summary, Architectural Comparison, Performance Benchmarks, Shortcomings, Advances, Trade-off Analysis, If You Built It Again)
- [ ] **ANAL-02**: Analysis uses pre-computed metrics (task success rate, build status, intervention count, token usage) not raw logs
- [ ] **ANAL-03**: CODEAGENT.md comparative analysis section populated with specific claims and evidence from rebuild

### Deployment

- [ ] **DEPL-01**: Railway billing resolved and account active
- [ ] **DEPL-02**: Rebuilt Ship deployed to a public URL via automated scripts

## Previous Milestone Requirements

<details>
<summary>v1.2 Autonomous Software Factory (29 requirements)</summary>

### Orchestration

- [x] **ORCH-01**: User can submit a codebase path and receive a DAG of executable tasks with dependency ordering
- [x] **ORCH-02**: Orchestrator enforces DAG dependencies -- no task executes before its prerequisites complete
- [x] **ORCH-03**: Orchestrator retries failed tasks with failure-type awareness (A/B/C/D classification)
- [x] **ORCH-04**: Orchestrator limits concurrency to 5-15 agents with queue-based scheduling
- [x] **ORCH-05**: Orchestrator persists DAG state to enable resume from failure without restart

### Analysis

- [x] **ANLZ-01**: Analyzer agent parses a codebase and outputs a module map with dependency graph
- [x] **ANLZ-02**: Analyzer generates per-module summaries for context pack assembly

### Planning

- [x] **PLAN-01**: Planner generates PRDs from module map, decomposing into buildable units
- [x] **PLAN-02**: Planner generates Tech Specs from PRDs (API contracts, DB schema, component interfaces)
- [x] **PLAN-03**: Planner generates a Task DAG from Tech Specs with <=300 LOC / <=3 files per task
- [ ] **PLAN-04**: Plan validation phase detects dependency cycles, validates contract completeness, estimates cost before execution

### Contracts

- [x] **CNTR-01**: Contract layer stores versioned DB schema, OpenAPI definitions, and shared types
- [x] **CNTR-02**: Agents read contracts before execution and write back changes through controlled updates
- [ ] **CNTR-03**: Contract changes include backward compatibility checks and migration strategy

### Execution

- [ ] **EXEC-01**: Each agent works in its own git branch and submits changes via PR
- [x] **EXEC-02**: Agents receive context packs (<=5 relevant files + contracts + recent changes)
- [ ] **EXEC-03**: Agents are idempotent -- safe to re-run without corrupting state
- [x] **EXEC-04**: Module ownership model prevents conflicting edits across agents

### Validation

- [x] **VALD-01**: Type checks, tests, lint, and build verification run after every task completion
- [x] **VALD-02**: Failure classification routes errors to appropriate handler (auto-fix / spec / debug / replan)
- [x] **VALD-03**: CI engine maintains always-working main branch, rejecting unstable merges

### Observability

- [ ] **OBSV-01**: Structured logging with unified format across all agents
- [x] **OBSV-02**: Progress metrics dashboard (tasks completed, DAG coverage %, CI pass rate)
- [x] **OBSV-03**: Task decision traces and failure heatmap for debugging

### Ship Rebuild

- [x] **SHIP-01**: System rebuilds Ship's 47 API routes as functional endpoints
- [x] **SHIP-02**: Core user workflows pass E2E tests
- [x] **SHIP-03**: UI renders without critical errors
- [x] **SHIP-04**: Rebuilt Ship deployed to a public URL
- [x] **SHIP-05**: Automated deployment scripts handle the full deploy pipeline

</details>

## Future Requirements

Deferred beyond v1.3. Tracked but not in current roadmap.

### Advanced Agent Intelligence

- **INTEL-01**: Vector DB for semantic recall across agent sessions
- **INTEL-02**: Learning from past failures to improve future task decomposition
- **INTEL-03**: Multi-LLM provider support (Claude + OpenAI routing)

### Advanced Collaboration

- **COLLAB-01**: Real-time dashboard showing live agent activity across all branches
- **COLLAB-02**: Human-in-the-loop approval gates for high-risk merges

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| General-purpose code generation (arbitrary apps) | v1.3 proves the system on Ship specifically. Generalization is v2.0. |
| Mobile/responsive Shipyard UI | Desktop browser is the only target |
| Multi-user Shipyard access | Single-user tool |
| Ship feature parity (FleetGraph AI, FPKI auth, AWS infra) | Rebuild proves architecture, not every gov-specific integration |
| Performance optimization of rebuilt Ship | Functional correctness is the bar, not production perf tuning |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LOOP-01 | Phase 17 | Pending |
| LOOP-02 | Phase 17 | Pending |
| LOOP-03 | Phase 17 | Pending |
| LOOP-04 | Phase 17 | Pending |
| LOOP-05 | Phase 17 | Pending |
| GEN-01 | Phase 18 | Pending |
| GEN-02 | Phase 18 | Pending |
| GEN-03 | Phase 18 | Pending |
| GEN-04 | Phase 18 | Pending |
| GEN-05 | Phase 18 | Pending |
| INTV-01 | Phase 19 | Pending |
| INTV-02 | Phase 19 | Pending |
| INTV-03 | Phase 19 | Pending |
| ANAL-01 | Phase 20 | Pending |
| ANAL-02 | Phase 20 | Pending |
| ANAL-03 | Phase 20 | Pending |
| DEPL-01 | Phase 21 | Pending |
| DEPL-02 | Phase 21 | Pending |

**Coverage:**
- v1.3 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
