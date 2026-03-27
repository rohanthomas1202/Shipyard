# Phase 2: Validation & Infrastructure - Research

**Researched:** 2026-03-26
**Domain:** Python syntax validation, LSP diagnostic diffing, circuit breaker patterns, async subprocess, SQLite WAL
**Confidence:** HIGH

## Summary

Phase 2 addresses five requirements across two domains: validation hardening (VALID-02, VALID-03, VALID-04) and infrastructure reliability (INFRA-01, INFRA-02). The codebase is well-positioned for all five changes. The validator already has a tiered architecture (LSP -> subprocess fallback) with structured error outputs from Phase 1. The async subprocess wrapper (`run_command_async`) already exists in `shell.py` but is not used by the executor node. SQLite uses `aiosqlite` but does not enable WAL mode.

All five requirements are achievable with Python stdlib and the existing dependency set. No new packages are needed. The changes are independent of each other (no ordering dependencies between the five requirements), which makes parallel planning viable.

**Primary recommendation:** Implement as three independent work streams: (1) validator enhancements (VALID-02/03/04 together, since they all touch `validator.py` and `graph.py`), (2) async subprocess conversion (INFRA-01, touches `executor.py` and `validator.py`), (3) SQLite WAL (INFRA-02, single line in `store/sqlite.py`). Stream 1 and 2 overlap on `validator.py`, so they should be sequenced (INFRA-01 first since it is simpler, then VALID-* on top).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicitly locked. All implementation choices are at Claude's discretion.

### Claude's Discretion
All implementation choices are at Claude's discretion -- pure infrastructure phase. Key constraints from research:
- Python syntax checking via py_compile or ast.parse
- LSP diffing must gracefully fall back to subprocess checks when unavailable
- Circuit breaker: after 2 identical errors, escalate model tier or skip step
- Async subprocesses: use asyncio.create_subprocess_exec instead of subprocess.run
- SQLite WAL mode: set on connection open via PRAGMA journal_mode=WAL

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VALID-02 | Validator checks Python file syntax via py_compile or ast.parse after edits | Add `.py` branch to `_syntax_check()` using `ast.parse()` -- stdlib, zero deps, catches SyntaxError with line/col info |
| VALID-03 | LSP diagnostic diffing reliably detects only NEW errors, with graceful fallback when LSP unavailable | LSP diffing already implemented in `_lsp_validate()`. Needs: ensure fallback path covers all edge cases (LSP timeout, crash, degraded). Current code already falls back on exception. |
| VALID-04 | Circuit breaker -- after 2 identical errors on same file/step, escalate model tier or skip step | Requires error history tracking in state + logic in `should_continue()` to detect repeated errors and route differently |
| INFRA-01 | All subprocess calls async (non-blocking) | `run_command_async()` exists. `executor_node` uses sync `run_command()`. `_syntax_check()` uses `subprocess.run` directly. Convert both. |
| INFRA-02 | SQLite WAL mode for concurrent access | Single PRAGMA after `aiosqlite.connect()` in `SQLiteSessionStore.initialize()` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ast (stdlib) | Python 3.11 | Python syntax validation | Returns SyntaxError with exact line/col, no subprocess overhead, handles all Python 3.11 syntax |
| asyncio (stdlib) | Python 3.11 | Async subprocess execution | `create_subprocess_exec` is the standard async subprocess API |
| aiosqlite | 0.22.1 | Async SQLite with WAL support | Already in use, supports PRAGMA execution |

### Supporting
No new dependencies needed. Everything is stdlib or already installed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ast.parse | py_compile | py_compile writes .pyc files as side effect, ast.parse is pure in-memory |
| ast.parse | subprocess python -m py_compile | Adds subprocess overhead for something stdlib can do in-process |

## Architecture Patterns

### Recommended Changes by File

