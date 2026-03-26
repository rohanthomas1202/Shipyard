# Domain Pitfalls: Autonomous AI Coding Agents

**Domain:** Autonomous coding agent (plan-read-edit-validate-commit pipeline)
**Researched:** 2026-03-26
**Applies to:** Shipyard -- LangGraph agent with anchor-based editing, LSP validation, FastAPI/WebSocket server

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or fundamentally broken agent behavior.

### Pitfall 1: Anchor Mismatch Cascade (Edit Reliability)

**What goes wrong:** The LLM generates an anchor string that does not exactly match the file content. Whitespace differences (tabs vs spaces, trailing whitespace, line endings), encoding issues, or the LLM hallucinating slightly different code all cause `str.replace()` to find zero matches. The edit fails, triggers a retry, and the retry often produces the *same wrong anchor* because the LLM sees the same numbered content and makes the same mistake.

**Why it happens:** LLMs are probabilistic text generators, not byte-level text matchers. When shown numbered file content, they frequently: (a) normalize whitespace in their output, (b) drop trailing spaces, (c) reformat slightly based on their training data conventions, (d) hallucinate minor differences in long code blocks. The longer the anchor, the more likely a mismatch.

**Consequences in Shipyard:** `edit_file()` in `file_ops.py:21-25` rejects zero-match and multi-match anchors. The retry loop (`_retry_count` in `graph.py:16-23`) caps at 3 retries then routes to reporter, meaning the step fails entirely. Three wasted LLM calls with no edit applied.

**Warning signs:**
- High retry rates (>20% of edits need retries)
- Trace logs showing identical anchor text across retry attempts
- Anchors that are very long (>10 lines) or contain lots of whitespace

**Prevention:**
1. **Implement layered fuzzy matching.** After exact match fails, try: (a) strip trailing whitespace from both anchor and file lines, (b) normalize indentation (tabs to spaces), (c) Levenshtein-based fuzzy match with a similarity threshold (>0.95). RooCode and Aider both use this pattern -- it recovers 10-30% of failed edits without false positives.
2. **Return the current file content in the error message** so the retry LLM call sees the actual bytes, not just the numbered display. This breaks the "same mistake twice" loop.
3. **Prefer shorter anchors.** Prompt engineering should instruct the LLM to use the minimum unique anchor (3-5 lines of distinctive context), not copy half the file.
4. **Normalize the numbered content display** to use consistent whitespace before showing it to the LLM, so what the LLM sees matches what `str.replace()` will search.

**Phase mapping:** Phase 1 -- this is the single highest-impact reliability improvement.

---

### Pitfall 2: State Bloat and Context Rot

**What goes wrong:** The `edit_history` list in `AgentState` accumulates every edit (including snapshots of full file content in the `snapshot` field) across all steps. The `file_buffer` holds full content of every read file. For a 20-step plan editing files >200 lines, state can balloon to hundreds of KB of text. LangGraph serializes the full state at every node boundary. Worse, if `messages` uses the `add_messages` reducer, conversation history grows unboundedly across the graph execution.

**Why it happens:** LangGraph's state model is "accumulate everything by default." The `Annotated[list, add_messages]` reducer on `messages` appends, never trims. The `edit_history` list grows linearly with edits. Snapshots store the *entire file content* before each edit for rollback -- necessary but expensive.

**Consequences in Shipyard:** (a) LangGraph checkpointing (if enabled) serializes increasingly large state blobs. (b) If state is ever passed to an LLM (e.g., for context), token costs explode. (c) Memory usage grows monotonically during a run -- no eviction. (d) The `runs` dict in `server/main.py:20` holds this state in memory indefinitely with no cleanup.

**Warning signs:**
- Runs slow down noticeably after step 8-10
- Memory usage climbs linearly during long runs
- LLM calls get slower (if state is included in context)

**Prevention:**
1. **Separate rollback snapshots from display state.** Store snapshots in SQLite (keyed by edit_id), not in the graph state. The state should only hold a reference.
2. **Cap edit_history to the last N entries** (e.g., 5) in the state reducer. Older entries go to the database.
3. **Evict files from file_buffer** once their steps are complete. Only keep files relevant to the current and next step.
4. **Do not pass full state to LLM calls.** The editor and validator should only see the relevant file content, not the accumulated history.
5. **Add TTL-based eviction** to the `runs` dict to prevent unbounded memory growth.

