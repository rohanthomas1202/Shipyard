# Phase 5: Agent Core Features - Research

**Researched:** 2026-03-26
**Domain:** Agent loop lifecycle, context injection, multi-agent coordination, git workflow automation
**Confidence:** HIGH

## Summary

Phase 5 implements four requirements that bring the agent from a single-shot executor to a persistent, context-aware, multi-agent system with end-to-end git automation. The good news is that most infrastructure already exists — the task is primarily wiring, gap-filling, and verification rather than greenfield construction.

**CORE-01 (persistent loop):** The server already has `POST /instruction` for new runs and `POST /instruction/{run_id}` for continuing runs. The gap is that `/instruction` always creates a brand-new run with a brand-new graph invocation. A true "accept next instruction without restart" flow means the server stays up and each new `POST /instruction` cleanly initializes a fresh run on the same long-lived process. This already works — the in-memory `runs` dict and `asyncio.create_task` pattern handle multiple sequential runs. The main verification needed is that state is properly reset between runs (no leakage from previous run state).

**CORE-02 (context injection):** The `InstructionRequest` already accepts `context: dict = {}`, and `planner_node` already uses `ContextAssembler` to inject `context["spec"]`, `context["schema"]`, and `context["files"]` into the planner prompt. The gap is that context is NOT passed through to editor, reader, refactor, or validator nodes. The `ContextAssembler` is wired into those nodes (Phase 3, CTX-01), but they only use file_buffer and error state — they do not pull from `state["context"]`. The fix is to thread `state["context"]` into the assembler calls in each LLM-calling node.

**CORE-03 (multi-agent coordination):** The coordinator node groups steps into parallel/sequential batches, and the merger node detects same-file conflicts. However, the graph does NOT actually fan out into parallel execution. The graph flow is linear: coordinator -> classify -> reader -> editor -> ... The `parallel_batches` and `sequential_first` fields are set but never consumed by the graph routing. True multi-agent means either (a) LangGraph subgraph fan-out, or (b) asyncio.gather on multiple graph invocations. The simpler approach is (b): spawn multiple graph runs for independent batches.

**CORE-04 (git ops end-to-end):** `git_ops_node` already implements branch -> stage -> commit -> push -> PR. `GitManager` handles local git ops. `GitHubClient` handles PR creation via REST API. The `git_ops_node` is wired into the graph via `classify_step` when `kind == "git"`. The gap is that the git step must be a plan step of kind "git" to trigger — but the planner may not always generate one. The fix is either (a) always append a git step to the plan, or (b) add git_ops as a post-reporter step in the graph for all runs.

**Primary recommendation:** Wire context through to all LLM nodes, implement parallel execution via asyncio.gather on separate graph invocations, ensure git_ops runs automatically after edits, and add integration tests proving all four requirements.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Agent runs in persistent loop accepting new instructions without restarting | Server already supports this via `POST /instruction`. Verify state isolation between runs. |
| CORE-02 | Agent accepts injected external context and uses it in LLM generation | `InstructionRequest.context` exists; planner uses it. Wire to editor/reader/validator/refactor nodes. |
| CORE-03 | Multi-agent coordination with 2+ agents parallel/sequential, merged outputs | Coordinator produces batches. Implement actual parallel execution and result merging. |
| CORE-04 | Git operations end-to-end: branch, stage, commit, push, PR | `git_ops_node` and `GitManager`/`GitHubClient` exist. Ensure automatic triggering and end-to-end flow. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.1.3 | Agent graph orchestration | Already committed, pinned |
| fastapi | >=0.115.0 | Server endpoints | Already in use |
| httpx | >=0.28.0 | GitHub API client | Already in use via `agent/github.py` |
| asyncio | stdlib | Parallel agent execution | No external dependency needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | (transitive) | Request/response models | Already in use |
| aiosqlite | >=0.20.0 | Async SQLite for run persistence | Already in use |

**No new dependencies needed.** Everything required is already installed.

## Architecture Patterns

