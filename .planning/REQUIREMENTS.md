# Requirements: Shipyard

**Defined:** 2026-03-26
**Core Value:** The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

## v1 Requirements

Requirements for reliability hardening milestone. Each maps to roadmap phases.

### Edit Precision

- [x] **EDIT-01**: Editor implements layered anchor matching with fuzzy fallbacks (exact -> whitespace-normalized -> fuzzy Levenshtein) so edits succeed despite trivial formatting differences
- [x] **EDIT-02**: Editor provides actionable error feedback when anchor matching fails (which anchor, what was found instead, similarity score) and feeds this into retry prompts
- [x] **EDIT-03**: Editor preserves indentation style of surrounding code when applying replacements (detect tabs vs spaces, indentation level)
- [x] **EDIT-04**: Editor checks file freshness via content checksums before applying edits, re-reads file if content has changed since last read

### Validation

- [x] **VALID-01**: Validator feeds specific error details (file, line, error message, validator output) into the retry prompt so retries are informed, not blind
- [ ] **VALID-02**: Validator checks Python file syntax via py_compile or ast.parse after edits
- [ ] **VALID-03**: LSP diagnostic diffing reliably detects only NEW errors introduced by edits (baseline vs post-edit comparison), with graceful fallback when LSP is unavailable
- [ ] **VALID-04**: Validator implements circuit breaker — after 2 identical errors on same file/step, escalates model tier or skips step instead of retrying same approach

### Context Management

- [ ] **CTX-01**: ContextAssembler is wired into all LLM-calling nodes (planner, editor, reader, validator, refactor) with token-budgeted prompt construction using ranked priorities
- [ ] **CTX-02**: Reader supports line-range reads for files >200 lines, loading only relevant sections to save tokens and reduce noise

### Infrastructure

- [x] **INFRA-01**: All subprocess calls in executor and validator nodes are async (non-blocking), preventing event loop stalls that kill WebSocket connections
- [x] **INFRA-02**: SQLite database runs in WAL mode for concurrent read/write access
- [x] **INFRA-03**: All LLM calls use OpenAI structured outputs with strict: true to eliminate JSON parse failures
- [ ] **INFRA-04**: LangGraph uses AsyncSqliteSaver for persistent checkpointing, enabling crash recovery and run resumption

### Run Lifecycle

- [ ] **LIFE-01**: User can gracefully cancel a running agent mid-execution with clean state rollback (no partial writes, no corrupted files)
- [ ] **LIFE-02**: Each LLM call tracks token usage (input/output) and aggregates cost per run, surfaced in traces and UI
- [ ] **LIFE-03**: LangSmith tracing captures complete structured traces with at least two shared trace links showing different execution paths (normal run + error recovery)

### Agent Core (from PDF)

- [ ] **CORE-01**: Agent runs in a persistent loop accepting new instructions without restarting
- [ ] **CORE-02**: Agent accepts injected external context (specs, schemas, test results, previous outputs) at runtime and uses it in LLM generation
- [ ] **CORE-03**: Multi-agent coordination — system can spawn at least two agents working in parallel or sequence, merge their outputs correctly
- [ ] **CORE-04**: Git operations work end-to-end — branch creation, staging, commit, push, PR creation via GitHub API

### Ship Rebuild

- [ ] **SHIP-01**: Agent successfully rebuilds the Ship app from scratch using natural language instructions with minimal human intervention
- [ ] **SHIP-02**: Every human intervention during the rebuild is documented in the rebuild log with what broke, what was done, and what it reveals

### Deliverables

- [ ] **DELIV-01**: CODEAGENT.md complete with all 8 sections (Agent Architecture, File Editing Strategy, Multi-Agent Design, Trace Links, Architecture Decisions, Ship Rebuild Log, Comparative Analysis, Cost Analysis)
- [ ] **DELIV-02**: Comparative analysis covers all 7 required sections (Executive Summary, Architectural Comparison, Performance Benchmarks, Shortcomings, Advances, Trade-off Analysis, If You Built It Again)
- [ ] **DELIV-03**: AI Development Log submitted (Tools & Workflow, Effective Prompts, Code Analysis, Strengths & Limitations, Key Learnings)
- [ ] **DELIV-04**: AI Cost Analysis with actual dev spend and production cost projections at 100/1K/10K users
- [ ] **DELIV-05**: Demo video (3-5 min) showing surgical edit, multi-agent task, and Ship rebuild example
- [ ] **DELIV-06**: Agent and agent-built Ship app both deployed and publicly accessible on Heroku/Railway

## v2 Requirements

### Advanced Reliability

- **ADV-01**: Context summarization on long runs (5+ steps) to prevent context rot
- **ADV-02**: Self-generated regression tests before/after edits for higher precision
- **ADV-03**: Multi-file transactional edits (all-or-nothing across related files)
- **ADV-04**: Edit confidence scoring with automatic routing to supervised mode

### Advanced Context

- **ADV-05**: Conversation memory across runs within the same project
- **ADV-06**: Smart file discovery (find relevant files without user specifying them)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Authentication/authorization | Single-user tool, unnecessary for v1 |
| Claude/Anthropic SDK support | Unlimited OpenAI tokens, no business need |
| Mobile UI | Desktop browser only target |
| Real-time collaboration | Single-user agent |
| Plugin/extension system | Hardcoded pipeline sufficient for v1 |
| Natural language code search (RAG/embeddings) | Grep + ast-grep is faster and more reliable |
| Streaming edit application | Too complex, requires separate apply model |
| Automatic conflict resolution | Serialize edits to same file instead |
| Whole-file rewriting | Anchor-based replacement is the committed strategy |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EDIT-01 | Phase 1 | Complete |
| EDIT-02 | Phase 1 | Complete |
| EDIT-03 | Phase 1 | Complete |
| EDIT-04 | Phase 1 | Complete |
| VALID-01 | Phase 1 | Complete |
| VALID-02 | Phase 2 | Pending |
| VALID-03 | Phase 2 | Pending |
| VALID-04 | Phase 2 | Pending |
| CTX-01 | Phase 3 | Pending |
| CTX-02 | Phase 3 | Pending |
| INFRA-01 | Phase 2 | Complete |
| INFRA-02 | Phase 2 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 4 | Pending |
| LIFE-01 | Phase 4 | Pending |
| LIFE-02 | Phase 3 | Pending |
| LIFE-03 | Phase 4 | Pending |
| CORE-01 | Phase 5 | Pending |
| CORE-02 | Phase 5 | Pending |
| CORE-03 | Phase 5 | Pending |
| CORE-04 | Phase 5 | Pending |
| SHIP-01 | Phase 6 | Pending |
| SHIP-02 | Phase 6 | Pending |
| DELIV-01 | Phase 7 | Pending |
| DELIV-02 | Phase 7 | Pending |
| DELIV-03 | Phase 7 | Pending |
| DELIV-04 | Phase 7 | Pending |
| DELIV-05 | Phase 7 | Pending |
| DELIV-06 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after roadmap creation*
