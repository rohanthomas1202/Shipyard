# Feature Landscape

**Domain:** Autonomous AI coding agent (reliability hardening)
**Researched:** 2026-03-26
**Focus:** Reliability features -- error recovery, validation, context management, edit precision

## Table Stakes

Features users expect from a production-quality coding agent. Missing any of these means the agent feels broken or untrustworthy.

### Edit Precision

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Layered edit matching with fuzzy fallbacks | Every production agent (Aider, RooCode, Codex) implements exact-match-first then progressively fuzzier matching. Without it, edits fail on trivial whitespace differences. | Medium | Shipyard uses anchor-based replacement but lacks fuzzy fallback tiers. Aider's approach: exact -> whitespace-insensitive -> indentation-preserving -> fuzzy. |
| Actionable error feedback on edit failure | When an edit fails to match, the agent must know WHY (which anchor failed, what was found instead) so it can self-correct on retry. Aider does this well -- "provides highly informative feedback when edits fail." | Medium | Shipyard's editor currently gets a pass/fail but limited diagnostic info on match failure. |
| Indentation preservation | Replacement text must adopt the indentation style of the surrounding code. Python and YAML are especially sensitive. RooCode's system captures original whitespace style and applies it. | Medium | Critical for Python files. Must detect tabs vs spaces, indentation level, and apply to replacements. |
| File state freshness checking | Files can change between read and edit. The edit tool must detect stale state and re-read before attempting replacement. Without this, edits silently target wrong content. | Low | Shipyard has `file_buffer` in state but no staleness detection. Add checksums or timestamps. |

### Validation and Error Recovery

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Validate-rollback-retry loop (3+ attempts) | Every serious agent implements this. Generate edit, validate (syntax + semantics), rollback on failure, retry with error context. Shipyard has this architecturally but it needs to be bulletproof. | Medium | Already exists in Shipyard (`should_continue()` with 3 retries). Focus: make error context from failed attempt available to retry. |
| Syntax validation for all edited file types | Agents must catch syntax errors before committing. esbuild for TS/JS, `python -c compile` for Python, json.loads for JSON, etc. | Low | Shipyard has TS/JS (esbuild), JSON, YAML. Add Python syntax checking. |
| LSP diagnostic diffing (baseline comparison) | Only flag NEW errors introduced by the edit, not pre-existing ones. Without baseline diffing, validators produce false positives that waste retry budget. | High | Shipyard recently built this. Ensure it works reliably -- this is a genuine differentiator when it works. |
| Atomic edit transactions | Buffer the full edit, validate before applying. If validation fails, discard entirely without partial application. Never leave files in a half-edited state. | Medium | Shipyard stores snapshots in `edit_history` for rollback. Verify atomicity -- partial writes during crash? |
| Circuit breaker for repeated failures | After N consecutive failures on the same file/step, stop retrying and escalate (report to user, skip step, try alternative approach). Prevents infinite loops that burn tokens. | Low | Shipyard has max 3 retries. Add: if same error repeats 2x, don't retry with same approach -- escalate model tier or skip. |

### Context Management

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Token-budgeted context assembly | Treat context window like memory -- budget allocation across categories (instructions, file content, conversation history, error context). Every production agent does this. | Medium | Shipyard has `ContextAssembler` with ranked priorities but it's NOT WIRED IN. Nodes build prompts directly. This is the #1 gap. |
| Selective file reading (line ranges) | Read only relevant portions of large files. "Read file.py offset=100 limit=20" saves 15K+ tokens per read vs reading entire files. | Low | Shipyard's reader loads full files into `file_buffer`. Add line-range reads for files >200 lines. |
| Context summarization on long runs | As runs get long, summarize earlier steps rather than carrying full history. Prevents context rot (accuracy degrades as token count grows). | Medium | Not implemented. For multi-step plans with 5+ edits, early steps should be summarized. |

### Observability

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Structured trace logging per run | Every step, every LLM call, every tool invocation logged with timing, tokens, success/failure. Users need to understand what happened. | Low | Shipyard has `TraceLogger` writing JSON to `traces/`. Ensure completeness. |
| Real-time progress streaming | Users see what the agent is doing as it happens. Status updates, current step, file being edited. | Low | Already implemented via WebSocket with P0/P1/P2 priority routing. |
| Cost tracking per run | Token usage and estimated cost per run. Users need to know what they're spending. | Low | Not implemented. Track token counts per LLM call and aggregate. |