### Pattern 1: State Isolation Between Sequential Runs
**What:** Each `POST /instruction` creates a completely fresh `initial_state` dict. The `runs` dict is keyed by `run_id` with independent entries. No shared mutable state leaks between runs.
**When to use:** CORE-01 verification
**Current state:** Already implemented in `submit_instruction()` (server/main.py lines 266-356). Each call generates a new `run_id`, fresh `initial_state`, and a new `asyncio.create_task`.
**Gap:** No test currently verifies that submitting a second instruction after the first completes works correctly on the same server process.

### Pattern 2: Context Threading Through All LLM Nodes
**What:** `state["context"]` must be consumed by every node that calls the LLM via `ContextAssembler`.
**Current state:** Only `planner_node` reads `state["context"]` (lines 18-35 of `agent/nodes/planner.py`).
**Required changes:**
- `editor_node`: Add context injection (specs, schemas, test results) into the editor's assembler
- `reader_node`: Add context injection for targeted reading
- `validator_node`: Add context (e.g., test results) for validation prompts
- `refactor_node`: Add context for refactoring decisions

```python
# Pattern for context injection in any LLM-calling node:
context = state.get("context", {})
if context.get("spec"):
    assembler.add_file("spec", context["spec"], priority="reference")
if context.get("schema"):
    assembler.add_file("schema", context["schema"], priority="reference")
if context.get("test_results"):
    assembler.add_error(context["test_results"])  # as execution evidence
```

### Pattern 3: Parallel Agent Execution via asyncio.gather
**What:** After coordinator identifies parallel batches, spawn independent graph invocations for each batch, then merge results.
**Why not LangGraph subgraph fan-out:** The current graph is monolithic. Adding native LangGraph `Send` API for fan-out would require restructuring the entire graph. Instead, use the simpler pattern of running multiple complete graph invocations concurrently.

```python
# In coordinator or a new parallel_executor node:
async def execute_parallel_batches(batches, base_state, config):
    """Run independent step-groups as separate graph invocations."""
    tasks = []
    for batch_indices in batches:
        batch_state = {**base_state}
        batch_state["plan"] = [base_state["plan"][i] for i in batch_indices]
        batch_state["current_step"] = 0
        task = asyncio.create_task(graph.ainvoke(batch_state, config=config))
        tasks.append(task)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

**Merge strategy:** Collect `edit_history` from all batch results, detect same-file conflicts (merger_node already does this), combine into single state.

### Pattern 4: Automatic Git Operations
**What:** After all edits are complete, automatically run git ops without requiring a plan step of kind "git".
**Current state:** `git_ops_node` only runs when the planner explicitly creates a `kind: "git"` step.
**Recommended change:** Add a graph edge from `reporter` to `git_ops` (instead of `reporter -> END`), or add a conditional edge that checks if edits were made and triggers git_ops automatically.

```python
# Option A: reporter -> git_ops -> END
graph.add_edge("reporter", "git_ops")
graph.add_edge("git_ops", END)

# Option B: conditional after reporter
def after_reporter(state: dict) -> str:
    if state.get("edit_history"):
        return "git_ops"
    return "end"
