# Project Research Summary

**Project:** Shipyard (Autonomous AI Coding Agent — Reliability Hardening)
**Domain:** Production-hardening of an existing LangGraph-based coding agent
**Researched:** 2026-03-26
**Confidence:** HIGH

## Executive Summary

Shipyard is a production-quality autonomous coding agent built on a solid but not yet resilient foundation: an 11-node LangGraph StateGraph with anchor-based editing, LSP validation, tiered model routing, and priority WebSocket event streaming. The agent runs correctly on the happy path but lacks the reliability layers that separate demo-quality agents from production-quality ones. Research across four domains converges on a single diagnosis: the pipeline lacks defensive programming at every layer — edits fail silently on whitespace mismatches, retries burn budget without learning from failures, context windows are built without budgets, and a server crash loses all in-flight run state.

The recommended approach is not architectural restructuring but surgical hardening in four dependency-ordered phases. Phase 1 addresses the three highest-impact, zero-risk improvements: fuzzy anchor matching to recover 10–30% of failed edits, structured outputs to eliminate LLM parse failures, and error feedback in retry prompts to break the "retry blindly" loop. Phases 2–4 layer in state management, loop prevention, and advanced validation — each building on the previous. The existing `ContextAssembler` component, tiered `ModelRouter`, and `ApprovalManager` are well-designed and simply need to be wired in; they are not gaps requiring new design, only integration work.

The primary risk is treating validation as theater: the current validator passes edits that are syntactically valid but semantically wrong, and flags pre-existing errors as edit failures. The LSP diagnostic diffing system (recently added) is the right solution but must become the canonical validation path, not an optional fallback. Run this first — it eliminates both false positives and false negatives in validation with infrastructure already in place.

## Key Findings

### Recommended Stack

The existing stack is well-chosen and should not change. LangGraph 1.1.3, FastAPI, React 19, pygls, and ast-grep-py are all correct choices. Three targeted additions deliver the most reliability value: `tenacity>=9.1.0` (retry with exponential backoff, replaces scattered ad-hoc retry logic), `structlog>=25.1.0` (structured JSON logging with run_id/node_name binding, essential for debugging async multi-step runs), and `langgraph-checkpoint-sqlite>=3.0.0` (crash recovery via persistent graph state — currently all in-flight runs are lost on server restart).

The most important version constraint is pinning `openai>=1.80.0,<2.0.0`. The 2.x SDK introduced the Responses API which replaces Chat Completions patterns used throughout `agent/llm.py`. Migrating to 2.x is a future milestone, not a hardening task. Two configuration changes require no new dependencies: enabling SQLite WAL mode (eliminates read/write lock contention between WebSocket handlers and agent writes) and enabling OpenAI structured outputs with `strict: True` (guarantees schema-compliant LLM output, eliminating the entire parse failure category in the editor and planner).

**Core technologies:**
- `tenacity>=9.1.0`: Retry with backoff — standardizes retry logic across LLM calls, LSP, and git ops
- `structlog>=25.1.0`: Structured logging — async-safe JSON logs with bound run_id for debugging
- `langgraph-checkpoint-sqlite>=3.0.0`: Graph checkpointing — enables crash recovery and run resumption
- `openai>=1.80.0,<2.0.0`: LLM provider — stay on 1.x to avoid breaking Responses API migration
- SQLite WAL mode: Configuration only — concurrent read/write without lock contention
- OpenAI structured outputs (`strict: True`): Configuration only — eliminates LLM parse failures

**Rejected additions:** PydanticAI (competing framework), circuit breakers (overkill for single-caller agent), loguru (fights stdlib integration), Postgres checkpointing (unnecessary for single-process deployment).

### Expected Features

Research across production agents (Aider, RooCode, Codex, OpenHands) identifies a clear hierarchy of what must work vs what differentiates.