```
agent/nodes/validator.py   # VALID-02: add .py to _syntax_check()
                            # VALID-03: harden LSP fallback paths
                            # INFRA-01: convert _syntax_check subprocess.run to async
agent/nodes/executor.py     # INFRA-01: convert to async, use run_command_async
agent/graph.py              # VALID-04: circuit breaker in should_continue()
agent/state.py              # VALID-04: add error_history field for tracking
store/sqlite.py             # INFRA-02: WAL pragma in initialize()
```

### Pattern 1: Python Syntax Checking with ast.parse
**What:** Add `.py` extension handling to `_syntax_check()` using `ast.parse(source, filename)`
**When to use:** Every time a `.py` file is edited
**Example:**
```python
# In _syntax_check(), add before the final return
if ext == ".py":
    try:
        with open(file_path) as f:
            source = f.read()
        ast.parse(source, filename=file_path)
        return {"valid": True, "error": None}
    except SyntaxError as e:
        return {"valid": False, "error": f"Line {e.lineno}: {e.msg}"}
```

### Pattern 2: Circuit Breaker via Error History
**What:** Track (file, error_message) tuples in state. When the same error appears 2+ times for the same file/step, escalate or skip instead of retrying.
**When to use:** In `should_continue()` decision logic
**Key design:** The circuit breaker must distinguish "same error repeating" from "different errors on same file". Only identical errors (same message) trigger escalation.
**Example:**
```python
# In should_continue() or a helper
def _detect_repeated_error(state: dict) -> bool:
    """Check if the last 2 errors on the same file/step are identical."""
    history = state.get("edit_history", [])
    lve = state.get("last_validation_error")
    if not lve:
        return False
    file_path = lve.get("file_path", "")
    error_msg = lve.get("error_message", "")
    step = state.get("current_step", 0)

    # Count identical errors in recent history for this file+step
    count = 0
    for entry in reversed(history):
        if entry.get("file") == file_path and entry.get("step") == step:
            if entry.get("error") == error_msg:
                count += 1
            else:
                break
        elif entry.get("file") != file_path:
            break
    return count >= 2
```

### Pattern 3: Async Executor Node
**What:** Convert `executor_node` from sync to async, using `run_command_async` instead of `run_command`
**When to use:** All shell command execution in the graph
**Example:**
```python
async def executor_node(state: dict) -> dict:
    # ... same logic ...
    result = await run_command_async(
        ["sh", "-c", command],  # or split command properly
        cwd=working_dir,
        timeout=60,
    )
    # ... same error handling ...
```

### Pattern 4: Async Syntax Checks in Validator
**What:** Convert `_syntax_check` from sync subprocess.run calls to async
**When to use:** For TS/JS/esbuild checks that shell out
**Key insight:** The validator already wraps `_syntax_check` in `asyncio.to_thread()`. Two options: (a) keep `_syntax_check` sync but replace subprocess.run with the thread approach (already done), or (b) make `_syntax_check` fully async. Option (b) is cleaner since `run_command_async` already exists.
**Example:**
```python
async def _syntax_check(file_path: str) -> dict:
    """Async language-appropriate syntax check."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        # Pure Python -- no subprocess needed
        try:
            with open(file_path) as f:
                ast.parse(f.read(), filename=file_path)
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {"valid": False, "error": f"Line {e.lineno}: {e.msg}"}

    if ext in (".ts", ".tsx"):
        result = await run_command_async(
            ["npx", "esbuild", file_path],
            timeout=30,
        )
        if result["exit_code"] != 0:
            return {"valid": False, "error": result["stderr"][:500]}
        return {"valid": True, "error": None}
    # ... etc
```

### Pattern 5: SQLite WAL Mode
**What:** Enable WAL journal mode immediately after connection
**When to use:** In `SQLiteSessionStore.initialize()`
**Example:**
```python
async def initialize(self):
    self._db = await aiosqlite.connect(self._db_path)
    await self._db.execute("PRAGMA journal_mode=WAL")
    self._db.row_factory = aiosqlite.Row
    await self._db.executescript(_SCHEMA)
    await self._db.commit()
```

