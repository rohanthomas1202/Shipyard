# Architecture Patterns for Reliable Autonomous Coding Agents

**Domain:** Autonomous AI coding agent (LangGraph-based, anchor-based editing)
**Researched:** 2026-03-26
**Focus:** Error recovery, state management, edit precision, context window management

## Recommended Architecture

Shipyard already has a solid foundation: an 11-node LangGraph StateGraph with tiered LLM routing, anchor-based editing, LSP validation, and priority event streaming. The hardening work is not about restructuring -- it is about adding reliability layers to each existing component.

The architecture should evolve from "happy-path pipeline" to "resilient pipeline with degradation paths" by adding five reliability layers:

```
+------------------------------------------------------------------+
|                    RELIABILITY LAYERS                              |
|                                                                    |
|  1. Checkpointed State (crash recovery, run resumption)           |
|  2. Edit Integrity (stale detection, fuzzy matching, rollback)    |
|  3. Loop Guards (progress detection, stuck-agent termination)     |
|  4. Context Budget (window management, compaction, eviction)      |
|  5. Validation Cascade (LSP -> syntax -> independent verify)      |
+------------------------------------------------------------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With | Hardening Needed |
|-----------|---------------|-------------------|------------------|
| **Graph Runner** (graph.py) | Orchestrate node execution, manage state transitions | All nodes, checkpointer, event bus | Checkpointing, crash recovery, timeout enforcement |
| **Planner** (nodes/planner.py) | Decompose instructions into typed PlanSteps | Router (LLM), file_ops (listing) | Output validation, plan sanity checks, step count limits |
| **Reader** (nodes/reader.py) | Load files into file_buffer | file_ops, ContextAssembler | Content hashing for stale detection, budget-aware truncation |
| **Editor** (nodes/editor.py) | Apply LLM-generated edits via anchor/replacement | Router (LLM), file_ops, ast_ops, ApprovalManager | Fuzzy anchor matching, edit pre-validation, snapshot guarantees |
| **Validator** (nodes/validator.py) | Check edits for correctness, rollback on failure | LSP manager, subprocess checks | Error classification (retriable vs fatal), independent verification |
| **Loop Guard** (new) | Detect stuck agents, enforce progress | Graph runner, state | Repeated-action detection, step budgets, progress signals |
| **Context Manager** (context.py) | Fill LLM context windows within budget | All LLM-calling nodes | Wire into nodes (currently unused), window utilization tracking |
| **Checkpointer** (new integration) | Persist state at each super-step | Graph runner, SQLite | Enable run resumption after crashes |

### Data Flow (Hardened)

**Current flow** (happy path only):
```
receive -> planner -> coordinator -> classify -> reader -> editor -> validator -> advance -> ...
```

**Hardened flow** (with reliability layers):
```
receive -> planner -> [plan validator] -> coordinator -> classify
  -> reader [with content hashing + budget tracking]
  -> editor [with stale detection + fuzzy matching + pre-validation]
  -> validator [LSP -> syntax -> independent verify, with error classification]
  -> [loop guard check: progress? retry budget?]
  -> advance or [error handler -> retry/skip/abort]
```

At each node boundary:
1. State is checkpointed (LangGraph super-step)
2. Loop guard evaluates progress
3. Context budget is recalculated
4. Error state is classified (retriable/fatal/degraded)

## Patterns to Follow

### Pattern 1: LangGraph Checkpointing for Crash Recovery

**What:** Use `langgraph-checkpoint-sqlite` (or `AsyncSqliteSaver`) to persist graph state at every super-step. On crash or WebSocket drop, resume from last checkpoint.

**Why:** Shipyard currently stores run state in an in-memory `runs` dict. A uvicorn crash loses all in-flight runs with no recovery path. LangGraph's built-in checkpointer solves this with zero architectural change.

**When:** Every graph invocation. Compile the graph with a checkpointer.

**Implementation sketch:**
```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def build_graph_with_checkpointer(db_path: str):
    checkpointer = AsyncSqliteSaver.from_conn_string(db_path)
    graph = StateGraph(AgentState)
    _build_graph_nodes(graph)
    return graph.compile(checkpointer=checkpointer)
```

Each run gets a unique `thread_id` in the config. On crash, re-invoke with the same thread_id to resume from last checkpoint.

**Confidence:** HIGH -- this is LangGraph's documented, primary persistence mechanism.

### Pattern 2: Content Hashing for Stale Edit Detection

**What:** Hash file contents when read into `file_buffer`. Before applying an edit, verify the hash still matches the file on disk. Reject edits against stale content.

**Why:** The current editor reads content from `file_buffer` but has no mechanism to detect if the file changed between read and edit (e.g., by the executor node running a command that modifies files, or by external tools). This is the exact problem hash-anchored edits solve in oh-my-pi, which saw "tenfold improvement in success rates" on some models.

**When:** Every edit operation.

**Implementation sketch:**
```python
import hashlib

