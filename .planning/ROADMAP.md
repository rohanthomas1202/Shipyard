# Roadmap: Shipyard

## Overview

Shipyard is a brownfield hardening project. The agent pipeline exists but breaks under real workloads: edits fail on whitespace mismatches, retries learn nothing, validation flags false positives, and crashes lose all state. This roadmap hardens the pipeline in dependency order — edit reliability first (everything depends on correct edits), then validation and infrastructure, then context management, then crash recovery, then agent core features — and culminates in the Ship rebuild integration test and final deliverables. Each phase delivers standalone value and unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Edit Reliability** - Fuzzy anchor matching, error feedback in retries, indentation preservation, file freshness checks, and structured LLM outputs
- [ ] **Phase 2: Validation & Infrastructure** - Python syntax checking, LSP diagnostic diffing, circuit breaker, async subprocesses, WAL mode
- [ ] **Phase 3: Context & Token Management** - Wire ContextAssembler into all nodes, line-range reads for large files, per-run cost tracking
- [ ] **Phase 4: Crash Recovery & Run Lifecycle** - LangGraph checkpointing, graceful cancellation, LangSmith tracing with shared links
- [ ] **Phase 5: Agent Core Features** - Persistent agent loop, external context injection, multi-agent coordination, git operations end-to-end
- [ ] **Phase 6: Ship Rebuild** - Agent rebuilds the Ship app from scratch, every intervention documented
- [ ] **Phase 7: Deliverables & Deployment** - CODEAGENT.md, comparative analysis, dev log, cost analysis, demo video, deployment

## Phase Details

### Phase 1: Edit Reliability
**Goal**: Edits succeed on first attempt far more often, and retries that do occur are informed by specific failure context
**Depends on**: Nothing (first phase)
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, VALID-01, INFRA-03
**Success Criteria** (what must be TRUE):
  1. Editor successfully applies edits to files with minor whitespace/formatting differences without failing (fuzzy fallback chain works)
  2. When an edit fails, the retry prompt includes the specific anchor that failed, what was found instead, and the similarity score
  3. Edited code preserves the indentation style (tabs vs spaces, nesting level) of the surrounding file context
  4. Editor detects when a file has changed since last read and re-reads before applying edits
  5. All LLM calls return schema-compliant structured output — zero JSON parse failures
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md — Fuzzy anchor matching, indentation preservation, content hashing (EDIT-01, EDIT-03, EDIT-04)
- [x] 01-02-PLAN.md — Structured LLM outputs via OpenAI parse() API (INFRA-03)
- [x] 01-03-PLAN.md — Error feedback in retries, file freshness, validator error details (EDIT-02, EDIT-04, VALID-01)

### Phase 2: Validation & Infrastructure
**Goal**: Validator catches real errors without false positives, and infrastructure does not block the event loop or cause data contention
**Depends on**: Phase 1
**Requirements**: VALID-02, VALID-03, VALID-04, INFRA-01, INFRA-02
**Success Criteria** (what must be TRUE):
  1. Python files are syntax-checked after edits and real syntax errors are caught
  2. LSP diagnostic diffing reports only NEW errors introduced by an edit (pre-existing errors are ignored), with graceful fallback when LSP is unavailable
  3. After 2 identical errors on the same file/step, the validator escalates model tier or skips the step instead of retrying the same approach
  4. Long-running subprocess calls (esbuild, tsc, git) do not block the event loop or drop WebSocket connections
  5. SQLite handles concurrent reads and writes without lock contention errors
**Plans**: 3 plans
Plans:
- [x] 02-01-PLAN.md — Async subprocess conversion and SQLite WAL mode (INFRA-01, INFRA-02)
- [ ] 02-02-PLAN.md — Python syntax checking and LSP fallback hardening (VALID-02, VALID-03)
- [x] 02-03-PLAN.md — Circuit breaker for repeated validation errors (VALID-04)

### Phase 3: Context & Token Management
**Goal**: LLM prompts are token-budgeted and context-aware, and token spend is tracked per run
**Depends on**: Phase 2
**Requirements**: CTX-01, CTX-02, LIFE-02
**Success Criteria** (what must be TRUE):
  1. All LLM-calling nodes (planner, editor, reader, validator, refactor) construct prompts through ContextAssembler with ranked priority filling
  2. Files over 200 lines are read in relevant line ranges rather than loaded in full
  3. Each run surfaces total token usage (input/output) and estimated cost in traces and UI
**Plans**: 3 plans
Plans:
- [x] 03-01-PLAN.md — LLMResult dataclasses, TokenTracker, router usage accumulation (LIFE-02)
- [x] 03-02-PLAN.md — Line-range reads for large files in reader_node (CTX-02)
- [x] 03-03-PLAN.md — Wire ContextAssembler into planner/editor, reporter token summary (CTX-01, LIFE-02)

