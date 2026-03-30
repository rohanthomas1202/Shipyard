# Requirements: Shipyard

**Defined:** 2026-03-28
**Core Value:** The agent must reliably complete real coding tasks end-to-end -- from instruction to committed code -- without producing broken edits, missing errors, or crashing mid-run.

## v1.2 Requirements

Requirements for Autonomous Software Factory milestone. Each maps to roadmap phases.

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
- [ ] **SHIP-02**: Core user workflows pass E2E tests
- [x] **SHIP-03**: UI renders without critical errors
- [x] **SHIP-04**: Rebuilt Ship deployed to a public URL
- [x] **SHIP-05**: Automated deployment scripts handle the full deploy pipeline

## Future Requirements

Deferred beyond v1.2. Tracked but not in current roadmap.

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
| General-purpose code generation (arbitrary apps) | v1.2 proves the system on Ship specifically. Generalization is v2.0. |
| Mobile/responsive Shipyard UI | Desktop browser is the only target |
| Multi-user Shipyard access | Single-user tool |
| Ship feature parity (FleetGraph AI, FPKI auth, AWS infra) | Rebuild proves architecture, not every gov-specific integration |
| Performance optimization of rebuilt Ship | Functional correctness is the bar, not production perf tuning |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ORCH-01 | Phase 12 | Complete |
| ORCH-02 | Phase 12 | Complete |
| ORCH-03 | Phase 15 | Complete |
| ORCH-04 | Phase 15 | Complete |
| ORCH-05 | Phase 12 | Complete |
| ANLZ-01 | Phase 13 | Complete |
| ANLZ-02 | Phase 13 | Complete |
| PLAN-01 | Phase 13 | Complete |
| PLAN-02 | Phase 13 | Complete |
| PLAN-03 | Phase 13 | Complete |
| PLAN-04 | Phase 13 | Pending |
| CNTR-01 | Phase 12 | Complete |
| CNTR-02 | Phase 12 | Complete |
| CNTR-03 | Phase 14 | Pending |
| EXEC-01 | Phase 15 | Pending |
| EXEC-02 | Phase 15 | Complete |
| EXEC-03 | Phase 15 | Pending |
| EXEC-04 | Phase 15 | Complete |
| VALD-01 | Phase 15 | Complete |
| VALD-02 | Phase 15 | Complete |
| VALD-03 | Phase 15 | Complete |
| OBSV-01 | Phase 14 | Pending |
| OBSV-02 | Phase 14 | Complete |
| OBSV-03 | Phase 14 | Complete |
| SHIP-01 | Phase 16 | Complete |
| SHIP-02 | Phase 16 | Pending |
| SHIP-03 | Phase 16 | Complete |
| SHIP-04 | Phase 16 | Complete |
| SHIP-05 | Phase 16 | Complete |

**Coverage:**
- v1.2 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28*