def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

# In reader_node: store hash alongside content
file_buffer[path] = content
file_hashes[path] = hash_content(content)

# In editor_node: verify before applying
current_on_disk = _read_raw(file_path)
if hash_content(current_on_disk) != state["file_hashes"].get(file_path):
    # File changed since read -- re-read and retry, don't apply stale edit
    return {"error_state": f"Stale file detected: {file_path}. Re-reading.", ...}
```

**Confidence:** HIGH -- proven pattern in oh-my-pi and similar systems.

### Pattern 3: Layered Anchor Matching (Fuzzy Fallback)

**What:** When the exact anchor string is not found, fall through a matching cascade: exact -> whitespace-normalized -> indentation-preserving -> fuzzy (difflib). This matches the proven pattern from Aider and RooCode.

**Why:** The current `edit_file()` does strict `content.count(anchor)` and fails immediately if count != 1. LLMs frequently produce anchors with minor whitespace differences, especially across long files. Aider's success is partly attributed to its layered matching strategy.

**When:** When exact anchor matching fails in `edit_file()`.

**Implementation sketch:**
```python
def edit_file(path: str, anchor: str, replacement: str) -> dict:
    content = _read(path)

    # Layer 1: Exact match
    if content.count(anchor) == 1:
        return _apply(content, anchor, replacement, path)

    # Layer 2: Whitespace-normalized match
    normalized_anchor = _normalize_ws(anchor)
    normalized_content = _normalize_ws(content)
    match = _find_normalized_match(content, normalized_content, normalized_anchor)
    if match:
        return _apply(content, match, replacement, path)

    # Layer 3: Fuzzy match (difflib, threshold 0.85)
    match = _fuzzy_find(content, anchor, threshold=0.85)
    if match:
        return _apply(content, match, replacement, path)

    return {"error": f"Anchor not found in {path} (tried exact, normalized, fuzzy)"}
```

**Confidence:** MEDIUM -- pattern is well-proven in Aider/RooCode, but threshold tuning needs empirical testing on Shipyard's specific edit patterns.

### Pattern 4: Loop Guard with Progress Detection

**What:** Track the last N tool calls / node executions. Detect repeating patterns (same file edited 3+ times with errors, same anchor failing repeatedly). Inject steering or abort.

**Why:** The current retry logic (`_retry_count >= 3 -> reporter`) counts consecutive errors but does not detect semantic loops (e.g., the editor keeps trying the same bad anchor). SWE-agent research shows "a prominent failure mode occurs when models repeatedly edit the same code snippet."

**When:** After every node execution, checked in `should_continue()`.

**Implementation sketch:**
```python
def _detect_loop(state: dict) -> bool:
    """Check last 6 edit_history entries for repeating patterns."""
    history = state.get("edit_history", [])[-6:]
    if len(history) < 4:
        return False

    # Check for same-file repeated failures
    recent_errors = [h for h in history if h.get("error")]
    if len(recent_errors) >= 3:
        files = [h.get("file") for h in recent_errors]
        if len(set(files)) == 1:
            return True  # Same file failing repeatedly

    # Check for anchor repetition
    anchors = [h.get("old", "")[:100] for h in history[-4:]]
    if len(set(anchors)) <= 2 and len(anchors) >= 3:
        return True  # Cycling between same anchors

    return False

def should_continue(state: dict) -> str:
    if _detect_loop(state):
        return "reporter"  # Bail out, don't waste tokens
    # ... existing logic
```

**Confidence:** HIGH -- pattern documented in strongdm/attractor coding-agent-loop-spec, validated in production.

### Pattern 5: Context Budget Enforcement

**What:** Wire the existing `ContextAssembler` into all LLM-calling nodes. Track context utilization. Keep it in the 40-60% range for complex tasks to leave room for LLM reasoning.

**Why:** `ContextAssembler` exists in `agent/context.py` but is completely unused -- nodes build prompts directly with unbounded string concatenation. This means large files silently exceed context windows, causing truncation or degraded output quality. The "lost-in-the-middle" phenomenon means information buried in large contexts is effectively invisible to the model.

**When:** Every LLM call in planner, editor, and reader nodes.

**Implementation sketch:**
```python
# In editor_node, replace direct prompt building:
assembler = ContextAssembler(max_tokens=router.resolve_model(task_type).context_window)
assembler.add_task(step_text)
assembler.add_file(file_path, numbered, priority="working")
if context.get("spec"):
    assembler.add_error(context["spec"])  # or add as reference
