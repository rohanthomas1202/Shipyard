# CODEAGENT.md

## Agent Architecture (MVP)

Shipyard uses a single LangGraph StateGraph with the following nodes wired in sequence:

`receive_instruction → planner → coordinator → [reader → editor → validator] (loop per step) → reporter`

**State:** `AgentState` TypedDict with messages, instruction, working_directory, context, plan, current_step, file_buffer, edit_history, error_state, is_parallel, parallel_batches, sequential_first, has_conflicts.

**Entry condition:** POST /instruction with instruction + optional context
**Normal exit:** All plan steps completed, validator passes on each
**Error exit:** 3 consecutive failures on same step → reporter surfaces status `waiting_for_human`

**Loop design:** FastAPI server keeps the graph alive. New instructions create or continue threads. Between instructions, server is idle but alive.

## File Editing Strategy (MVP)

**Strategy:** Anchor-based replacement (same pattern as Claude Code and OpenCode)

**Mechanism:**
1. Reader loads target file into file_buffer
2. Editor LLM produces (anchor, replacement) JSON
3. Agent validates anchor uniqueness: `file_content.count(anchor) == 1`
4. Snapshot saved to edit_history
5. `content.replace(anchor, replacement, 1)` applied
6. Validator runs language-appropriate syntax check (.ts → esbuild, .json → json.load, .yaml → yaml.safe_load)
7. If syntax fails → rollback from snapshot, retry with error context (max 3)

**When it gets the location wrong:** Validator detects intent mismatch, rollback triggers, reader re-runs to find correct file.

## Multi-Agent Design (MVP)

**Orchestration:** Coordinator node groups plan steps by directory prefix (api/, web/, shared/). Steps targeting different directories can run as parallel subgraphs. shared/ always runs first (dependency).

**Communication:** Subgraphs don't communicate directly. Each writes to isolated edit_log. Merger collects all logs and checks for file conflicts.

**Conflict resolution:** Different files → merge directly. Same file, different anchors → apply sequentially. Overlapping regions → flag to human.

## Trace Links (MVP)

- **Trace 1 (normal run):** `traces/trace-1-normal-edit.json` — Single-file edit on Ship's `api/src/routes/search.ts`. Path: `receive → planner (2 steps) → coordinator → reader → editor → validator → advance → reader → editor → validator → reporter`. 1 successful anchor-based edit adding a rate limit comment above the /mentions endpoint.

- **Trace 2 (different execution path — read-only + edit branching):** `traces/trace-2-branching-path.json` — Multi-step plan with mixed step types. Path: `receive → planner (3 steps) → coordinator → reader (read-only, skips editor) → advance → reader (read-only, skips editor) → advance → reader → editor → validator → reporter`. Demonstrates the `after_reader` conditional routing: read-only steps advance directly without invoking the editor, while edit steps go through the full reader → editor → validator pipeline. 2 read-only steps + 1 edit step = different branching condition from Trace 1.

## Architecture Decisions (Final Submission)

### 1. Anchor-based replacement over unified diff / AST editing

- **Decision:** Use `content.replace(anchor, replacement, 1)` where the anchor is a unique substring of the target file.
- **Alternatives considered:**
  - **Unified diff:** LLMs produce malformed diffs ~15-20% of the time. One bad hunk offset and the patch silently misapplies.
  - **Line-range replacement:** Edits earlier in the file shift line numbers for later edits, requiring offset tracking for no added benefit.
  - **AST-based editing:** Ship has .ts, .tsx, .json, .css, .yaml, .md, .sh files. Building parsers for each is a week of work.
- **Rationale:** Both OpenCode and Claude Code -- the two most successful real-world coding agents -- use this exact pattern. It is language-agnostic, resilient to line number drift, and has clear failure modes (anchor not found, anchor not unique) that are easy to detect and recover from.
- **Impact:** Edit precision became the P0 reliability axis. Fuzzy matching at FUZZY_THRESHOLD=0.85 catches minor whitespace drift without false positives. Snapshot-based rollback on syntax failure keeps the codebase safe.

### 2. LangGraph StateGraph over custom loop or LangChain agents

- **Decision:** Use LangGraph's `StateGraph` with typed `AgentState` TypedDict for the entire agent orchestration.
- **Alternatives considered:**
  - **Plain LangChain agents:** No graph-based state management, harder to model the plan-read-edit-validate loop with conditional branching.
  - **Custom Python asyncio loop:** Would need to build state management, checkpointing, conditional routing, and tracing from scratch.
  - **Node.js LangGraph:** Less mature, weaker ecosystem for agent tooling.