**Must have (table stakes):**
- Layered edit matching with fuzzy fallbacks — every production agent does exact -> whitespace-normalized -> fuzzy; Shipyard currently fails on whitespace mismatches
- Actionable error feedback on edit failure — agent must know which anchor failed and why, to self-correct on retry
- File state freshness checking via content hashes — detect when files changed between read and edit
- Validate-rollback-retry loop with error context in retry prompt — currently retries blindly with no error information
- Token-budgeted context assembly — `ContextAssembler` exists but is not wired in; nodes build prompts with unbounded string concatenation (the #1 gap)
- Syntax validation for all edited file types — add Python syntax checking to existing TS/JS/JSON/YAML coverage
- Structured trace logging per run — `TraceLogger` exists; ensure per-run isolation (currently module-level singletons)
- Graceful cancellation — stop callback is never wired; cancel must not leave partial writes

**Should have (differentiators):**
- LSP-powered semantic validation with baseline diffing — already built, must become canonical validation path (not optional fallback)
- Tiered model routing with retry-count-based escalation — `ModelRouter` exists; add escalation on consecutive failures
- AST-aware structural refactoring via ast-grep — already built; deterministic alternative to LLM edits for mechanical changes
- Contextual error recovery (error details in retry prompts) — `error_state` exists but is not fed into editor prompt template
- Edit confidence scoring — route low-confidence edits to human review automatically
- Cost tracking per run — low effort, high visibility; track tokens per call and aggregate

**Defer to v2+:**
- Self-generated regression tests — high value (2x precision improvement per SWE-bench), but requires test infrastructure first
- Multi-file transactional edits — important for refactors, but single-file atomicity must be solid first
- Run resumption after crash — valuable, requires LangGraph checkpointing migration (significant infrastructure work)
- Context summarization on long runs — only matters after basic context assembly is wired in

**Anti-features (do not build):**
- Multi-agent parallel execution — adds coordination complexity without proportional value at this stage
- Whole-file rewriting — primary cause of broken edits; anchor-based replacement exists to prevent this
- Autonomous deployment pipelines — agent creates branch/PR; human merges
- Natural language code search (embeddings/RAG) — grep + AST search is faster and more reliable for code

### Architecture Approach

The hardening work follows five reliability layers added to the existing pipeline without restructuring it: (1) checkpointed state for crash recovery, (2) edit integrity via stale detection, fuzzy matching, and snapshot guarantees, (3) loop guards for stuck-agent termination, (4) context budget enforcement via the existing but unwired `ContextAssembler`, and (5) a validation cascade with proper error classification replacing the current flat string-based error state.

**Major components and hardening needed:**
1. **Graph Runner** (graph.py) — add `AsyncSqliteSaver` checkpointing, timeout enforcement, crash recovery
2. **Editor** (nodes/editor.py) — add fuzzy anchor matching cascade (exact -> whitespace-normalized -> fuzzy), stale detection via content hashes, pre-validation before applying, snapshot atomicity guarantee
3. **Validator** (nodes/validator.py) — enforce LSP diagnostic diffing as canonical path, typed error classification (RETRIABLE / DEGRADED / FATAL / ABORT), Python syntax checking
4. **Reader** (nodes/reader.py) — populate `file_hashes` alongside `file_buffer`, budget-aware truncation via `ContextAssembler`
5. **Context Manager** (context.py) — wire `ContextAssembler` into all LLM-calling nodes; target 40–60% context window utilization
6. **Loop Guard** (new component) — detect repeating edit patterns (same file failing 3+ times, same anchor cycling), inject into `should_continue()` routing
7. **Checkpointer** (new integration) — `AsyncSqliteSaver` enabling resume from last completed node after crash

### Critical Pitfalls

1. **Anchor mismatch cascade** — LLMs produce anchors with minor whitespace differences that cause exact-match failures; retries reproduce the same wrong anchor because the LLM sees the same numbered content. Prevention: implement layered fuzzy matching (exact -> whitespace-normalized -> Levenshtein threshold 0.95); return actual file bytes in error message so retry sees reality; prefer shorter anchors (3–5 distinctive lines, not half the file).

2. **Retry without learning** — `error_state` is stored in `AgentState` but never included in the editor's retry prompt (`EDITOR_USER` template has no `previous_error` field). All three retry attempts reproduce the same failure. Prevention: add `previous_error` to editor prompt template; escalate model tier on retry (gpt-4o-mini -> gpt-4o -> o3 already supported by `ModelRouter`); vary anchor strategy on retry 2.

3. **Validation theater (false confidence and false positives)** — validator reports pass when edits are wrong (syntax valid, semantics broken), and flags pre-existing errors as edit failures (causing rollback of correct edits). Prevention: make LSP diagnostic diffing the canonical validation path for TS/TSX (not optional fallback); layer validation in order of speed (syntax -> types -> tests); report validation coverage per edit so humans know what was actually checked.

4. **Synchronous operations blocking the event loop** — `executor_node` calls sync `subprocess.run(shell=True)` which blocks uvicorn's asyncio loop, causing WebSocket heartbeats to stop, connections to drop, and the UI to show "disconnected" during long commands. Prevention: use `asyncio.create_subprocess_exec` (not `shell=True`) everywhere; the async `run_command_async()` already exists — use it; implement command allowlist to prevent shell injection from LLM-generated commands.

5. **State bloat and context rot** — `edit_history` accumulates full file snapshots for every edit across all steps; `file_buffer` holds entire file content indefinitely; `runs` dict in `server/main.py` holds all of this in memory with no TTL. For 20-step plans on 200+ line files, state balloons to hundreds of KB, slowing checkpointing and risking context overflow. Prevention: store rollback snapshots in SQLite keyed by edit_id (not in graph state); cap `edit_history` to last 5 entries; evict `file_buffer` entries when steps complete; add TTL-based cleanup to `runs` dict.

## Implications for Roadmap

Based on research, the hardening work decomposes naturally into four dependency-ordered phases. Each phase delivers standalone value and unblocks the next.

### Phase 1: Edit Reliability and Infrastructure Foundations

**Rationale:** Edit failures are the primary failure mode. Three independent fixes — fuzzy matching, structured outputs, and error feedback in retry prompts — each recovers 10–30% of failures and have no prerequisites. Infrastructure changes (WAL mode, async subprocesses, stop callback) are similarly zero-dependency and unblock everything else. All PITFALLS.md P0 items belong here.

**Delivers:** Dramatically reduced retry rate; retries that actually learn from failures; unblocked event loop; working run cancellation.

**Addresses features:** Layered edit matching, actionable error feedback, file state freshness (hashing), structured outputs, async subprocess conversion, graceful cancellation.

**Avoids pitfalls:** Anchor mismatch cascade (#1), retry without learning (#4), event loop blocking (#5), LLM output format brittleness (#8), large file listing (#13).

**Stack additions:** `openai>=1.80.0,<2.0.0` pinned; SQLite WAL mode configured; `tenacity>=9.1.0` added.

### Phase 2: State Management and Context Integrity

**Rationale:** With edit reliability improved in Phase 1, the next bottleneck is state quality: unbounded state growth, stale file buffer reads, unwired context assembly, and planner quality issues. These are the PITFALLS.md P1 items. Phase 2 makes long runs stable and token-efficient.

**Delivers:** Bounded memory growth for long runs; fresh file content on every edit; context-budget-aware prompts; plan schema enforcement.

**Addresses features:** Token-budgeted context assembly (wire `ContextAssembler`), selective file reading (line ranges for files >200 lines), file buffer stale detection after executor steps, planner output schema validation, plan length cap.

**Avoids pitfalls:** State bloat (#2), file buffer stale reads (#7), planner generating unbounded or mistyped plans (#6).

**Stack additions:** `structlog>=25.1.0` added; structured logging wired into all nodes with `run_id` binding.

### Phase 3: Loop Prevention and Crash Recovery

**Rationale:** With reliable edits and stable state, the remaining reliability risk is catastrophic failures: stuck agents burning full retry budgets, crashed servers losing all run state. Loop guard requires error classification from Phase 2; checkpointing requires stable state management from Phase 2.

**Delivers:** Agents that detect when they're stuck and bail out gracefully; run state that survives server crashes and WebSocket disconnects; per-run timeout enforcement.

**Addresses features:** Run resumption after crash, human-in-the-loop approval persistence, run/step timeout enforcement, stop callback wired.

**Avoids pitfalls:** Retry loop without learning escalation variant (#4), no cancellation/timeout (#9), WebSocket reconnection race (#10), approval manager in-memory state loss (#14), module-level singleton tracer (#11).

**Stack additions:** `langgraph-checkpoint-sqlite>=3.0.0` integrated with `AsyncSqliteSaver`; `pytest-timeout>=2.3.0` added to dev dependencies.

### Phase 4: Advanced Validation and Observability

**Rationale:** With reliable edits, stable state, and crash recovery in place, the final layer is semantic correctness and observability. Independent verification (generator-evaluator pattern), acceptance criteria checking, and cost tracking deliver the differentiating quality signals. These require the solid foundation of Phases 1–3 — verifying garbage edits is wasteful.

**Delivers:** Semantic correctness checks beyond syntax/types; cost visibility per run; LangSmith trace annotations; validation coverage reporting.

**Addresses features:** Independent verification via acceptance criteria, cost tracking per run, LangSmith trace annotations, edit confidence scoring (LSP results inform routing to human review).

**Avoids pitfalls:** Edit produces valid syntax but wrong semantics (#12), validation theater (false confidence part) (#3).

**Deferred to post-Phase 4:** Self-generated regression tests (requires test infrastructure), multi-file transactional edits (requires solid single-file atomicity), context summarization on very long runs.

### Phase Ordering Rationale

- Phase 1 before all others because edit failures are P0 and have no prerequisites — fixing them delivers immediate value and reduces noise in all subsequent work.
- Phase 2 before Phase 3 because checkpointing large unbounded state is counterproductive — state must be bounded before persisting it efficiently.
- Phase 3 before Phase 4 because independent verification of unstable edits wastes tokens — the validator needs reliable input to produce reliable output.
- Anti-features (whole-file rewriting, multi-agent parallelism, RAG search) are explicitly excluded at every phase; the research is unambiguous that these add complexity without reliability gains at this stage.

### Research Flags

Phases with standard, well-documented patterns (skip research-phase during planning):
- **Phase 1 — Fuzzy anchor matching:** Aider and RooCode both document this pattern exhaustively. Implementation is mechanical.
- **Phase 1 — Structured outputs:** OpenAI official docs. No ambiguity.
- **Phase 1 — WAL mode / async subprocesses:** SQLite official docs, asyncio stdlib. Standard patterns.
- **Phase 3 — LangGraph checkpointing:** Official LangGraph docs, `AsyncSqliteSaver` is the documented primary mechanism.

Phases that may benefit from targeted research during planning:
- **Phase 2 — ContextAssembler wiring:** The component exists and is well-designed, but the integration points across multiple node prompt templates need careful mapping before implementation. A quick audit of all `EDITOR_USER`, `PLANNER_USER` prompt templates is warranted.
- **Phase 2 — State eviction strategy:** The tradeoff between rollback capability (need N snapshots) and memory growth (want few snapshots) needs to be calibrated against realistic run lengths. The "last 5 entries" suggestion from research needs validation against actual run data.
- **Phase 4 — Independent verification latency/cost:** The generator-evaluator pattern adds a fast-model LLM call per complex edit. Acceptable cost at single-user scale, but the routing threshold (when to trigger verification) needs empirical tuning.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations verified against PyPI, official docs. The `openai <2.0.0` pin is critical and well-documented. Only FastAPI floor version is MEDIUM (inferred from release notes). |
| Features | HIGH | Sourced from comparative analysis of Aider, RooCode, Codex, OpenHands plus SWE-bench research and Martin Fowler/Simon Willison writing. Strong cross-source agreement on priorities. |
| Architecture | HIGH | LangGraph checkpointing from official docs. Fuzzy matching from Aider docs + quantitative benchmarks. Content hashing from oh-my-pi with benchmark data. Context budget from advanced-context-engineering spec. |
| Pitfalls | HIGH | Forensic audit of real-world agent PRs, LangGraph-specific state bloat research, FastAPI WebSocket disconnect analysis. All pitfalls are grounded in specific code locations in Shipyard. |

**Overall confidence:** HIGH

### Gaps to Address

- **Fuzzy match threshold tuning:** ARCHITECTURE.md recommends difflib threshold 0.85 for fuzzy anchor matching, but notes this requires empirical testing on Shipyard's specific edit patterns. Start with 0.85, add a metric to track fuzzy match acceptance rate, adjust based on false positive rate (fuzzy matches that produce incorrect edits).

- **State eviction calibration:** Research recommends capping `edit_history` to last 5 entries, but the right number depends on maximum realistic rollback depth. Audit the longest rollback chain in existing trace logs before hard-coding the cap.

- **LSP server stability under load:** PITFALLS.md notes the LSP server crash fallback path must exist, but the current `LspManager` behavior on repeated crashes is not fully specified. Clarify restart policy (how many restarts before degraded mode?) during Phase 3 planning.

- **OpenAI SDK 2.x migration timeline:** Pinning `<2.0.0` is the right short-term call, but the Responses API is the future direction. Flag this as a planned migration milestone after Phase 4 is complete.

## Sources

### Primary (HIGH confidence)
- [LangGraph PyPI + Docs](https://pypi.org/project/langgraph/) — version verification, checkpointing API
- [LangGraph Checkpoint SQLite PyPI](https://pypi.org/project/langgraph-checkpoint-sqlite/) — `AsyncSqliteSaver` API
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) — `strict: True` schema compliance
- [OpenAI Responses API Migration Guide](https://platform.openai.com/docs/guides/migrate-to-responses) — confirmed breaking change in 2.x
- [SQLite WAL Mode](https://www.sqlite.org/wal.html) — concurrent read/write configuration
- [LangGraph Persistence Docs](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpointer thread_id resumption
- [Aider Edit Formats](https://aider.chat/docs/more/edit-formats.html) — layered matching: exact -> whitespace -> indentation -> fuzzy
- [Aider GPT-4 Benchmarks](https://aider.chat/docs/benchmarks.html) — quantitative edit format success rates
- [SWE-Agent NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf) — repeated edit failure modes
- [Tenacity PyPI](https://pypi.org/project/tenacity/) — version 9.1.4 verified
- [structlog docs](https://www.structlog.org/en/stable/) — async support, stdlib integration
- [Coding Agent Loop Spec (strongdm/attractor)](https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md) — loop guard patterns

### Secondary (MEDIUM confidence)
- [Code Surgery: How AI Assistants Make Precise Edits](https://fabianhertwig.com/blog/coding-assistants-file-edits/) — comparative edit strategy analysis across Codex, Aider, RooCode, Cursor, OpenHands
- [Advanced Context Engineering for Coding Agents](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/ace-fca.md) — 40–60% context utilization target
- [oh-my-pi hash-anchored edits](https://github.com/can1357/oh-my-pi) — stale detection benchmark across 16 models
- [Advanced Error Handling in LangGraph](https://sparkco.ai/blog/advanced-error-handling-strategies-in-langgraph-applications) — node-level error classification patterns
- [The Memory Leak in the Loop](https://azguards.com/ai-engineering/the-memory-leak-in-the-loop-optimizing-custom-state-reducers-in-langgraph/) — LangGraph state bloat from `add_messages` reducer
- [Where Autonomous Coding Agents Fail](https://medium.com/@vivek.babu/where-autonomous-coding-agents-fail-a-forensic-audit-of-real-world-prs-59d66e33efe9) — forensic audit of production agent PRs
- [Simon Willison: Anti-patterns in Agentic Engineering](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/) — what not to build
- [Context Engineering for Coding Agents (Martin Fowler)](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html) — context management strategies

### Tertiary (MEDIUM-LOW confidence)
- [SWE-bench and Code Agents as Testers](https://arxiv.org/html/2406.12952v1) — test generation improving edit precision 2x (needs validation on Shipyard's specific task types)
- [Hermes Agent Independent Verification](https://github.com/NousResearch/hermes-agent/issues/406) — generator-evaluator pattern for semantic correctness
- [Agentic Coding Trends Report 2026](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf) — industry context

---
*Research completed: 2026-03-26*
*Ready for roadmap: yes*