user_prompt = assembler.build()
```

**Confidence:** HIGH -- the component exists and is well-designed. This is pure wiring work.

### Pattern 6: Error Classification (Retriable vs Fatal vs Degraded)

**What:** Replace the current string-based `error_state` with a typed error object that classifies failures. Different error types get different recovery paths.

**Why:** The current system treats all errors identically: set `error_state` string, retry up to 3 times, then report. But "anchor not found" (retriable with re-read) is fundamentally different from "file not found" (fatal) or "LSP unavailable" (degraded mode). Conflating these wastes retry budget on unrecoverable errors and fails to use appropriate recovery for each type.

**When:** Every error path in every node.

**Implementation sketch:**
```python
from enum import Enum
from typing import TypedDict, Optional

class ErrorSeverity(Enum):
    RETRIABLE = "retriable"    # Re-read file and retry edit
    DEGRADED = "degraded"      # Continue with reduced capability
    FATAL = "fatal"            # Skip step, move to next
    ABORT = "abort"            # Stop entire run

class ErrorInfo(TypedDict):
    severity: str  # ErrorSeverity value
    message: str
    node: str
    step: int
    retry_hint: Optional[str]  # What to do differently on retry

# In should_continue():
error = state.get("error_info")  # Typed, not just a string
if error:
    if error["severity"] == "fatal":
        return "advance"  # Skip this step
    if error["severity"] == "abort":
        return "reporter"
    if error["severity"] == "retriable" and _retry_count(state) < 3:
        return "reader"  # Re-read and retry
    return "reporter"
```

**Confidence:** MEDIUM -- the pattern is sound and well-established, but requires touching every node's error paths. Needs careful migration.

### Pattern 7: Independent Verification (Two-Context Validation)

**What:** After the editor produces an edit and the primary validator (LSP/syntax) passes it, optionally send the before/after diff to a separate LLM call (fast tier) to verify the edit matches the intent. This is the "generator-evaluator" pattern.

**Why:** The current validator catches syntax errors but not semantic errors (edit compiles but does the wrong thing). The planner's `acceptance_criteria` field exists but is never checked post-edit. This is the gap between "code compiles" and "code is correct."

**When:** For complex edits (complexity == "complex") or after retries.

**Implementation sketch:**
```python
async def _semantic_verify(router, file_path, old_content, new_content, acceptance_criteria):
    diff = _generate_diff(old_content, new_content)
    prompt = f"Does this diff satisfy these criteria?\n{acceptance_criteria}\n\nDiff:\n{diff}\n\nAnswer YES or NO with brief explanation."
    result = await router.call("validate", VERIFY_SYSTEM, prompt)
    return "YES" in result.upper()
