# AI Development Log — Shipyard

## Tools and Workflow

### Primary AI Tool

**Claude (Anthropic)** via Claude Code CLI was the sole AI tool used for all development — planning, coding, testing, debugging, and documentation. No other coding assistants were used during development.

### Development Workflow

**GSD (Get Shit Done) Framework** — a structured planning and execution system that enforces:

1. **ROADMAP.md** — 7-phase dependency-ordered roadmap with success criteria per phase
2. **Per-phase plans** — Each phase contains 2-3 focused plans (18 total plans across 7 phases)
3. **Atomic execution** — Each plan is executed as a unit: discuss, plan, execute, verify
4. **STATE.md tracking** — Accumulated decisions, blockers, and session continuity across all plans
5. **SUMMARY.md per plan** — Post-execution documentation with commits, deviations, and metrics

### Supporting Tools

- **LangSmith** — Trace observability for every agent graph execution (automatic via LangGraph integration)
- **pytest + pytest-asyncio** — Python test runner for integration tests with mock router fixtures
- **Git** — Version control with atomic per-task commits following conventional commit format
- **ESLint** — Frontend linting for React/TypeScript code quality

### Development Pattern

Each of the 7 phases followed the same cycle:
1. **Discuss** — Review requirements, identify dependencies, scope the work
2. **Plan** — Create detailed plan files with tasks, verification steps, and acceptance criteria
3. **Execute** — Implement each task atomically, commit after verification passes
4. **Verify** — Run automated checks, review outputs, confirm success criteria met

### Key Metrics

- **7 phases** executed sequentially over the project timeline
- **18 total plans** with an average of ~3 minutes execution time each
- **~50 minutes total Claude execution time** across all plans
- **Model used for development:** Claude (Anthropic) — planning, coding, testing, documentation
- **Model used by the agent:** OpenAI o3/gpt-4o/gpt-4o-mini with tiered routing (o3 for planning, gpt-4o for edits, gpt-4o-mini for validation)

---

## Effective Prompts and Interactions

### 1. Structured Instruction Decomposition

**Pattern:** Break complex instructions into typed plan steps with explicit target files, step kind, and acceptance criteria.

**Example prompt to the agent:**
> "Add a 'tags' field (string array) to the Document interface, update the create function in src/models/document.ts to accept tags, and add a DocumentList filter that only shows documents matching a selected tag."

**Why it works:** The planner decomposes this into a `PlanStep` JSON array with `kind: "edit"`, `target_files`, and `acceptance_criteria` per step. This gives the editor precise scope — it knows exactly which file to read and what change to make, rather than trying to infer the full scope from a vague instruction.

**Result:** Multi-file instructions that previously required manual intervention completed autonomously when structured this way.

### 2. Error-Contextualized Retries

**Pattern:** When an edit fails, include the specific anchor that failed, what was found instead, and the similarity score in the retry prompt.

**Example feedback loop:**
> "Anchor not found (similarity: 0.72). Expected: `description: text('description'),\n  status:` — Found nearest match at line 45: `description: text('description'),\n    status:` (indentation mismatch). Re-read the file and use the exact whitespace."

**Why it works:** Informed retries converge in 1 attempt instead of 3. The LLM knows exactly what went wrong (whitespace, not content) and adjusts precisely. Blind retries often produce the same anchor again.

**Result:** Average retry loops dropped from 3 to 1 after implementing error feedback in Phase 1 (Plan 03).

### 3. Graduated Complexity for Rebuild

**Pattern:** Start with simple single-field additions before attempting multi-file coordination. Each successful instruction builds confidence and context for the next.

**Example sequence (from rebuild orchestrator):**
1. Add a `status` field to Document interface (single file, single edit)
2. Add a GET /ready health endpoint (single file, new function)
3. Add documents CRUD routes (new file + register in app — 2 files)
4. Add tags field and filter (3 files — model, type, component)
5. Parallel: priority field + DELETE endpoint (multi-agent, 2 independent edits)