```

### Anti-Patterns to Avoid
- **Shared mutable state between parallel agents:** Each parallel batch MUST get its own copy of `file_buffer`, `edit_history`, etc. Never share mutable dicts.
- **Blocking git operations in parallel:** GitManager uses per-repo locks (`_repo_locks`). Parallel agents hitting the same repo will serialize automatically, which is correct — do not remove the locks.
- **Context bloat:** Do not dump entire context dict into every prompt. Use ContextAssembler's token budget to prevent overflow.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel task execution | Custom thread pool or process pool | `asyncio.gather` with `create_task` | Already async codebase; processes add serialization overhead |
| Git operations | Raw subprocess git calls | `GitManager` class | Already handles locking, error handling, dirty-tree stash |
| GitHub API | Raw httpx calls | `GitHubClient` class | Already handles auth headers, PR creation, merge |
| Context budgeting | Manual string truncation | `ContextAssembler` | Already implements priority-based token budgeting |
| Run state management | Custom state store | Existing `runs` dict + SQLiteSessionStore | Already handles run lifecycle, persistence, task tracking |

## Common Pitfalls

### Pitfall 1: State Leakage Between Sequential Runs
**What goes wrong:** Previous run's `file_buffer`, `edit_history`, or `error_state` bleeds into the next run.
**Why it happens:** If code reuses state objects instead of creating fresh ones.
**How to avoid:** Each `POST /instruction` already creates a brand-new `initial_state` dict. Verify this with a test that submits two instructions sequentially and checks the second run has empty edit_history.
**Warning signs:** Second run shows edits from first run in its history.

### Pitfall 2: Parallel Agents Writing Same File
**What goes wrong:** Two parallel graph invocations edit the same file, last write wins silently.
**Why it happens:** Coordinator groups by directory (api/ vs web/) but can't detect cross-directory file dependencies.
**How to avoid:** Merger node detects same-file conflicts. On conflict, re-run conflicting steps sequentially.
**Warning signs:** `has_conflicts: true` in merger output.

### Pitfall 3: Git Branch Already Exists
**What goes wrong:** `ensure_branch` fails because a branch with the same slug already exists.
**Why it happens:** Multiple runs with similar instructions.
**How to avoid:** Already handled — `ensure_branch` appends `-2`, `-3` suffixes. Verify with test.

### Pitfall 4: GitHub PAT Not Configured
**What goes wrong:** `git_ops_node` reaches PR creation but project has no `github_pat`.
**Why it happens:** Project settings not configured.
**How to avoid:** `git_ops_node` already checks `github_repo and github_pat` before attempting PR. Push and commit still succeed locally. PR creation is best-effort.

### Pitfall 5: Context Not Reaching Editor
**What goes wrong:** User provides spec/schema in context, but editor prompt doesn't include it.
**Why it happens:** Only planner currently reads `state["context"]`.
**How to avoid:** Thread context through all LLM-calling nodes as described in Pattern 2.

## Code Examples

### Current: How /instruction Creates a Run (Already Works for CORE-01)
```python
# server/main.py, submit_instruction()
initial_state = {
    "messages": [],
    "instruction": req.instruction,
    "working_directory": req.working_directory,
    "context": req.context,  # <-- context injection point
    "plan": [],
    "current_step": 0,
    "file_buffer": {},
    "edit_history": [],
    "error_state": None,
    "is_parallel": False,
    "parallel_batches": [],
    "sequential_first": [],
    "has_conflicts": False,
    "ast_available": {},
    "invalidated_files": [],
}
task = asyncio.create_task(execute())
runs[run_id]["task"] = task
```

### Current: How Planner Uses Context (Pattern for Other Nodes)
```python
# agent/nodes/planner.py
context = state.get("context", {})
if context.get("spec"):
    assembler.add_file("spec", context["spec"], priority="working")
if context.get("schema"):
    assembler.add_file("schema", context["schema"], priority="reference")
if context.get("files"):
    assembler.add_file("key_files", ", ".join(context["files"]), priority="reference")