### Run Lifecycle

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Graceful cancellation | User can stop a run mid-execution without corrupting state. Files rolled back to last good state. | Medium | Partially implemented. Verify: cancel during edit doesn't leave partial writes. |
| Run resumption after crash/disconnect | If the server restarts or WebSocket drops, the run state should be recoverable. LangGraph supports checkpointing for this. | High | Shipyard stores run state in memory (`runs` dict). Server restart loses everything. Need persistent checkpointing. |
| Human-in-the-loop approval gates | User can review edits before they're applied. Critical for trust-building. | Low | Already implemented via `ApprovalManager` with full state machine. |

## Differentiators

Features that set Shipyard apart. Not universally expected, but create competitive advantage when they work.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LSP-powered semantic validation | Most agents use only syntax checks (linters, compilers). Semantic validation via LSP catches type errors, missing imports, undefined references. When combined with baseline diffing, this is genuinely better than competitors. | High | Already built. The differentiator is reliability -- if it works consistently, it's a real edge. Most agents fall back to "run tests" which is slower and less precise. |
| Self-generated regression tests | SWE-bench research shows agents that generate tests before/after editing achieve 2x higher precision. Generate a test that reproduces the expected behavior, then verify the edit passes it. | High | Not built. Would require: generate test -> run test (expect fail) -> apply edit -> run test (expect pass). Significant complexity but proven value. |
| Tiered model routing with auto-escalation | Use fast/cheap models for simple tasks, reasoning models for complex ones. Auto-escalate on failure. Most agents use a single model. | Medium | Already built via `ModelRouter`. Differentiator if routing policy is well-tuned. |
| Multi-file transactional edits | Edit multiple related files as a single transaction -- all succeed or all rollback. Most agents edit files independently, leading to inconsistent states. | High | Not built. Would require: batch edits across files, validate all, commit or rollback all. Important for refactors touching interfaces + implementations. |
| Plan-mode with dependency resolution | Break instructions into typed steps with explicit dependencies, execute in correct order. Most agents use flat task lists. | Medium | Already built via `PlanStep` with `depends_on` and `coordinator` batching. Differentiator if dependency resolution actually works correctly. |
| Edit confidence scoring | Before applying an edit, estimate confidence based on anchor uniqueness, file complexity, change size. Low-confidence edits get extra validation or human review. | Medium | Not built. Could use: anchor match quality score, file size, number of similar anchors. Route low-confidence to supervised mode automatically. |
| Contextual error recovery | On retry, include the specific error from the failed attempt in the prompt. "Your previous edit broke line 47 with TypeError: X. Here's the validator output." Most agents retry blindly. | Low | Partially exists (error_state in AgentState). Ensure the full error context makes it into the retry prompt. |
| AST-aware structural refactoring | Use ast-grep for pattern-based refactoring across entire directories. Rename a function, update an interface, change an import pattern. Deterministic, not LLM-dependent. | Medium | Already built via `refactor` node with ast-grep. Differentiator because it's deterministic -- doesn't depend on LLM precision for mechanical changes. |

## Anti-Features