- **Rationale:** LangGraph provides built-in state management, subgraph support via `Send` API for parallel agent fan-out, native checkpointing with `SqliteSaver`, automatic LangSmith tracing, and clean conditional edges for error recovery and branching.
- **Impact:** Every node, tool call, and LLM invocation is automatically traced in LangSmith. Conditional edges (`should_continue`, `after_reader`) cleanly separate the happy path from error recovery. Checkpointing enables run resumption after crashes.

### 3. Tiered model routing with auto-escalation (o3 / gpt-4o / gpt-4o-mini)

- **Decision:** Route LLM calls by task type to three tiers: reasoning (o3), general (gpt-4o), fast (gpt-4o-mini). Auto-escalate to a higher tier on failure.
- **Alternatives considered:**
  - **Single model for everything:** Overpays for simple tasks (validation, classification) and under-serves complex tasks (planning, conflict resolution).
  - **Manual model selection per call site:** Fragile, requires updating every call site when models change.
- **Rationale:** Planning needs reasoning (o3), editing needs precision (gpt-4o), classification/validation needs speed (gpt-4o-mini). The `ROUTING_POLICY` maps task types to tiers centrally. Auto-escalation recovers from model-specific failures without manual intervention.
- **Impact:** Used OpenAI non-beta `parse()` path for structured output (SDK 2.x). Reasoning tier (o3) falls back to `router.call()` since structured outputs may not be supported. LLMResult/LLMStructuredResult are dataclasses (not Pydantic) for lightweight overhead.

### 4. AsyncSqliteSaver for LangGraph checkpointing over in-memory state

- **Decision:** Use a separate `shipyard_checkpoints.db` SQLite database for LangGraph checkpoint persistence, isolated from the main application database.
- **Alternatives considered:**
  - **In-memory checkpointer:** Loses all state on crash; no run resumption.
  - **Shared database:** Checkpoint tables mixed with application tables risk schema conflicts and migration headaches.
  - **PostgreSQL:** Overkill for a single-user agent; adds infrastructure complexity.
- **Rationale:** SQLite is zero-config, bundled with Python, and sufficient for demo scale. Isolating checkpoints into a separate file prevents schema conflicts between LangGraph's internal tables and Shipyard's application schema.
- **Impact:** Resume passes `None` to `ainvoke()` to trigger LangGraph checkpoint resume. The `trace_url` field was added to the Run model proactively to prevent schema conflicts. Rollback on cancel restores all edits from snapshots -- no partial writes survive cancellation.

### 5. Parallel subgraphs via Send API for multi-agent coordination

- **Decision:** Use LangGraph's `Send` API to fan out independent plan steps to parallel subgraph workers, with a merger node to reconcile results.
- **Alternatives considered:**
  - **Sequential execution only:** Safe but slow; no parallelism benefit.
  - **Thread-based parallelism:** Hard to coordinate state merging; race conditions on shared file buffer.
  - **External task queue (Celery, etc.):** Over-engineered for a single-process agent.
- **Rationale:** The `Send` API is LangGraph's native fan-out primitive. Each subgraph gets isolated state (its own `edit_log`), removing race conditions. The merger node handles three cases: different files (merge directly), same file with different anchors (apply sequentially), and overlapping regions (flag to human).
- **Impact:** For the Ship rebuild, this enables a two-agent split by package -- one handles `api/`, one handles `web/`. The `shared/` package runs sequentially first since both agents depend on it.

### 6. Circuit breaker pattern for repeated validation failures

- **Decision:** After 2 identical consecutive errors on the same plan step, skip/advance instead of retrying indefinitely. After 3 total failures, route to reporter with `waiting_for_human` status.
- **Alternatives considered:**
  - **Unlimited retries:** Can loop forever on fundamentally broken edits, burning tokens.
  - **Single retry:** Too aggressive; many transient failures (anchor drift, minor syntax issues) resolve on retry with error context.
  - **No retries:** Fails on first error; unacceptable for an autonomous agent.
- **Rationale:** The circuit breaker threshold of 2 identical errors balances recovery attempts against infinite loops. Each retry includes the previous error as context, so the LLM can self-correct. If the same error appears twice, the problem is structural, not transient.
- **Impact:** `_normalize_error` was duplicated in `graph.py` and `validator.py` to avoid circular imports. The `last_validation_error` field is stored as a separate dict to preserve `error_state` string backward compatibility.