```

### Current: How git_ops_node Runs Full Pipeline
```python
# agent/nodes/git_ops.py — already implements branch->stage->commit->push->PR
# 1. ensure_branch (creates shipyard/<slug>-<run_id>)
# 2. stage_files (from applied edits in store)
# 3. commit (with LLM-generated message)
# 4. push (best-effort, skips if no remote)
# 5. PR creation (if github_repo + github_pat configured)
```

### Needed: Parallel Execution Pattern
```python
# New function in coordinator or separate parallel_executor module
async def run_parallel_batches(graph, batches, base_state, config):
    async def run_batch(indices):
        batch_state = dict(base_state)
        batch_state["plan"] = [base_state["plan"][i] for i in indices]
        batch_state["current_step"] = 0
        batch_state["edit_history"] = []
        batch_state["file_buffer"] = {}
        return await graph.ainvoke(batch_state, config=config)

    results = await asyncio.gather(
        *[run_batch(indices) for indices in batches],
        return_exceptions=True,
    )
    return results
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | pyproject.toml (test section) |
| Quick run command | `.venv311/bin/python3 -m pytest tests/ -x -q` |
| Full suite command | `.venv311/bin/python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | Sequential instructions without restart | integration | `.venv311/bin/python3 -m pytest tests/test_persistent_loop.py -x` | Wave 0 |
| CORE-02 | Context flows to all LLM nodes | unit | `.venv311/bin/python3 -m pytest tests/test_context_injection.py -x` | Wave 0 |
| CORE-03 | Parallel agents merge outputs | unit+integration | `.venv311/bin/python3 -m pytest tests/test_multiagent.py tests/test_parallel_execution.py -x` | Partial (test_multiagent.py exists) |
| CORE-04 | Git branch->commit->push->PR flow | integration | `.venv311/bin/python3 -m pytest tests/test_git_ops_node.py tests/test_git.py tests/test_github.py -x` | Exists |

### Sampling Rate
- **Per task commit:** `.venv311/bin/python3 -m pytest tests/ -x -q`
- **Per wave merge:** `.venv311/bin/python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_persistent_loop.py` -- CORE-01: two sequential POST /instruction on same server
- [ ] `tests/test_context_injection.py` -- CORE-02: verify context reaches editor/reader/validator nodes
- [ ] `tests/test_parallel_execution.py` -- CORE-03: parallel batch execution and merge
- [ ] Update `tests/test_git_ops_node.py` -- CORE-04: test automatic git_ops triggering after edits

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All | (3.14.3 available, .venv311 has 3.11) | 3.11 via venv | -- |
| git | CORE-04 | Yes | 2.50.1 | -- |
| gh (GitHub CLI) | CORE-04 verification | Yes | 2.87.2 | Not needed; uses httpx directly |
| pytest | Testing | Yes | 9.0.2 (venv) | -- |

**Missing dependencies with no fallback:** None.

## Open Questions

1. **Should git_ops run automatically or only when planner generates a git step?**
   - What we know: Currently only triggered by `kind: "git"` plan step. The planner may not always produce one.
   - Recommendation: Make git_ops automatic after reporter when edits exist. Add conditional edge.

2. **How should parallel agent results be merged when both succeed?**
   - What we know: Merger node detects same-file conflicts but doesn't resolve them.
   - Recommendation: On conflict, log it and re-run conflicting steps sequentially. On no conflict, concatenate edit_histories.

3. **Should context support arbitrary key-value pairs beyond spec/schema/files?**
   - What we know: Current code checks specific keys (`spec`, `schema`, `files`).
   - Recommendation: Support a generic `context["extra"]` field as a catch-all string, plus keep typed keys for common cases like `test_results`.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `server/main.py`, `agent/graph.py`, `agent/nodes/coordinator.py`, `agent/nodes/git_ops.py`, `agent/git.py`, `agent/github.py`, `agent/context.py`, `agent/nodes/planner.py`, `agent/state.py`
- Existing test files: `tests/test_multiagent.py`, `tests/test_git.py`, `tests/test_git_ops_node.py`, `tests/test_github.py`, `tests/test_server.py`

### Secondary (MEDIUM confidence)
- LangGraph documentation for subgraph patterns (training data, not live-verified)

## Project Constraints (from CLAUDE.md)

- **LLM Provider:** OpenAI (o3/gpt-4o/gpt-4o-mini) -- no other providers
- **Framework:** LangGraph 1.1.3 -- committed, not switching
- **File editing:** Anchor-based string replacement -- committed
- **Deployment:** Heroku/Railway PaaS, single-process uvicorn
- **Node conventions:** `async def {name}_node(state: dict, config: RunnableConfig) -> dict:`
- **DI pattern:** `config["configurable"]` for runtime dependencies
- **State pattern:** Flat TypedDict, nodes return partial dicts
- **LLM calls:** Always through `router.call(task_type, system, user)`, never direct
- **Naming:** snake_case modules, PascalCase classes, UPPER_SNAKE for constants
- **No Co-Authored-By lines in commits** (from user memory)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new deps needed
- Architecture: HIGH - patterns derived from direct codebase analysis
- Pitfalls: HIGH - identified from actual code gaps, not hypothetical

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable codebase, no external dependency changes expected)