Features to deliberately NOT build. Each would add complexity without proportional value, or would actively harm reliability.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Multi-agent parallel execution | "Building sophisticated multi-agent systems when a well-crafted prompt would suffice" (Simon Willison). Adds massive complexity for coordination, state merging, conflict resolution. Most multi-agent demos fail in production. | Sequential execution with good planning. Invest in making single-agent reliable before parallelizing. The PDF guidance says: "Get surgical editing working completely before multi-agent." |
| Whole-file rewriting | Rewriting entire files is the #1 cause of broken edits in production agents. Loses context, introduces regressions, wastes tokens. Anchor-based replacement exists specifically to avoid this. | Stick with anchor-based replacement. Never rewrite files >50 lines. For large restructuring, use ast-grep. |
| Autonomous deployment pipelines | "Fully autonomous deployment pipelines exist only in tightly constrained use cases, and error rates aren't yet acceptable for most production systems." | Agent creates branch, commits, opens PR. Human merges and deploys. |
| Plugin/extension system | Custom tool/plugin systems add API surface, versioning burden, and security concerns. For v1, hardcoded pipeline is sufficient. | Add tools directly to the codebase. Refactor to plugin system only if external users demand it. |
| Natural language code search (embeddings/RAG) | Vector search for code sounds good but performs poorly in practice. Code semantics don't embed well. Grep + AST search is faster and more reliable. | Use ripgrep for text search, ast-grep for structural search. Both are deterministic and fast. |
| Streaming edit application | Applying edits as the LLM streams tokens (like Cursor's speculative approach). Extremely complex, requires a separate "apply" model, and any streaming interruption corrupts state. | Wait for complete LLM response, parse, validate, then apply atomically. |
| Automatic conflict resolution | Attempting to auto-merge conflicting edits when multiple steps touch the same file. This is where agents go wrong -- silent merge conflicts produce subtle bugs. | Serialize edits to the same file. Re-read file after each edit to ensure fresh state. |

## Feature Dependencies

```
Token-budgeted context assembly -> Context summarization (summarization needs budget awareness)
Token-budgeted context assembly -> Selective file reading (reading needs budget allocation)

Layered edit matching -> Actionable error feedback (need to know which layer failed)
Actionable error feedback -> Contextual error recovery (error details feed retry prompts)

Atomic edit transactions -> Multi-file transactional edits (single-file atomicity first)
Validate-rollback-retry loop -> Circuit breaker (circuit breaker wraps the retry loop)

File state freshness checking -> Atomic edit transactions (freshness before atomicity)

LSP diagnostic diffing -> Edit confidence scoring (LSP results inform confidence)

Syntax validation -> LSP diagnostic diffing (syntax is the fast path; LSP is the deep path)
```

## MVP Recommendation (Reliability Hardening Phase)

Prioritize in this order -- each builds on the previous:

1. **Wire in ContextAssembler** -- This is the biggest gap. Nodes building prompts directly means no token budgeting, no priority ranking, no context management. Every other improvement is less effective without proper context.

2. **Layered edit matching with fuzzy fallbacks** -- Most edit failures come from trivial whitespace/formatting mismatches. Adding fallback tiers (exact -> normalized whitespace -> fuzzy) dramatically reduces false failures without changing the anchor-based approach.

3. **Actionable error feedback + contextual error recovery** -- When edits DO fail, the agent must know why and use that information on retry. This turns blind retries into informed retries.

4. **File state freshness checking** -- Add checksums to `file_buffer` entries. Before editing, verify the file hasn't changed since it was read. Re-read if stale.

5. **Circuit breaker for repeated failures** -- Prevent the agent from burning all 3 retries on the same doomed approach. If the same error repeats, escalate model tier or skip the step.

6. **Selective file reading (line ranges)** -- For files >200 lines, read only relevant sections. Saves tokens, reduces noise, improves edit precision.

7. **Cost tracking per run** -- Low effort, high visibility. Track tokens per call and surface in the UI.

Defer:
- **Self-generated regression tests**: High value but high complexity. Save for after edit precision is solid.
- **Multi-file transactional edits**: Important for refactors but requires solid single-file atomicity first.
- **Run resumption after crash**: Valuable but requires LangGraph checkpointing migration -- significant infrastructure work.
- **Context summarization**: Only matters for very long runs (5+ steps). Optimize after basic context assembly works.

## Sources

- [Code Surgery: How AI Assistants Make Precise Edits](https://fabianhertwig.com/blog/coding-assistants-file-edits/) -- Comprehensive analysis of edit strategies across Codex, Aider, RooCode, Cursor, OpenHands
- [Context Engineering for Coding Agents](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html) -- Martin Fowler on context management strategies
- [Anti-patterns in Agentic Engineering](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/) -- Simon Willison on what to avoid
- [Where Autonomous Coding Agents Fail](https://medium.com/@vivek.babu/where-autonomous-coding-agents-fail-a-forensic-audit-of-real-world-prs-59d66e33efe9) -- Forensic audit of real-world agent PR failures
- [The Era of Autonomous Coding Agents](https://www.sitepoint.com/autonomous-coding-agents-guide-2026/) -- 2026 agent ecosystem overview
- [SWE-bench and Code Agents as Testers](https://arxiv.org/html/2406.12952v1) -- Research on test generation improving edit precision
- [Hashline File Editing](https://github.com/adenhq/hive/issues/4752) -- Hashline approach improving edit success rates by 8%
- [OpenAI Apply Patch Tool](https://developers.openai.com/api/docs/guides/tools-apply-patch) -- OpenAI's patch-based edit format
- [Error Recovery and Fallback Strategies](https://www.gocodeo.com/post/error-recovery-and-fallback-strategies-in-ai-agent-development) -- Error handling patterns for agents
- [AI Agent Retry Patterns](https://fast.io/resources/ai-agent-retry-patterns/) -- Retry, circuit breaker, and escalation patterns
- [Factory.ai: The Context Window Problem](https://factory.ai/news/context-window-problem) -- Context as finite resource management
- [Codex Sandboxing](https://developers.openai.com/codex/concepts/sandboxing) -- OpenAI Codex sandbox and validation architecture
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide) -- Lifecycle hooks for guardrails and automation
- [Agentic Coding Trends Report 2026](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf) -- Anthropic's analysis of coding agent trends