### Anti-Patterns to Avoid
- **Subprocess for Python syntax checking:** `ast.parse()` is faster, has no side effects, and gives better error messages than shelling out to `python -m py_compile`
- **Tracking circuit breaker state externally:** Keep error history in `AgentState` (graph state), not in module-level variables. The graph state is the single source of truth.
- **Using shell=True for async commands:** `run_command_async` correctly uses `create_subprocess_exec` with argv list. The sync `run_command` uses `shell=True` which is a security concern -- do not replicate this in the async conversion.
- **Committing after every WAL pragma:** WAL mode is set per-connection, not per-database. It persists until changed but should be set on every connection open for safety.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Python syntax checking | Custom regex parser | `ast.parse()` from stdlib | Handles all Python 3.11 syntax edge cases including f-strings, match/case, walrus operator |
| Async subprocess | Custom process manager | `asyncio.create_subprocess_exec` (via existing `run_command_async`) | Already implemented and tested in `shell.py` |
| SQLite concurrency | Custom locking/queueing | WAL mode (`PRAGMA journal_mode=WAL`) | SQLite's built-in solution, readers never block writers |
| Error deduplication | Hash-based custom dedup | Simple string equality on `error_message` field | Error messages from syntax checkers and LSP are deterministic for the same bug |

## Common Pitfalls

### Pitfall 1: ast.parse False Negatives on Encoding
**What goes wrong:** `ast.parse()` with default encoding may fail on files with non-UTF-8 encoding
**Why it happens:** Python source files can declare encoding via `# -*- coding: ... -*-` magic comment
**How to avoid:** Read file as bytes and let `ast.parse()` handle encoding detection, or read as UTF-8 with errors='replace' (acceptable for syntax checking)
**Warning signs:** SyntaxError mentioning encoding on files that are valid Python

### Pitfall 2: Circuit Breaker Over-Triggering
**What goes wrong:** Circuit breaker skips steps that would succeed on retry with different context
**Why it happens:** Error messages contain variable content (line numbers, file paths) that change between retries even for the "same" underlying error
**How to avoid:** Normalize error messages before comparison -- strip line numbers and absolute paths, compare the core error description only
**Warning signs:** Steps being skipped that should succeed

### Pitfall 3: Executor Command Splitting
**What goes wrong:** Converting `run_command(command_string)` to `run_command_async(argv_list)` breaks commands with pipes, redirects, or shell features
**Why it happens:** `run_command` uses `shell=True` which lets the shell handle pipes. `run_command_async` uses `create_subprocess_exec` which does not.
**How to avoid:** For the executor node, wrap the command string with `["sh", "-c", command]` to get shell features while still being async. This is the standard pattern.
**Warning signs:** Commands with `|`, `>`, `&&`, or environment variable expansion failing

### Pitfall 4: WAL Mode and Database Copies
**What goes wrong:** Database file grows because WAL checkpoint doesn't run
**Why it happens:** WAL mode creates `-wal` and `-shm` sidecar files. If the process crashes without closing the connection, these can grow unbounded.
**How to avoid:** Ensure `store.close()` is called in the FastAPI lifespan shutdown handler. The existing code already has this pattern.
**Warning signs:** `shipyard.db-wal` file growing to >100MB

### Pitfall 5: Async Validator Breaking Existing Tests
**What goes wrong:** Converting `_syntax_check` to async breaks the existing `asyncio.to_thread(_syntax_check, ...)` call
**Why it happens:** `asyncio.to_thread` wraps a sync function. If `_syntax_check` becomes async, the call site must change.
**How to avoid:** When making `_syntax_check` async, update the call in `validator_node` from `await asyncio.to_thread(_syntax_check, ...)` to `await _syntax_check(...)` directly.
**Warning signs:** `TypeError: object coroutine can't be used in await expression` from to_thread

### Pitfall 6: Circuit Breaker State Not in AgentState TypedDict
**What goes wrong:** New state fields added to circuit breaker logic are silently ignored by LangGraph
**Why it happens:** LangGraph state merging only handles keys declared in the TypedDict
**How to avoid:** If adding new tracking fields, add them to `AgentState` in `state.py`. Alternatively, reuse the existing `edit_history` and `last_validation_error` fields which already contain enough data for deduplication.
**Warning signs:** State appearing to reset between nodes