**Why it works:** The agent accumulates file_buffer context from earlier steps. By the time it hits the complex multi-file task, it has already seen the codebase structure. Jumping straight to instruction 5 would force cold reads of every file.

### 4. Context Injection via Structured JSON

**Pattern:** Provide schemas, specs, and file hints as structured JSON in the instruction payload's `context` field, rather than embedding them in the instruction text.

**Example:**
```json
{
  "instruction": "Add a due_date field to the Document model",
  "context": {
    "schema": { "Document": { "fields": ["id", "title", "content", "status"] } },
    "file_hints": ["src/types/index.ts", "src/models/document.ts"]
  }
}
```

**Why it works:** The ContextAssembler ranks context by priority (instruction > schema > file contents > history) and fills the token budget accordingly. Structured context gets higher priority than inferred context from file reads.

### 5. Negative Constraints in System Prompts

**Pattern:** Explicitly state what the LLM should NOT do, preventing common failure modes.

**Examples used in Shipyard's editor prompts:**
- "Do NOT use unified diff format — return anchor and replacement strings only"
- "Do NOT rewrite the entire file — produce the minimal change that achieves the edit"
- "Do NOT include line numbers in the anchor — use the actual text content"

**Why it works:** LLMs have strong priors from training on diff-heavy codebases. Without negative constraints, the editor would occasionally produce unified diffs or full file rewrites, both of which bypass the anchor-based validation pipeline.

---

## Code Analysis

### Codebase Overview

- **~30 Python modules** across `agent/`, `server/`, `store/` directories
- **React frontend** in `web/src/` with ~15 components, 3 context providers, and custom hooks
- **12 direct Python dependencies** (openai, langgraph, langchain-openai, fastapi, uvicorn, httpx, aiosqlite, pyyaml, pydantic, ast-grep-py, pygls, lsprotocol)
- **SQLite** for persistence — zero-config, single-file database

### Key Architectural Patterns

1. **LangGraph StateGraph with conditional edges** — The agent graph (`agent/graph.py`) uses `should_continue()` to route between retry loops, error recovery, and completion based on `error_state` and retry count.

2. **Anchor-based surgical editing** — The core edit strategy (`agent/nodes/editor.py`) uses `content.replace(anchor, replacement, 1)` with fuzzy matching fallback (FUZZY_THRESHOLD=0.85) and snapshot-based rollback.

3. **Tiered model routing** — `ModelRouter` in `agent/router.py` maps task types to model tiers (o3 for reasoning, gpt-4o for general, gpt-4o-mini for fast) with automatic escalation on failure.

4. **Priority event streaming** — `EventBus` classifies events as P0 (immediate: approvals), P1 (batched at 50ms: token streams), P2 (node boundary flush: status updates).

5. **Protocol-based store abstraction** — `SessionStore` Protocol in `store/protocol.py` enables swappable backends. Currently backed by `SQLiteSessionStore` with WAL mode.

### Code Quality

- **Fully typed Python 3.11+** — Modern union syntax (`str | None`), TypedDict for graph state, Pydantic models for persistence, dataclasses for config
- **Async throughout** — All node entry points are `async def`, subprocess calls use `asyncio.create_subprocess_exec`, database uses aiosqlite
- **Consistent naming** — `snake_case` for Python modules/functions, `PascalCase` for classes, `{name}_node()` for graph entry points
- **Module docstrings** on every Python file explaining purpose

### Test Coverage

- Integration tests with mock router fixtures (no real LLM calls in tests)
- Ship-like fixture project for end-to-end edit testing
- LSP validation integration tests with diagnostic diffing
- pytest-asyncio for async test support

### Known Weaknesses

- Some code duplication (`_normalize_error` exists in both `graph.py` and `validator.py`) due to circular import avoidance
- Ad-hoc logging in some nodes (`logging.getLogger("shipyard.editor")`) alongside the structured TraceLogger
- No `.flake8` or `ruff.toml` — Python linting not enforced by config

---

## Strengths and Limitations of AI-Assisted Development

### Strengths