```

**Confidence:** MEDIUM -- the pattern is proven (Anthropic's compound AI architecture, Hermes agent's independent verification), but adds latency and cost. Use selectively.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Unbounded Retry Without Re-Reading

**What:** Retrying an edit without re-reading the file from disk first.

**Why bad:** After a rollback, the file_buffer may still contain the pre-rollback content. The editor will generate the same bad anchor again. The current `should_continue -> reader` path does handle this correctly for the retry case, but if rollback changes the file state, the buffer must be explicitly invalidated.

**Instead:** Always re-read from disk on retry. Invalidate file_buffer entries for rolled-back files.

### Anti-Pattern 2: Silent Context Overflow

**What:** Building prompts by concatenating strings without checking total token count.

**Why bad:** When a 500-line file is loaded into context alongside a detailed plan and step instructions, the prompt may exceed the model's effective attention window. The model still produces output, but quality degrades silently. No error is raised.

**Instead:** Use ContextAssembler with explicit budget. Truncate or summarize large files. Track utilization.

### Anti-Pattern 3: Single Error Type for All Failures

**What:** Using `error_state: Optional[str]` for every failure mode.

**Why bad:** "Anchor not found" and "file permissions denied" both become strings in the same field. The retry logic cannot distinguish between them. Retry budget is wasted on unrecoverable errors.

**Instead:** Use typed error objects with severity classification.

### Anti-Pattern 4: Editing Without Snapshot Guarantee

**What:** The legacy `edit_file()` path creates a snapshot, but if the function throws between read and write, the snapshot is lost.

**Why bad:** Rollback becomes impossible. The validator calls `_rollback(last_edit)` which reads `snapshot` from `edit_history`, but if the editor crashed mid-write, the snapshot may not exist.

**Instead:** Write snapshot to a temporary file (or checkpointer state) before any write operation. Use atomic write patterns (write to temp, rename).

### Anti-Pattern 5: Mutable State in Node Return

**What:** Building new state dicts with spread operators `{**file_buffer, file_path: updated_content}` -- this works but creates increasingly large state objects as the run progresses.

**Why bad:** Each edit appends to `edit_history` and copies `file_buffer`. For long runs (20+ edits), state grows unbounded. LangGraph checkpointer persists this at every step.

**Instead:** Consider evicting completed steps from edit_history (keep only last N for rollback). Use a separate file cache that is not persisted in state.

## Scalability Considerations

| Concern | Current (10 files) | At 50 files | At 200+ lines/file |
|---------|-------------------|-------------|---------------------|
| State size | Small, no issue | file_buffer grows, checkpoints slow | Context overflow in editor prompts |
| Edit precision | Anchors work | Anchor uniqueness degrades | Must use longer anchors or line-range hints |
| Validation time | Fast (LSP + esbuild) | LSP startup cost amortized | Individual file validation still fast |
| Context window | Under budget | Files compete for context | Truncation or summarization required |
| Retry budget | 3 retries adequate | 3 per step * 50 steps = 150 max LLM calls | Cost concern at scale |

## Build Order (Dependencies Between Hardening Components)

The hardening work should proceed in this order based on dependencies and impact:

### Phase 1: Foundation (No Dependencies)
1. **Checkpointing** -- Add `AsyncSqliteSaver` to graph compilation. This is a one-line change to `build_graph()` plus config wiring. Everything else benefits from crash recovery.
2. **Content hashing** -- Add `file_hashes` field to `AgentState`, populate in reader, check in editor. Independent of other changes.
3. **Wire ContextAssembler** -- Replace direct prompt building in editor and planner nodes. The component exists; this is integration work.

### Phase 2: Edit Reliability (Depends on Phase 1)
4. **Fuzzy anchor matching** -- Extend `edit_file()` with layered matching cascade. Benefits from content hashing (knows when to re-read vs fuzzy match).
5. **Error classification** -- Replace `error_state: str` with typed `ErrorInfo`. Update `should_continue()` routing. All retry/rollback logic improves.
6. **Stale file detection** -- Uses content hashes from Phase 1. Editor rejects edits against changed files.

### Phase 3: Loop Prevention (Depends on Phase 2)
7. **Loop guard** -- Requires error classification to distinguish "stuck" from "retriable." Analyzes edit_history patterns.
8. **Step budget enforcement** -- Limit total LLM calls per run. Requires error classification to know when to skip vs abort.

### Phase 4: Advanced Validation (Depends on Phases 1-3)
9. **Independent verification** -- Semantic check using acceptance_criteria. Useful only after edit reliability is solid (otherwise you are verifying garbage).
10. **Validation cascade hardening** -- Add timeout enforcement, fallback ordering, degraded-mode tracking for LSP.

## Sources

- [Code Surgery: How AI Assistants Make Precise Edits](https://fabianhertwig.com/blog/coding-assistants-file-edits/) -- Comparative analysis of edit strategies across Aider, Cursor, Codex, RooCode, OpenHands. HIGH confidence.
- [oh-my-pi: Hash-Anchored Edits](https://github.com/can1357/oh-my-pi) -- Hash-anchor approach with stale detection. Benchmarked across 16 models. MEDIUM confidence (single project, but with quantitative benchmarks).
- [Advanced Context Engineering for Coding Agents](https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/ace-fca.md) -- Context budget patterns, 40-60% utilization target, sub-agent compaction. HIGH confidence.
- [LangGraph Persistence Docs](https://docs.langchain.com/oss/python/langgraph/persistence) -- Checkpointer API, AsyncSqliteSaver, thread-based resumption. HIGH confidence (official docs).
- [Advanced Error Handling in LangGraph](https://sparkco.ai/blog/advanced-error-handling-strategies-in-langgraph-applications) -- Node-level error objects, circuit breakers, graceful degradation. MEDIUM confidence.
- [Coding Agent Loop Spec (strongdm/attractor)](https://github.com/strongdm/attractor/blob/main/coding-agent-loop-spec.md) -- Turn-based loop spec with progress detection and loop guards. HIGH confidence (production-derived spec).
- [Aider Edit Formats](https://aider.chat/docs/more/edit-formats.html) -- Layered matching: exact -> whitespace -> indentation -> fuzzy. HIGH confidence.
- [SWE-Agent: Agent-Computer Interfaces](https://proceedings.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf) -- Repeated edit failure modes, guardrail patterns. HIGH confidence (NeurIPS paper).
- [Infinite Agent Loop Detection](https://www.agentpatterns.tech/en/failures/infinite-loop) -- Loop detection patterns for agents. MEDIUM confidence.
- [Hermes Agent Independent Verification](https://github.com/NousResearch/hermes-agent/issues/406) -- Independent code verification and quality gates. MEDIUM confidence.

---

*Architecture research: 2026-03-26*