**Phase mapping:** Phase 1 (snapshot externalization) and Phase 2 (state trimming, memory management).

---

### Pitfall 3: Validation Theater (False Confidence)

**What goes wrong:** The validator reports "pass" but the edit actually broke something. Two failure modes: (a) **False negatives** -- the validator does not check for the class of error introduced (e.g., `esbuild` catches syntax errors but not type errors, runtime errors, or logic errors). (b) **False positives** -- the validator flags pre-existing errors as edit failures, causing unnecessary rollbacks of correct edits.

**Why it happens:** Shipyard's validator has a narrow check surface: JSON parse, esbuild compile, node --check, yaml parse. These catch syntax-level issues only. The LSP diagnostic diffing (recent addition) helps with type errors for TypeScript but: (a) only works when the LSP server is running, (b) depends on `tsconfig.json` being correct, (c) is not wired for Python, Rust, Go, etc. Meanwhile, esbuild does *bundling* -- it can produce false positives from missing dependencies that have nothing to do with the edit.

**Consequences in Shipyard:** Agent appears to work (all validations pass) but produces code that fails at runtime. During the Ship app rebuild, this would surface as "agent said it succeeded, but the app crashes." Alternatively, good edits get rolled back because of pre-existing lint errors, wasting all three retry attempts.

**Warning signs:**
- Agent reports "success" but manual testing reveals broken code
- High rollback rate on files that already had errors before the edit
- Validator only triggers on syntax errors, never on type or logic errors

**Prevention:**
1. **Layer validation checks** in order of speed and specificity: syntax check (fast, catches gross errors) -> type check via LSP (medium, catches type errors) -> targeted test execution (slow, catches logic errors). Each layer is optional but the agent should know which layers ran.
2. **Always use diagnostic diffing**, not absolute error counts. The LSP baseline comparison pattern already exists in Shipyard -- make sure it is the *only* validation path for TS/TSX, not a fallback.
3. **Run relevant tests when available.** If the plan step specifies affected test files, run them as part of validation. This catches logic errors that static analysis misses.
4. **Report validation coverage** in the edit result: "validated: syntax=true, types=true, tests=false" so the human/reporter knows what was actually checked.
5. **Handle LSP server crashes gracefully.** If the TypeScript server dies mid-run, fall back to esbuild but log a warning. Never silently skip validation.

**Phase mapping:** Phase 1 (fix false positives via consistent diffing), Phase 2 (layer in test execution).

---

### Pitfall 4: Retry Loop Without Learning

**What goes wrong:** When an edit fails validation and gets rolled back, the agent retries by going back to the reader node, re-reading the same file (now restored to its pre-edit state), and asking the LLM to try again. But the retry prompt contains no information about *why the previous attempt failed*. The LLM makes the same mistake or a similar one. Three retries burn, then the step fails.

**Why it happens:** The `should_continue` function in `graph.py:26-38` routes errors back to `reader`, which re-reads the file. But the error message from the validator is stored in `error_state`, which gets passed through the state but is *not included* in the editor's prompt. The editor prompt template (`EDITOR_USER`) takes `file_path`, `numbered_content`, `edit_instruction`, and `context_section` -- there is no field for "previous attempt feedback."

**Consequences in Shipyard:** Wasted LLM calls (3x cost for the same failed edit), frustrated users watching the same error repeat, and ultimately a failed step that might have succeeded if the LLM knew what went wrong.

**Warning signs:**
- Same or very similar error messages across all 3 retry attempts
- Retry success rate below 30%
- Error messages that describe the exact fix needed but the LLM does not receive them

**Prevention:**
1. **Feed the error back to the editor prompt.** Add a `previous_error` field to the editor prompt template. On retry, populate it with the validator's error message and the failed anchor/replacement pair.
2. **Escalate model tier on retry.** If gpt-4o-mini fails twice, escalate to gpt-4o. If gpt-4o fails, escalate to o3. The router's tiered model system already supports this -- add retry-count-based escalation.
3. **Vary the approach.** On retry 2, instruct the LLM to use a different anchor (shorter/longer) or a different edit strategy. Break the deterministic loop.
4. **Add a "reflection" step** between validator failure and editor retry that asks a cheap model "why did this edit fail and what should be different next time?"