## Code Examples

### Python Syntax Validation (VALID-02)
```python
# Source: Python stdlib ast module
import ast

def _check_python_syntax(file_path: str) -> dict:
    try:
        with open(file_path, "r") as f:
            source = f.read()
        ast.parse(source, filename=file_path)
        return {"valid": True, "error": None}
    except SyntaxError as e:
        # SyntaxError provides: lineno, offset, msg, text
        error = f"Line {e.lineno}, col {e.offset}: {e.msg}"
        if e.text:
            error += f" | {e.text.strip()}"
        return {"valid": False, "error": error}
```

### Circuit Breaker Decision (VALID-04)
```python
# In graph.py, modify should_continue()
def should_continue(state: dict) -> str:
    error = state.get("error_state")
    plan = state.get("plan", [])
    step = state.get("current_step", 0)

    if error:
        retries = _retry_count(state)
        if retries >= 3:
            return "reporter"
        # Circuit breaker: detect repeated identical errors
        if _has_repeated_error(state, threshold=2):
            # Skip this step and advance (or escalate model --
            # model escalation is already handled by ModelRouter)
            return "advance"  # or "reporter" if last step
        return "reader"

    if step + 1 < len(plan):
        return "advance"
    return "reporter"
```

### WAL Mode (INFRA-02)
```python
# Source: SQLite documentation
async def initialize(self):
    self._db = await aiosqlite.connect(self._db_path)
    await self._db.execute("PRAGMA journal_mode=WAL")
    # Optional: tune WAL for better write performance
    await self._db.execute("PRAGMA synchronous=NORMAL")
    self._db.row_factory = aiosqlite.Row
    await self._db.executescript(_SCHEMA)
    await self._db.commit()
```

### Async Executor (INFRA-01)
```python
# Convert executor_node to async
from agent.tools.shell import run_command_async

async def executor_node(state: dict) -> dict:
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]

    if step >= len(plan):
        return {"error_state": None}

    step_text = plan[step]
    if isinstance(step_text, dict):
        command = step_text.get("command", "")
    else:
        command = step_text
        for prefix in ["Run:", "run:", "Execute:", "execute:"]:
            if prefix in step_text:
                command = step_text.split(prefix, 1)[1].strip()
                break

    # Use sh -c to support pipes/redirects while being async
    result = await run_command_async(["sh", "-c", command], cwd=working_dir)

    tracer.log("executor", {
        "command": command,
        "exit_code": result["exit_code"],
        "stdout_preview": result["stdout"][:200],
        "stderr_preview": result["stderr"][:200],
    })

    if result["exit_code"] != 0:
        return {"error_state": f"Command failed (exit {result['exit_code']}): {result['stderr'][:500]}"}

    return {"error_state": None, "invalidated_files": ["*"]}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No Python syntax checking | `ast.parse()` in-process | This phase | Catches Python syntax errors before commit |
| Sync subprocess in executor | `asyncio.create_subprocess_exec` | This phase | Event loop stays responsive during builds |
| Default SQLite journal mode | WAL mode | This phase | Concurrent readers + single writer without contention |
| Fixed 3-retry limit | Circuit breaker after 2 identical errors | This phase | Avoids wasting tokens on unfixable-by-retry errors |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | None (no pytest.ini or pyproject.toml section) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VALID-02 | Python syntax errors caught by ast.parse | unit | `python -m pytest tests/test_validator_node.py -x -k python` | Partially (test_validator_node.py exists, no .py tests yet) |
| VALID-03 | LSP fallback when unavailable, only new errors trigger rollback | unit | `python -m pytest tests/test_validator_node.py -x -k lsp` | Partially (LSP tests exist in test_lsp_client.py, not in validator tests) |
| VALID-04 | Circuit breaker skips/escalates after 2 identical errors | unit | `python -m pytest tests/test_graph.py -x -k circuit` | No (test_graph.py exists but no circuit breaker tests) |
| INFRA-01 | Executor uses async subprocess, validator uses async syntax checks | unit | `python -m pytest tests/test_shell_async.py tests/test_validator_node.py -x` | Partially (test_shell_async.py exists) |
| INFRA-02 | SQLite WAL mode enabled on init | unit | `python -m pytest tests/test_store.py -x -k wal` | No (test_store.py exists but no WAL test) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_validator_node.py` -- add Python syntax validation tests (valid .py, invalid .py with SyntaxError)
- [ ] `tests/test_validator_node.py` -- add LSP fallback tests (mock LSP unavailable, verify subprocess fallback)
- [ ] `tests/test_graph.py` -- add circuit breaker tests (repeated identical error -> skip/escalate)
- [ ] `tests/test_store.py` -- add WAL mode verification test (`PRAGMA journal_mode` returns 'wal')
- [ ] `tests/test_validator_node.py` -- add async syntax check tests (verify no blocking subprocess.run)

