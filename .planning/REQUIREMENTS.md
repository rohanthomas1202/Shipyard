# Requirements: Shipyard

**Defined:** 2026-03-28
**Core Value:** The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

## v1.2 Requirements

Requirements for Autonomous Software Factory milestone. Each maps to roadmap phases.

### Orchestration

- [ ] **ORCH-01**: User can submit a codebase path and receive a DAG of executable tasks with dependency ordering
- [ ] **ORCH-02**: Orchestrator enforces DAG dependencies — no task executes before its prerequisites complete
- [ ] **ORCH-03**: Orchestrator retries failed tasks with failure-type awareness (A/B/C/D classification)
- [ ] **ORCH-04**: Orchestrator limits concurrency to 5-15 agents with queue-based scheduling
- [ ] **ORCH-05**: Orchestrator persists DAG state to enable resume from failure without restart

### Analysis

- [ ] **ANLZ-01**: Analyzer agent parses a codebase and outputs a module map with dependency graph
- [ ] **ANLZ-02**: Analyzer generates per-module summaries for context pack assembly

### Planning

- [ ] **PLAN-01**: Planner generates PRDs from module map, decomposing into buildable units
- [ ] **PLAN-02**: Planner generates Tech Specs from PRDs (API contracts, DB schema, component interfaces)
- [ ] **PLAN-03**: Planner generates a Task DAG from Tech Specs with ≤300 LOC / ≤3 files per task
- [ ] **PLAN-04**: Plan validation phase detects dependency cycles, validates contract completeness, estimates cost before execution

### Contracts

- [ ] **CNTR-01**: Contract layer stores versioned DB schema, OpenAPI definitions, and shared types
- [ ] **CNTR-02**: Agents read contracts before execution and write back changes through controlled updates
- [ ] **CNTR-03**: Contract changes include backward compatibility checks and migration strategy

### Execution

- [ ] **EXEC-01**: Each agent works in its own git branch and submits changes via PR
- [ ] **EXEC-02**: Agents receive context packs (≤5 relevant files + contracts + recent changes)
- [ ] **EXEC-03**: Agents are idempotent — safe to re-run without corrupting state
- [ ] **EXEC-04**: Module ownership model prevents conflicting edits across agents

### Validation

- [ ] **VALD-01**: Type checks, tests, lint, and build verification run after every task completion
- [ ] **VALD-02**: Failure classification routes errors to appropriate handler (auto-fix / spec / debug / replan)
- [ ] **VALD-03**: CI engine maintains always-working main branch, rejecting unstable merges

### Observability

- [ ] **OBSV-01**: Structured logging with unified format across all agents
- [ ] **OBSV-02**: Progress metrics dashboard (tasks completed, DAG coverage %, CI pass rate)
- [ ] **OBSV-03**: Task decision traces and failure heatmap for debugging

### Ship Rebuild

- [ ] **SHIP-01**: System rebuilds Ship's 47 API routes as functional endpoints
- [ ] **SHIP-02**: Core user workflows pass E2E tests
- [ ] **SHIP-03**: UI renders without critical errors
- [ ] **SHIP-04**: Rebuilt Ship deployed to a public URL
- [ ] **SHIP-05**: Automated deployment scripts handle the full deploy pipeline

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
| ORCH-01 | TBD | Pending |
| ORCH-02 | TBD | Pending |
| ORCH-03 | TBD | Pending |
| ORCH-04 | TBD | Pending |
| ORCH-05 | TBD | Pending |
| ANLZ-01 | TBD | Pending |
| ANLZ-02 | TBD | Pending |
| PLAN-01 | TBD | Pending |
| PLAN-02 | TBD | Pending |
| PLAN-03 | TBD | Pending |
| PLAN-04 | TBD | Pending |
| CNTR-01 | TBD | Pending |
| CNTR-02 | TBD | Pending |
| CNTR-03 | TBD | Pending |
| EXEC-01 | TBD | Pending |
| EXEC-02 | TBD | Pending |
| EXEC-03 | TBD | Pending |
| EXEC-04 | TBD | Pending |
| VALD-01 | TBD | Pending |
| VALD-02 | TBD | Pending |
| VALD-03 | TBD | Pending |
| OBSV-01 | TBD | Pending |
| OBSV-02 | TBD | Pending |
| OBSV-03 | TBD | Pending |
| SHIP-01 | TBD | Pending |
| SHIP-02 | TBD | Pending |
| SHIP-03 | TBD | Pending |
| SHIP-04 | TBD | Pending |
| SHIP-05 | TBD | Pending |

**Coverage:**
- v1.2 requirements: 29 total
- Mapped to phases: 0 (pending roadmap creation)
- Unmapped: 29

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28*