**Phase mapping:** Phase 1 -- this is the second highest-impact reliability improvement after fuzzy matching.

---

### Pitfall 5: Synchronous Operations Blocking the Event Loop

**What goes wrong:** The asyncio event loop gets blocked by synchronous subprocess calls, causing WebSocket heartbeats to stop, connections to drop, and the frontend to show the run as "disconnected" even though the agent is still working. When the blocking call finishes, the WebSocket is dead, events are lost, and the UI is stale.

**Why it happens:** `executor_node` calls `run_command()` (sync `subprocess.run` with `shell=True`) instead of `run_command_async()`. The validator's `_syntax_check` uses sync `subprocess.run` (though it is wrapped in `asyncio.to_thread` now). Any sync I/O in a LangGraph node blocks the entire uvicorn event loop because LangGraph runs nodes as coroutines on the main event loop.

**Consequences in Shipyard:** (a) WebSocket connections silently die during long `npm install` or test suite runs. (b) Heartbeats stop, causing the frontend to enter reconnection mode. (c) The reconnection replay may race with new events. (d) `shell=True` in `run_command` is also a security risk (shell injection from LLM-generated commands).

**Warning signs:**
- Frontend shows "disconnected" during executor steps
- Heartbeat gaps > 30 seconds in WebSocket logs
- Commands > 5 seconds cause observable UI lag

**Prevention:**
1. **Convert all subprocess calls to async.** Use `asyncio.create_subprocess_exec` (not `shell=True`) everywhere. The `run_command_async` function already exists -- use it.
2. **Set `--ws-ping-interval` on uvicorn** (e.g., 20 seconds) so stale connections are detected quickly.
3. **Cancel background tasks on WebSocket disconnect.** The current code does not cancel the graph task when the client disconnects, leading to orphaned runs sending to dead connections.
4. **Implement a command allowlist** for the executor node. Do not pass arbitrary LLM-generated strings to `shell=True`.

**Phase mapping:** Phase 1 (async conversion), Phase 2 (cancellation, allowlist).

---

## Moderate Pitfalls

### Pitfall 6: Planner Generates Unbounded or Mistyped Plans

**What goes wrong:** The planner LLM generates too many steps (20+ for a simple change), steps with wrong `kind` values (causing misrouting in `classify_step`), or steps with vague `acceptance_criteria` that the editor cannot act on. The legacy string-based step format is still supported, causing dual code paths that behave differently.

**Prevention:**
1. **Validate plan steps against the PlanStep schema** immediately after generation. Reject and re-plan if validation fails.
2. **Cap plan length** (e.g., max 15 steps). If the LLM generates more, it is likely over-decomposing.
3. **Remove legacy string step support.** The dual code paths in `graph.py:70-78`, `reader.py:20-33`, `executor.py:15-21` add complexity and behave differently. Force typed steps only.
4. **Include examples in the planner prompt** showing good decomposition for common task types.

**Phase mapping:** Phase 1 (schema validation, cap), Phase 2 (remove legacy format).

---

### Pitfall 7: File Buffer Stale Reads

**What goes wrong:** The `file_buffer` stores file content at the time the reader node ran. If the executor node modifies files (e.g., `npm install` updates `package-lock.json`, or a build step generates files), subsequent steps see stale content in the buffer. Edits based on stale content fail with anchor mismatches.

**Prevention:**
1. **Invalidate file_buffer entries after executor steps.** The `invalidated_files` state field exists but is only checked for ast-grep cache clearing, not for buffer invalidation.
2. **Re-read files at the start of each edit step**, not just at the reader node. The reader-then-edit flow should guarantee fresh content.
3. **After executor steps that modify files** (install, build, codegen), clear the entire file_buffer and force re-reads.

**Phase mapping:** Phase 1 -- straightforward fix with high impact.

---

### Pitfall 8: LLM Output Format Brittleness

**What goes wrong:** The editor expects the LLM to return a JSON object with `anchor` and `replacement` keys. The current parsing strips markdown fences but fails on: nested fences, JSON preceded by commentary text, multiple JSON objects, or the LLM wrapping the response in an array. Any parse failure aborts the edit with no retry -- `error_state` is set but the retry loop counts it as an error that exhausts retries.