## Open Questions

1. **Circuit breaker: skip vs escalate?**
   - What we know: CONTEXT.md says "escalate model tier or skip step". The `ModelRouter` already has auto-escalation built in (e.g., `edit_simple` escalates from `general` to `reasoning`). The validator uses `fast` tier with escalation to `general`.
   - What's unclear: Should the circuit breaker escalate the LLM model tier for the RETRY (send to a smarter model to fix the error), or should it skip the step entirely? These are different actions.
   - Recommendation: Do BOTH in sequence: first attempt is normal retry (already handled), second identical error triggers model escalation (use `reasoning` tier for the retry edit), third identical error skips the step. This gives maximum chance of success. The `should_continue` routing can return a new target like `"escalated_reader"` that forces reasoning tier, or add an `escalation_requested` flag to state.

2. **Error message normalization for dedup**
   - What we know: Error messages from ast.parse, esbuild, and LSP all include line numbers and sometimes file paths that may shift between retries
   - What's unclear: How aggressively to normalize -- strip all numbers? Just line numbers?
   - Recommendation: Normalize by removing line/column numbers and absolute path prefixes. Keep the core error type and description. Use a simple regex: `re.sub(r'[Ll]ine \d+|col \d+|offset \d+', '', msg)` plus path stripping.

## Sources

### Primary (HIGH confidence)
- Python `ast` module documentation (stdlib) -- `ast.parse()` returns AST or raises `SyntaxError` with `lineno`, `offset`, `msg`, `text` attributes
- Python `asyncio` subprocess documentation (stdlib) -- `create_subprocess_exec` API
- SQLite WAL mode documentation -- `PRAGMA journal_mode=WAL` enables concurrent readers
- Codebase inspection of `agent/nodes/validator.py`, `agent/tools/shell.py`, `agent/nodes/executor.py`, `store/sqlite.py`, `agent/graph.py`

### Secondary (MEDIUM confidence)
- aiosqlite 0.22.1 supports PRAGMA execution (verified by `await self._db.execute("PRAGMA ...")` pattern already used in codebase for schema creation)

## Project Constraints (from CLAUDE.md)

- **LLM Provider:** OpenAI only (o3/gpt-4o/gpt-4o-mini)
- **Framework:** LangGraph 1.1.3 -- committed, not switching
- **Runtime:** Python 3.11
- **Naming:** `snake_case` for modules, `_prefix` for private helpers, `{name}_node` for graph nodes
- **Graph state:** Flat `TypedDict` (`AgentState`), nodes return partial dicts
- **Dependencies injected via:** `config["configurable"]` dict
- **Error handling:** `should_continue()` checks `error_state`, retries up to 3 times
- **Testing:** pytest + pytest-asyncio
- **Logging:** `TraceLogger.log(node_name, data_dict)` for agent nodes

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all stdlib or already-installed packages
- Architecture: HIGH - patterns are straightforward modifications to existing code
- Pitfalls: HIGH - well-understood failure modes with clear mitigations

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (30 days - stable domain, no moving targets)