1. **Consistency across long sessions** — No fatigue, no context drift within a plan. The 18th plan was executed with the same discipline as the 1st.

2. **Speed** — 18 plans averaging ~3 minutes each. Features that would take hours of manual coding were planned, implemented, tested, and committed in minutes.

3. **Structured approach** — The GSD framework prevented scope creep. Each plan had explicit acceptance criteria that had to pass before moving on. Without this structure, AI tends to over-engineer or wander.

4. **Test-first thinking** — Verification criteria were defined before implementation in every plan. This caught issues early — the validator rollback logic, for example, was tested before it was needed in production.

5. **Cross-cutting consistency** — Naming conventions, import patterns, error handling approaches were maintained across all 30+ modules because the same AI applied the same conventions throughout.

6. **Fearless refactoring** — Changing the router interface (Phase 3, Plan 01) touched 8 files. With AI, this was a single plan with atomic commits. Manually, this would be error-prone and tedious.

### Limitations

1. **Context window pressure** — Complex plans with many files degrade quality past 50% context usage. The solution was keeping plans small (2-3 tasks) and reading only relevant line ranges.

2. **Stale assumptions** — AI occasionally references APIs that have changed since training (e.g., LangGraph checkpoint API evolved between versions). Required manual verification of API signatures.

3. **Over-engineering tendency** — Without explicit negative constraints, AI adds unnecessary abstractions, extra error handling layers, or premature optimizations. The "Do NOT" patterns in system prompts were essential.

4. **Debugging blind spots** — AI cannot actually run the application and observe behavior. It relies entirely on test output, syntax checks, and static analysis. Subtle runtime issues (race conditions, WebSocket timing) require human observation.

5. **Circular dependency detection** — AI sometimes creates import cycles that only surface at runtime. The `_normalize_error` duplication was a pragmatic fix, but ideally the AI would detect and avoid circular imports proactively.

6. `[FILL AFTER REBUILD: specific limitations observed during Ship rebuild — e.g., how the agent handled ambiguous instructions, multi-file coordination failures, anchor matching on generated code]`

---

## Key Learnings

### 1. Plans are prompts
The quality of the plan file directly determines execution quality. A vague plan produces vague code. Plans with explicit `target_files`, `acceptance_criteria`, and `verify` commands produce precise, tested code. Treat plan authoring as prompt engineering.

### 2. Small plans win
2-3 tasks per plan keeps context fresh and quality high. Plans with 5+ tasks showed degraded quality on later tasks as context filled up. The GSD framework's atomic plan execution enforced this naturally.

### 3. Vertical slices over horizontal layers
Feature-complete vertical slices (e.g., "add checkpointing end-to-end") parallelize better and catch integration issues earlier than horizontal layers (e.g., "add all models first, then all routes"). Each phase in Shipyard was organized around capabilities, not code layers.

### 4. Error feedback loops matter more than retry count
Informed retries (with specific failure context) converge faster than blind retries (just "try again"). Phase 1's error feedback implementation cut average retries from 3 to 1. The circuit breaker (Phase 2) added a hard cap of 2 identical errors before escalation.

### 5. Anchor-based editing is robust but brittle on large files
Files under 200 lines edit cleanly. Files over 200 lines need line-range reads (Phase 3, Plan 02) to prevent the editor from selecting ambiguous anchors. The skeleton reader (head=30, tail=10) gives the editor enough context without token waste.

### 6. Circuit breakers prevent infinite loops
Without the 2-strike rule (Phase 2, Plan 03), the agent would retry the same failing edit 3 times with identical prompts. The circuit breaker escalates the model tier or skips the step, saving tokens and time.

### 7. Dependency ordering is everything
The roadmap's phase ordering (edit reliability -> validation -> context -> recovery -> features -> rebuild -> deliverables) meant each phase built on proven foundations. Attempting the Ship rebuild before edit reliability was hardened would have produced chaos.

### 8. `[FILL AFTER REBUILD: key learning from actual Ship rebuild experience — e.g., how many interventions were needed, what class of failures dominated, whether the graduated instruction approach worked]`