**Prevention:**
1. **Use structured output / function calling** instead of free-text JSON parsing. OpenAI's function calling API guarantees valid JSON matching a schema. This eliminates the entire parse failure category.
2. **As a fallback**, implement regex-based JSON extraction: find the first `{...}` in the response that parses as valid JSON with the required keys.
3. **Do not count parse failures as edit failures** for retry purposes. A parse failure should re-prompt with "please return valid JSON" without decrementing retry budget.

**Phase mapping:** Phase 1 (function calling migration is high-value, low-risk).

---

### Pitfall 9: No Run Cancellation or Timeout

**What goes wrong:** A run enters a bad state (stuck waiting for approval that never comes, LLM taking forever to respond, infinite retry on a fundamentally impossible edit) and there is no way to stop it. The WebSocket `stop` action dispatches to `_stop_callback` which is never set. The only option is server restart, which loses all in-flight state.

**Prevention:**
1. **Wire up the stop callback** to cancel the asyncio task running the graph.
2. **Add a global timeout** per run (e.g., 10 minutes). If the run exceeds this, force-terminate and report partial results.
3. **Add per-step timeout** (e.g., 2 minutes per LLM call). The OpenAI SDK supports timeout parameters.
4. **Persist run state to SQLite at node boundaries** using LangGraph's checkpointer, so restarts do not lose progress.

**Phase mapping:** Phase 1 (stop callback, timeouts), Phase 2 (checkpointing).

---

### Pitfall 10: WebSocket Reconnection Race Condition

**What goes wrong:** During reconnection, the server replays events from the store while new events may be generated by the running agent. The client can receive events out of order or miss events that were generated between the snapshot and the end of replay. There is no lock preventing concurrent sends during replay.

**Prevention:**
1. **Buffer new events during replay.** When a reconnection is in progress, queue any new events for that run_id. After replay completes, flush the buffer.
2. **Use sequence numbers strictly.** The client should discard any event with `seq <= last_received_seq` and request re-replay if gaps are detected.
3. **Send a "replay_complete" sentinel** so the client knows when live events resume.

**Phase mapping:** Phase 2 (the current implementation mostly works, but edge cases surface under load).

---

## Minor Pitfalls

### Pitfall 11: Module-Level Singleton TraceLogger

**What goes wrong:** Every node file creates `tracer = TraceLogger()` at module level. With concurrent runs, trace entries from different runs interleave. The `run_id` field gets overwritten, and `tracer.save()` writes a file mixing data from multiple runs.

**Prevention:** Pass a per-run tracer via `config["configurable"]` instead of module-level singletons. This is already a known concern in CONCERNS.md.

**Phase mapping:** Phase 2.

---

### Pitfall 12: Edit Produces Valid Syntax but Wrong Semantics

**What goes wrong:** The LLM generates an edit that is syntactically valid, passes type checking, but does the wrong thing (e.g., reverses a condition, deletes important logic, adds dead code). No amount of static validation catches this.

**Prevention:**
1. **Include acceptance criteria in the validation step.** The planner generates `acceptance_criteria` per step -- the validator could pass these to a cheap LLM to verify the edit matches intent.
2. **Run tests when available.** This is the only reliable way to catch semantic errors.
3. **Log diffs to LangSmith** so human reviewers can audit what was changed during the run.

**Phase mapping:** Phase 3 (requires test execution infrastructure).

---

### Pitfall 13: Large File Listing Wastes Planner Context

**What goes wrong:** `list_files(working_dir)` runs `glob.glob("**/*", recursive=True)` with no gitignore filtering. For a project with `node_modules/`, this returns thousands of files, consuming LLM tokens and degrading planner quality by burying signal in noise.

**Prevention:**
1. **Use `git ls-files`** instead of glob. This automatically respects `.gitignore`.
2. **Limit depth and count** (e.g., max 200 files, max 3 levels deep for initial listing).
3. **Filter by relevance** to the instruction (e.g., only show `.ts`/`.tsx` files for a "fix the React component" task).

**Phase mapping:** Phase 1 -- simple fix, meaningful improvement.

---

### Pitfall 14: Approval Manager In-Memory State Loss