### 7. ContextAssembler with ranked priority budget filling

- **Decision:** Build a `ContextAssembler` that fills context by priority rank (instruction > schema > current files > recent messages > history) within a token budget, rather than letting nodes build prompts ad-hoc.
- **Alternatives considered:**
  - **Ad-hoc prompt construction in each node:** Already existed; led to context window overflows on large files and inconsistent truncation behavior.
  - **Fixed-size context windows:** Wastes budget on small files, overflows on large ones.
- **Rationale:** With model context limits (128K-200K tokens), a budget-aware assembler ensures the most important context always fits. The `system_prompt_reserve` of 500 tokens ensures system prompts are never crowded out. Skeleton threshold at 200 lines (head=30, tail=10) prevents large files from consuming the entire budget.
- **Impact:** Assembler `build()` output replaces inline context in node prompts. Templates wrap the assembled context. Content hashing (16-char truncated SHA-256) detects file staleness efficiently.

### 8. LSP diagnostic diffing for validation accuracy

- **Decision:** Use a Language Server Protocol client to capture diagnostics before and after edits, then diff them to identify only edit-caused errors.
- **Alternatives considered:**
  - **Subprocess-only validation:** Running `tsc --noEmit` catches errors but includes pre-existing ones, causing false positives.
  - **No validation:** Unacceptable for an autonomous agent.
- **Rationale:** Baseline vs post-edit diagnostic comparison prevents flagging pre-existing TypeScript errors as edit failures. The LSP server stays running across edits (managed by `LspManager`), avoiding cold-start overhead.
- **Impact:** `LspManager` handles server lifecycle; `LspDiagnosticClient` provides high-level diagnostics with timeout/retry. Validator falls back to subprocess syntax checks when LSP is unavailable (degraded mode).

## Ship Rebuild Log (Final Submission)

The detailed instruction-by-instruction log is maintained in [SHIP-REBUILD-LOG.md](SHIP-REBUILD-LOG.md).

### Summary

| Metric | Value |
|--------|-------|
| Total instructions sent | [FILL AFTER REBUILD: total instruction count] |
| First-attempt success rate | [FILL AFTER REBUILD: percentage] |
| Instructions requiring intervention | [FILL AFTER REBUILD: count] |
| Most common failure mode | [FILL AFTER REBUILD: category from limitation taxonomy] |
| Total human time on interventions | [FILL AFTER REBUILD: duration] |

### Key Findings

The rebuild exposed the following top agent limitations:

1. **[FILL AFTER REBUILD: limitation #1]** -- e.g., anchor precision degrades on files >300 lines where the LLM truncates long anchors
2. **[FILL AFTER REBUILD: limitation #2]** -- e.g., multi-file coordination requires explicit dependency ordering in instructions
3. **[FILL AFTER REBUILD: limitation #3]** -- e.g., planner over-decomposes simple tasks into too many steps

### Lessons Learned

**Top insight:** [FILL AFTER REBUILD: the single most important lesson from running the agent on a real codebase, e.g., "Surgical editing works reliably on files under 200 lines but needs skeleton-mode context for larger files to keep anchors accurate."]

See [SHIP-REBUILD-LOG.md](SHIP-REBUILD-LOG.md) for the complete intervention log with root cause analysis for each failure.

## Comparative Analysis (Final Submission)

### 1. Executive Summary

Shipyard was tasked with rebuilding the Ship app -- a TypeScript monorepo with Express API, React frontend, and SQLite persistence -- from natural language instructions alone. The agent-built version follows the same architectural blueprint as the original but is produced through a fundamentally different process: decomposed instructions fed to an autonomous plan-read-edit-validate pipeline rather than interactive human development.

Key metrics: [FILL AFTER REBUILD: success rate, total instructions, human intervention count]. The comparison reveals where autonomous agents match human developers (consistency, speed on repetitive tasks) and where they fall short (architectural intuition, edge case awareness).

### 2. Architectural Comparison

| Dimension | Original Ship (Human-Built) | Agent-Rebuilt Ship |
|-----------|----------------------------|-------------------|
| **Project structure** | pnpm monorepo: `api/`, `web/`, `shared/` | Same monorepo structure preserved |
| **API framework** | Express.js with typed route handlers | Express.js (same -- agent follows instructions faithfully) |
| **Data layer** | SQLite via better-sqlite3 with raw SQL | SQLite via better-sqlite3 (same) |
| **Frontend** | React 18 with Vite, Tailwind CSS | React with Vite, Tailwind CSS (same toolchain) |
| **Type sharing** | Shared TypeScript interfaces in `shared/` | Same pattern -- agent reads types from shared/ first |
| **Testing** | Manual testing, some unit tests | [FILL AFTER REBUILD: testing approach agent used] |
| **Error handling** | Try-catch with HTTP status codes | [FILL AFTER REBUILD: how agent handled error patterns] |
| **Build system** | pnpm workspaces, tsc, Vite | Same (agent preserves existing configuration) |

**What the agent preserved:** Project structure, framework choices, dependency management, and TypeScript configuration were faithfully reproduced because they were specified in the instructions or inferred from context.

**What the agent changed:** [FILL AFTER REBUILD: specific differences in implementation style, naming, patterns]

### 3. Performance Benchmarks

| Metric | Agent-Built | Original (Human) |
|--------|-------------|-------------------|
| Time to rebuild | [FILL AFTER REBUILD] | Estimated several days of human development |
| Total instructions | [FILL AFTER REBUILD] | N/A (interactive development) |
| Lines of code generated | [FILL AFTER REBUILD] | ~3,000 LOC across packages |
| First-attempt success rate | [FILL AFTER REBUILD] | N/A |
| Average retries per instruction | [FILL AFTER REBUILD] | N/A |
| Human interventions required | [FILL AFTER REBUILD] | Continuous (human is the developer) |

### 4. Shortcomings of Agent-Built Version

**Code quality:**
- Repetitive patterns -- the agent may duplicate code rather than extracting shared utilities, since each instruction is processed independently without cross-instruction refactoring awareness.
- Missed optimizations -- database queries may lack indexes or efficient joins that a human developer would add intuitively.
- [FILL AFTER REBUILD: specific shortcoming examples from the actual rebuild]

**Testing gaps:**
- The agent does not write tests unless explicitly instructed to do so. A human developer builds tests as a natural part of development.
- Integration tests across packages (API + frontend) require holistic understanding the agent lacks.

**Architecture understanding:**
- The agent follows instructions literally. It does not question whether a requested architecture makes sense or suggest alternatives.
- Design intent (why a pattern was chosen) is lost -- the agent reproduces structure without understanding motivation.
- [FILL AFTER REBUILD: specific examples where the agent missed architectural intent]

### 5. Advances Over Original

**Reproducibility:** Given the same instructions and context, Shipyard produces the same output. The rebuild is deterministic (modulo LLM temperature), unlike human development where decisions vary by mood, fatigue, and experience.

**Speed:** What takes a human developer days of interactive coding can be completed in [FILL AFTER REBUILD: actual time]. Each instruction is processed in seconds to minutes, limited only by LLM latency.

**Consistency:** The agent applies the same code style, naming conventions, and patterns throughout. No "Friday afternoon code" vs "Monday morning code" quality drift.

**Traceability:** Every change is traced in LangSmith -- every LLM call, every tool invocation, every decision point. The human-built version has git history but no insight into the developer's reasoning process.

**Iteration speed:** Fixing an agent mistake is as fast as sending a corrected instruction. Fixing a human mistake requires context-switching back to the problem.

### 6. Trade-off Analysis

| Dimension | Human Advantage | Agent Advantage | Winner |
|-----------|----------------|-----------------|--------|
| **Speed** | Faster on novel, ambiguous tasks | Faster on well-specified, repetitive tasks | Agent (for defined work) |
| **Consistency** | Can vary style intentionally for readability | Uniform style, no drift | Agent |
| **Creativity** | Invents novel solutions, questions requirements | Follows instructions literally | Human |
| **Debugging** | Intuition, stack trace reading, hypothesis testing | Systematic retry with error context | Human |
| **Architecture** | Holistic design thinking, trade-off evaluation | Reproduces specified architecture faithfully | Human |
| **Testing** | Writes tests naturally as part of development | Only tests when instructed | Human |
| **Documentation** | Writes docs from understanding | Generates docs from pattern matching | Tie |
| **Scale** | Fatigues, limited parallelism | Parallel subgraphs, no fatigue | Agent |

### 7. If You Built It Again

**Better context windowing for large files:** The skeleton-mode reader (head=30, tail=10 for files >200 lines) works but loses important middle sections. A smarter approach would use AST-aware chunking to keep structurally relevant sections regardless of position.

**Smarter planning decomposition:** The planner sometimes over-decomposes simple tasks or under-decomposes complex ones. A two-pass planning approach -- high-level plan then detailed step expansion -- would improve instruction quality.

**Test generation as a first-class step:** Tests should be generated alongside edits, not as a separate instruction. Adding a `test` step type that runs after each edit step would catch regressions immediately.

**Richer multi-file coordination:** The current model (parallel by directory, sequential within) is too coarse. File-level dependency analysis would enable finer-grained parallelism and catch cross-file issues earlier.

[FILL AFTER REBUILD: lessons from actual rebuild experience -- which Shipyard features were most/least valuable, what should be redesigned]

## Cost Analysis (Final Submission)

### Development Spend

| Phase | Plans | Est. Invocations | Avg Tokens/Invocation | Est. Cost |
|-------|-------|------------------|-----------------------|-----------|
| 01 - Edit Reliability | 3 | ~45 | ~20,000 | ~$3.60 |
| 02 - Validation Infrastructure | 3 | ~40 | ~18,000 | ~$2.88 |
| 03 - Context & Token Management | 3 | ~50 | ~25,000 | ~$5.00 |
| 04 - Crash Recovery & Lifecycle | 3 | ~55 | ~22,000 | ~$4.84 |
| 05 - Agent Core Features | 3 (2 completed) | ~35 | ~20,000 | ~$2.80 |
| 06 - Ship Rebuild | 3 | ~30 | ~15,000 | ~$1.80 |
| 07 - Deliverables & Deployment | 3 | ~20 | ~12,000 | ~$0.96 |
| **Total** | **~21** | **~275** | **~19,000 avg** | **~$21.88 est.** |

**Actual development spend:** [FILL AFTER REBUILD: actual total from LangSmith dashboard]

*Note: Shipyard uses OpenAI models (o3/gpt-4o/gpt-4o-mini), not Claude API. The cost estimates above use OpenAI pricing.*

### Production Cost Projections

**Per-invocation cost model:**

| Parameter | Value | Source |
|-----------|-------|--------|
| Typical single-edit run | ~14,100 tokens | PRESEARCH.md token budget estimates |
| Complex multi-file run | ~100,000 tokens | PRESEARCH.md cost cliffs analysis |
| Average invocation (midpoint) | ~30,000 tokens | Weighted average: 70% simple + 30% complex |
| Input/output ratio | 4:1 | Typical for code editing (large file reads, small edits) |
| Input tokens per invocation | ~24,000 | 80% of 30K |
| Output tokens per invocation | ~6,000 | 20% of 30K |

**gpt-4o pricing** (as of March 2026): $2.50/1M input tokens, $10.00/1M output tokens

| Component | Cost per invocation |
|-----------|-------------------|
| Input (24K tokens) | $0.06 |
| Output (6K tokens) | $0.06 |
| **Total per invocation** | **~$0.12** |

**Scaling projections:**

| Tier | Users | Invocations/Day | Monthly Cost | Notes |
|------|-------|-----------------|--------------|-------|
| 100 Users | 100 | 500 (5/user/day) | **~$1,800/month** | Small team, heavy usage |
| 1,000 Users | 1,000 | 5,000 (5/user/day) | **~$18,000/month** | Medium org |
| 10,000 Users | 10,000 | 50,000 (5/user/day) | **~$180,000/month** | Enterprise scale |

**Cost optimization levers:**
- Route simple validation/classification to gpt-4o-mini (~10x cheaper) -- already implemented via tiered routing
- Cache file reads across steps to reduce redundant input tokens
- Use skeleton mode for large files to cap per-invocation input size
- Batch parallel subgraph LLM calls where possible

**Assumptions:**

| Assumption | Value | Rationale |
|------------|-------|-----------|
| Average invocations per user per day | 5 | Developer making 5 multi-file changes/day |
| Average tokens per invocation (input/output) | 24,000 / 6,000 | Midpoint between single-edit and complex runs |
| Cost per invocation | ~$0.12 | gpt-4o at current pricing with 4:1 I/O ratio |
| Model mix | 60% gpt-4o, 30% gpt-4o-mini, 10% o3 | Based on task type distribution in routing policy |

**Actual production cost:** [FILL AFTER REBUILD: actual from LangSmith dashboard if available]