### Phase 4: Crash Recovery & Run Lifecycle
**Goal**: Runs survive crashes and disconnects, can be cancelled cleanly, and produce complete observable traces
**Depends on**: Phase 3
**Requirements**: INFRA-04, LIFE-01, LIFE-03
**Success Criteria** (what must be TRUE):
  1. After a server crash or restart, a previously running agent resumes from the last completed node (not from scratch)
  2. User can cancel a running agent mid-execution and the workspace has no partial writes or corrupted files
  3. LangSmith traces capture complete structured execution paths, with at least two shared trace links showing different paths (normal run and error recovery)
**Plans**: 3 plans
Plans:
- [ ] 04-01-PLAN.md — AsyncSqliteSaver checkpointing and crash recovery resume (INFRA-04)
- [ ] 04-02-PLAN.md — Graceful cancellation with edit rollback (LIFE-01)
- [ ] 04-03-PLAN.md — LangSmith tracing with shared trace links (LIFE-03)

### Phase 5: Agent Core Features
**Goal**: Agent operates as a persistent, context-aware system that coordinates work and manages git workflows
**Depends on**: Phase 4
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04
**Success Criteria** (what must be TRUE):
  1. Agent accepts a new instruction after completing a previous one without server restart
  2. Agent uses injected external context (specs, schemas, test results) in LLM generation when provided at runtime
  3. System can spawn at least two agents working in parallel or sequence and merge their outputs correctly
  4. Agent can branch, stage, commit, push, and create a PR via GitHub API in a single end-to-end flow
**Plans**: 3 plans
Plans:
- [ ] 01-01-PLAN.md — Fuzzy anchor matching, indentation preservation, content hashing (EDIT-01, EDIT-03, EDIT-04)
- [ ] 01-02-PLAN.md — Structured LLM outputs via OpenAI parse() API (INFRA-03)
- [ ] 01-03-PLAN.md — Error feedback in retries, file freshness, validator error details (EDIT-02, EDIT-04, VALID-01)

### Phase 6: Ship Rebuild
**Goal**: The agent proves itself by rebuilding the Ship app from scratch — the ultimate integration test
**Depends on**: Phase 5
**Requirements**: SHIP-01, SHIP-02
**Success Criteria** (what must be TRUE):
  1. Agent rebuilds the Ship app from natural language instructions with minimal human intervention (interventions counted and documented)
  2. Every human intervention during the rebuild is logged with what broke, what was done manually, and what it reveals about agent limitations
**Plans**: 3 plans
Plans:
- [ ] 01-01-PLAN.md — Fuzzy anchor matching, indentation preservation, content hashing (EDIT-01, EDIT-03, EDIT-04)
- [ ] 01-02-PLAN.md — Structured LLM outputs via OpenAI parse() API (INFRA-03)
- [ ] 01-03-PLAN.md — Error feedback in retries, file freshness, validator error details (EDIT-02, EDIT-04, VALID-01)

### Phase 7: Deliverables & Deployment
**Goal**: All submission artifacts are complete and both the agent and the agent-built Ship app are publicly accessible
**Depends on**: Phase 6
**Requirements**: DELIV-01, DELIV-02, DELIV-03, DELIV-04, DELIV-05, DELIV-06
**Success Criteria** (what must be TRUE):
  1. CODEAGENT.md contains all 8 required sections with substantive content drawn from actual development experience
  2. Comparative analysis covers all 7 sections comparing agent-built Ship vs the original
  3. AI Development Log and Cost Analysis are complete with real data (not placeholders)
  4. Demo video (3-5 min) shows surgical edit, multi-agent task, and Ship rebuild example
  5. Agent and agent-built Ship app are both deployed and publicly accessible on Heroku/Railway
**Plans**: 3 plans
Plans:
- [ ] 01-01-PLAN.md — Fuzzy anchor matching, indentation preservation, content hashing (EDIT-01, EDIT-03, EDIT-04)
- [ ] 01-02-PLAN.md — Structured LLM outputs via OpenAI parse() API (INFRA-03)
- [ ] 01-03-PLAN.md — Error feedback in retries, file freshness, validator error details (EDIT-02, EDIT-04, VALID-01)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Edit Reliability | 3/3 | Complete | - |
| 2. Validation & Infrastructure | 0/3 | Planning | - |
| 3. Context & Token Management | 0/3 | Planning | - |
| 4. Crash Recovery & Run Lifecycle | 0/3 | Planned | - |
| 5. Agent Core Features | 0/TBD | Not started | - |
| 6. Ship Rebuild | 0/TBD | Not started | - |
| 7. Deliverables & Deployment | 0/TBD | Not started | - |