**What goes wrong:** `ApprovalManager._batch_registry` is in-memory only. Server restart loses all pending approval state. Batch operations for refactor edits fail silently.

**Prevention:** Query batch membership from the `edits` table (which already has a `batch_id` column) instead of the in-memory registry.

**Phase mapping:** Phase 2.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation | Priority |
|-------------|---------------|------------|----------|
| Edit reliability hardening | Anchor mismatch cascade (#1) | Fuzzy matching, shorter anchors, error feedback | P0 |
| Edit reliability hardening | Retry without learning (#4) | Feed errors back to editor prompt | P0 |
| Edit reliability hardening | LLM output format brittleness (#8) | Function calling / structured output | P0 |
| Validation hardening | False confidence (#3) | Layered validation, diagnostic diffing everywhere | P0 |
| Validation hardening | Stale file buffer (#7) | Invalidate buffer after executor steps | P1 |
| Infrastructure stability | Event loop blocking (#5) | Async subprocess, ws-ping-interval | P0 |
| Infrastructure stability | No cancellation/timeout (#9) | Wire stop callback, add timeouts | P1 |
| Infrastructure stability | WebSocket reconnection race (#10) | Buffer events during replay | P2 |
| State management | State bloat (#2) | Externalize snapshots, cap history | P1 |
| Planner quality | Unbounded plans (#6) | Schema validation, cap length | P1 |
| Planner quality | Large file listing (#13) | Use git ls-files | P1 |
| Observability | Singleton tracer (#11) | Per-run tracer via config | P2 |
| Semantic correctness | Wrong semantics (#12) | Test execution, acceptance criteria | P2 |
| Approval flow | In-memory state loss (#14) | Persist to SQLite | P2 |

---

## Sources

- [Code Surgery: How AI Assistants Make Precise Edits to Your Files](https://fabianhertwig.com/blog/coding-assistants-file-edits/) -- comprehensive survey of edit format reliability across major coding assistants
- [The 80% Problem in Agentic Coding](https://addyo.substack.com/p/the-80-problem-in-agentic-coding) -- why agents confidently produce wrong results on complex tasks
- [Where Autonomous Coding Agents Fail: A Forensic Audit of Real-World PRs](https://medium.com/@vivek.babu/where-autonomous-coding-agents-fail-a-forensic-audit-of-real-world-prs-59d66e33efe9) -- failure patterns in production agent PRs
- [Are Bugs and Incidents Inevitable with AI Coding Agents?](https://stackoverflow.blog/2026/01/28/are-bugs-and-incidents-inevitable-with-ai-coding-agents/) -- Stack Overflow analysis of AI-generated code quality
- [Optimizing LangGraph Cycles: Stopping the Infinite Loop](https://rajatpandit.com/optimizing-langgraph-cycles/) -- LangGraph-specific retry and loop management
- [The Memory Leak in the Loop: Custom State Reducers in LangGraph](https://azguards.com/ai-engineering/the-memory-leak-in-the-loop-optimizing-custom-state-reducers-in-langgraph/) -- state bloat from `add_messages` reducer
- [Fix File Editing Tool Reliability - Cline Issue #4384](https://github.com/cline/cline/issues/4384) -- community discussion of search/replace failure modes and fuzzy matching
- [Diff Format Explained: Search-Replace Blocks](https://www.morphllm.com/edit-formats/diff-format-explained) -- edit format comparison with reliability data
- [GPT Code Editing Benchmarks - Aider](https://aider.chat/docs/benchmarks.html) -- quantitative data on edit format success rates
- [Unified Diffs Make GPT-4 Turbo 3X Less Lazy](https://aider.chat/docs/unified-diffs.html) -- Aider's lessons on edit format impact on LLM behavior
- [Building Effective AI Coding Agents for the Terminal](https://arxiv.org/abs/2603.05344) -- arXiv paper on context engineering and safety controls
- [Evaluating the Impact of LSP-based Code Intelligence on Coding Agents](https://www.nuanced.dev/blog/evaluating-lsp) -- LSP integration benefits and pitfalls for agents
- [FastAPI WebSocket Disconnection Discussion #9031](https://github.com/fastapi/fastapi/discussions/9031) -- WebSocket disconnect propagation issues with uvicorn

---

*Concerns audit: 2026-03-26*
