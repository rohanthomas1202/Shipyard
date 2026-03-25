# ast-grep + LSP Integration Design

**Date:** 2026-03-25
**Status:** Approved (pending review)
**Approach:** Layered Integration (Hybrid)

## Overview

Integrate ast-grep (structural code search/replace via tree-sitter) and Language Server Protocol (LSP) into Shipyard's edit pipeline to improve edit accuracy, validation depth, and codebase-wide refactoring.

**Core principle:** Every new capability degrades gracefully to the existing text-based path. The system is strictly additive — removing ast-grep-py or all LSP servers returns Shipyard to its current behavior with zero regressions.

### What This Solves

| Problem | Current State | With This Design |
|---|---|---|
| Edit accuracy | `str.replace()` on raw text — fragile anchors, false matches inside strings/comments, no indentation awareness | ast-grep structural matching validates anchors against AST boundaries, performs indentation-preserving replacements |
| Validation depth | Syntax-only checks (esbuild, node --check, json.load, yaml.safe_load) — misses type errors, broken imports, unused variables | LSP semantic diagnostics catch type errors, missing imports, and other language-specific issues |
| Refactoring at scale | Not supported — each edit targets a single anchor in a single file | ast-grep YAML rules execute structural patterns across entire directories |

### Architecture Summary

- **ast-grep** owns the **edit path**: structural anchor validation, AST-aware replacement, codebase-wide refactoring
- **LSP** owns the **validation path**: semantic diagnostics after edits, replacing subprocess syntax checks
- **Fallback at every layer**: unsupported language → text-based edit; no LSP server → subprocess validation

```
Editor flow:
  LLM → {"anchor", "replacement"}
      → ast_ops.validate_anchor()
          → structural_match: ast_ops.structural_replace() [pure function, returns old/new]
          → no match / unsupported: str.replace() via edit_file()
      → approval flow (supervised: wait for human; autonomous: auto-approve)
      → write to disk
      → validator (LSP diagnostics when available, subprocess fallback)

Refactor flow:
  Planner → {"type": "refactor", "pattern", "replacement", "language", "scope"}
      → refactor_node → ast_ops.apply_rule() [dry-run first]
      → batch approval (supervised: single approval for entire changeset)
      → write all files
      → LSP validation on all changed files
      → atomic rollback via batch_id if any file fails
```

---

## Section 1: ast-grep Edit Layer

**New file:** `agent/tools/ast_ops.py`

Dependencies: `ast-grep-py` (PyPI)

### 1a. Structural Anchor Validation

`validate_anchor(file_path: str, content: str, anchor: str) -> AnchorResult`

Parses the file with ast-grep and checks whether the anchor text maps to one or more complete AST nodes (not a partial expression, not inside a string literal or comment).

Returns one of:
- `structural_match: True` — anchor aligns with AST boundaries, safe for structural replace
- `structural_match: False, node_type: str` — anchor cuts across AST nodes; includes the node type for actionable retry feedback
- `unsupported_language` — no tree-sitter grammar available, skip validation

```python
@dataclass
class AnchorResult:
    structural_match: bool
    unsupported_language: bool = False
    node_type: str | None = None  # e.g. "function_declaration", "if_statement"
```

### 1b. Structural Replace (Pure Function)

`structural_replace(content: str, anchor: str, replacement: str, language: str) -> str`

**Critical design decision:** This is a **pure function** that returns the new file content as a string without writing to disk. The caller (editor_node) feeds `(content, new_content)` into the existing ApprovalManager flow as `(old_content, new_content)`. This preserves supervised mode correctness — `structural_replace()` never bypasses human approval gates.

Uses ast-grep's tree-sitter-aware engine to perform the replacement.

**Indentation post-processing:**
1. Detect indentation level of the original matched node
2. Re-indent the replacement to match
3. For multi-line replacements, use the first line's indentation as base and preserve relative indentation within the replacement

**Known limitation:** Indentation post-processing is deceptively hard for edge cases (nested replacements, Python's indentation-sensitive syntax, string literals with significant whitespace). Pre-implementation requirement: write 5-10 test cases covering:
- Nested class → method → body replacement (3+ indent levels)
- Python-specific: replacing a function body inside a class
- Replacement containing string literals with embedded newlines
- Multi-line replacement with mixed indentation (e.g., switch/case)
- Single-line replacement (should be trivial, verify no regression)

### 1c. Codebase-Wide Refactoring

`apply_rule(rule: dict, scope: str, dry_run: bool = True) -> list[RefactorResult]`

Accepts an ast-grep YAML rule (pattern + fix + language) and executes it across a directory scope.

```python
@dataclass
class RefactorResult:
    file_path: str
    old_content: str
    new_content: str
    match_count: int
```

Always runs as dry-run first. The caller (refactor_node) decides whether to apply based on mode (supervised vs autonomous).

### 1d. Parse Tree Cache

LRU cache keyed on `(file_path, content_hash)`:
- Avoids re-parsing on sequential edits to the same file (common: 5-10 edits to one file in a complex step)
- Cache is per-run, cleared at run end
- Configurable size: `ast_grep.cache_size` (default 64 entries)
- **Invalidation:** Cache entries are cleared for files modified by exec/test steps (see Section 7)

### 1e. Language Detection

`detect_languages(working_directory: str) -> dict[str, bool]`

**Synchronous function.** Called once at run start in `receive_node`. Scans file extensions in the working directory, probes ast-grep-py grammar support for each detected language via `ast_grep_py.SgRoot` (instantiation with a language string raises if grammar is unavailable — this is the probe mechanism). Populates `ast_available` in AgentState. No async required.

```python
# Example output
{
    "typescript": True,
    "python": True,
    "rust": True,
    "markdown": False,  # no grammar needed
    "custom_dsl": False  # unsupported
}
```

**Language fallback:** For files in languages where `ast_available[lang] == False`, all ast-grep features are skipped. The existing text-based path runs unchanged.

---

## Section 2: LSP Validation Layer

**New file:** `agent/tools/lsp_client.py`

No new dependencies — thin JSON-RPC implementation over `asyncio.subprocess`.

### Two-Layer Architecture

**Layer 1 — `LspConnection`:**
- Handles stdio transport and JSON-RPC framing (Content-Length headers, JSON serialization)
- Background `asyncio.Task` reads server stdout continuously, dispatches notifications to registered handlers
- **Separate background task for stderr** — drains stderr and pipes to `TraceLogger` at debug level. If stderr is not drained, OS pipe buffers fill and the server process blocks.
- Tracks `window/workDoneProgress` create/end pairs for readiness detection
- Exposes `is_ready: bool` flag — `True` after initial `workDoneProgress/end` received, or after `readiness_timeout` if server doesn't support progress notifications

**Layer 2 — `LspDiagnosticClient`:**
Single high-level interface:

```python
async def get_diagnostics(
    file_path: str,
    content: str,
    timeout: float | None = None
) -> list[Diagnostic]
```

Internally manages `didOpen`/`didChange`/`didClose`. Awaits server readiness on first call (with timeout). Returns collected diagnostics.

```python
async def notify_rollback(file_path: str, restored_content: str) -> None
```

Sends `didChange` with full restored content after a validator rollback. Prevents stale virtual document state in the LSP server.

### Capability Detection

After `initialize` handshake, inspects `serverCapabilities`:

| Capability | Behavior |
|---|---|
| `diagnosticProvider` present | Pull model: send `textDocument/diagnostic` request |
| `textDocumentSync` present, no `diagnosticProvider` | Push model: wait for `publishDiagnostics` notification |
| Neither | Mark server as "no diagnostic support", fall back to subprocess checks |

### Tiered Timeouts

| Scenario | Default | Rationale |
|---|---|---|
| First diagnostic after server start | 30s | Covers initial indexing |
| Incremental diagnostic after edit | 5s | Server is warm |
| Server readiness (workDoneProgress) | 60s | Large projects, rust-analyzer |

Configurable per-language in server registry (rust-analyzer gets longer defaults).

**First-timeout retry:** If the first diagnostic request times out, retry once with 2x timeout before marking the server as degraded. Prevents false degradation on large projects.

### Diagnostic Severity Mapping

| LSP Severity | Shipyard Behavior |
|---|---|
| Error (1) | Validation failure → triggers rollback |
| Warning (2) | Logged via TraceLogger, does not block |
| Information (3) | Ignored |
| Hint (4) | Ignored |

### Integration with validator_node

The `validator_node` return contract is unchanged — still returns `{"error_state": ...}` or `{"error_state": None}`. However, the function signature must change:

**Migration: sync → async.** The current `validator_node` is `def validator_node(state: dict) -> dict:` — a synchronous function with no `config` parameter. To access `lsp_manager` from `config["configurable"]` and call `await get_diagnostics()`, it must become:

```python
async def validator_node(state: dict, config: dict) -> dict:
```

**Implications:**
- LangGraph handles async node functions natively — no graph edge changes needed
- The existing `_syntax_check()` helper uses synchronous `subprocess.run`. Wrap in `asyncio.to_thread(_syntax_check, file_path)` to avoid blocking the event loop, or convert to `asyncio.create_subprocess_exec` for consistency
- This is a **Phase 3 change** (LSP integration). Phase 1 (ast-grep only) does not require this migration since `validate_anchor()` and `structural_replace()` are synchronous

**Updated flow:**
1. Get `lsp_manager` from `config["configurable"].get("lsp_manager")`
2. If `lsp_manager` exists and has a client for this language: call `await client.get_diagnostics()`, return errors
3. If no LSP client: fall back to `_syntax_check()` subprocess checks (wrapped in `asyncio.to_thread`)

---

## Section 3: LSP Server Lifecycle Manager

**New file:** `agent/tools/lsp_manager.py`

### Injection Pattern

**Not stored in AgentState.** `LspManager` is a graph-level dependency injected via `config["configurable"]["lsp_manager"]`, matching the existing `approval_manager` pattern. Subprocess handles are not serializable and would break LangGraph's state persistence.

### Server Registry

Hardcoded, extensible via configuration:

```python
REGISTRY = {
    "typescript": {
        "cmd": ["typescript-language-server", "--stdio"],
        "timeout_first": 10,
        "timeout_incremental": 5,
        "readiness_timeout": 15,
    },
    "python": {
        "cmd": ["pyright-langserver", "--stdio"],
        "fallback_cmd": ["pylsp"],
        "timeout_first": 20,
        "readiness_timeout": 30,
    },
    "rust": {
        "cmd": ["rust-analyzer"],
        "timeout_first": 45,
        "timeout_incremental": 10,
        "readiness_timeout": 120,
    },
    "go": {
        "cmd": ["gopls", "serve"],
        "timeout_first": 15,
    },
}
```

### Auto-Discovery

At run start, scans the project for file extensions, then for each detected language:
1. Check registry for preferred server binary
2. Probe `PATH` and project-local paths (`node_modules/.bin/`, `.venv/bin/`, `target/release/`)
3. If found → available. If not → that language uses subprocess fallback.

### Installation Responsibility

Shipyard does **not** install LSP servers. It discovers what's available in the project environment. For containerized/remote runs, the container image must include the relevant servers.

### Lifecycle: Async Context Manager

```python
class LspManager:
    async def __aenter__(self) -> "LspManager":
        """Detect languages, start available LSP servers, perform initialize handshake."""
        ...

    async def __aexit__(self, *exc) -> None:
        """Send shutdown/exit to all servers, kill subprocesses, cancel background tasks."""
        ...

    def get_client(self, language: str) -> LspDiagnosticClient | None:
        """Get an active diagnostic client for a language. Returns None if unavailable/degraded."""
        ...

    def server_status(self) -> dict[str, str]:
        """Returns {"typescript": "running", "python": "degraded", "rust": "unavailable"}"""
        ...
```

Used as a context manager wrapping the graph invocation. **Important:** This lives inside the `execute()` background coroutine (the `asyncio.create_task` target in `server/main.py` lines 157-195), NOT at the HTTP endpoint level. Placing it at the endpoint level would block the HTTP response until the entire graph run completes, defeating the fire-and-forget async task pattern.

```python
# Inside the execute() background coroutine in server/main.py
async def execute():
    try:
        async with LspManager(project_path, detected_languages, lsp_config) as lsp_mgr:
            result = await graph.ainvoke(state, config={
                "configurable": {
                    "lsp_manager": lsp_mgr,
                    "approval_manager": approval_mgr,
                    "router": router,
                    "store": store,
                }
            })
            # ... handle result ...
    except Exception as e:
        runs[run_id] = {"status": "error", "result": str(e)}
```

This guarantees cleanup even if the graph errors out before reaching `reporter_node`.

**Additional safety:** Signal handlers (`SIGINT`/`SIGTERM`) registered to schedule async cleanup on the running event loop. As a last resort, an `atexit` handler kills subprocess PIDs via `os.kill()` (note: `atexit` handlers are synchronous and cannot `await` — they are limited to forceful process termination). Background reader tasks per server run inside an `asyncio.TaskGroup` (Python 3.11+) — automatically cancelled on context exit.

### Server Crash Handling

If a server crashes mid-run:
1. Background reader task detects EOF on stdout
2. Server marked as "degraded" in `server_status()`
3. `get_client()` returns `None` for that language going forward
4. Subsequent validations fall back to subprocess checks
5. Logged via TraceLogger with server stderr output

No automatic restart. Restarts risk inconsistent state and are not worth the complexity for v1.

### Per-File Locking

`LspManager` maintains a `dict[str, asyncio.Lock]` keyed by file path. When parallel steps are active:
- Two editors modifying **different files** validate concurrently
- Two steps touching the **same file** (rare, given coordinator's directory grouping) have their `didOpen`/`didChange`/diagnostic cycles serialized

This prevents interleaved virtual document state in the LSP server.

---

## Section 4: Refactor Node

**New file:** `agent/nodes/refactor.py`

### Step Schema

The planner emits a step of type `refactor`:

```json
{
  "type": "refactor",
  "pattern": "oldFunc($ARG)",
  "replacement": "newFunc($ARG)",
  "language": "typescript",
  "scope": "web/src/"
}
```

### Planner Changes

**`agent/steps.py` modifications:**
- Update `PlanStep.kind` Literal type from `Literal["read", "edit", "exec", "test", "git"]` to include `"refactor"`
- Update `validate_kind` field_validator's `allowed` set to include `"refactor"` (currently raises `ValueError` for unknown kinds)
- Add optional fields to `PlanStep` for refactor metadata: `pattern: str | None`, `refactor_replacement: str | None`, `language: str | None`, `scope: str | None`

The planner system prompt (`agent/prompts/planner.py`) gets a new section:

> **When to emit `refactor` vs `edit`:**
> - `edit` — change specific code in 1-3 known files
> - `refactor` — apply a structural pattern across many files (rename symbol, migrate API, update import paths)
>
> Heuristic: if the instruction mentions "all files", "everywhere", "across the codebase", or names a pattern rather than a specific file location, emit a `refactor` step.

### Execution Flow

1. Build ast-grep rule from pattern/replacement/language
2. **Dry-run:** `ast_ops.apply_rule(rule, scope, dry_run=True)` → collect all matches
3. If 0 matches → return informational message, no error
4. **Approval:**
   - Supervised mode: surface full changeset as a batch via `approval_manager.propose_batch()`
   - Autonomous mode: proceed immediately
5. **Apply:** `ast_ops.apply_rule(rule, scope, dry_run=False)`
6. **Update file_buffer:** Refresh `file_buffer` entries for all changed files with post-refactor content
7. **Validate:** Run LSP diagnostics on all changed files
8. **Record:** All changes written to `edit_history` with `batch_id`

### Atomic Rollback via batch_id

All edits from a single refactor step share a `batch_id` (UUID). The `edit_history` entry format:

```python
{
    "file": str,
    "old": str,          # anchor text (for display)
    "new": str,          # replacement text (for display)
    "snapshot": str,     # FULL file content before edit (required for rollback)
    "batch_id": str,     # NEW: groups refactor edits
}
```

**Snapshot consistency note:** The current approval path in `editor.py` (lines 82-87, 96-101) does NOT save a full-file snapshot — it only stores `"old": anchor` (the anchor text, not the full content). The refactor node must store full-file snapshots independently by reading the file content before applying each edit. The `rollback_batch()` function depends on `entry["snapshot"]` being the complete original file content. As a Phase 2 prerequisite, the approval path should also be updated to store full-file snapshots for consistency.

New function in `file_ops.py`:

```python
def rollback_batch(edit_history: list[dict], batch_id: str) -> None:
    """Revert all files in a batch atomically."""
    batch_entries = [e for e in edit_history if e.get("batch_id") == batch_id]
    for entry in batch_entries:
        if "snapshot" not in entry:
            raise ValueError(f"Cannot rollback {entry['file']}: no snapshot stored")
        with open(entry["file"], "w") as f:
            f.write(entry["snapshot"])
```

If any file in the batch fails LSP validation, the entire batch rolls back.

### Batch Approval

New methods on `ApprovalManager`:

```python
async def propose_batch(self, run_id: str, records: list[EditRecord], batch_id: str) -> list[EditRecord]
async def approve_batch(self, batch_id: str, op_id: str) -> list[EditRecord]
```

Supervised mode: one human decision per refactor batch, not per-file.

### Serialization Constraint

**Refactor steps are never parallelized.** The coordinator filters steps with `kind == "refactor"` into `sequential_first`, never into `parallel_batches`. This eliminates multi-file deadlock risk (two refactors locking overlapping file sets in different orders). Parallel refactors can be revisited when there's a real use case.

### Scope Controls

Default exclusions: `node_modules/`, `.git/`, `__pycache__/`, `dist/`, `build/`, `.venv/`, `target/`. Planner-specified scope further restricts to a subdirectory. Refactor node never modifies files outside scope.

---

## Section 5: Graph Integration

**Modified file:** `agent/graph.py`

### Updated Graph Topology

```
planner → coordinator → classify → [reader → editor → validator] → advance → classify ...
                                 ↘ [refactor → validator] → advance → classify ...
                                 ↘ [executor] → advance → classify ...
                                 ↘ reporter (when all steps done)
```

**`classify_step` in `agent/graph.py`** — add routing for `kind == "refactor"`:
The current `classify_step` function (line 44-75) routes based on `step["kind"]`. It must add:
```python
if kind == "refactor":
    return "refactor"
```
And the conditional edges map must include `"refactor": "refactor"`.

**`coordinator_node` in `agent/nodes/coordinator.py`** — enforce sequential refactors:
The current coordinator operates on raw strings (`step_lower = step.lower()`) for directory-based grouping. It must be updated to:
1. Handle typed `PlanStep` dicts (check `isinstance(step, dict)` and read `step["kind"]`)
2. Filter steps with `kind == "refactor"` into `sequential_first`, never into `parallel_batches`
3. Preserve backward compatibility with string-based steps (existing fallback path)

**Graph construction** — register the new node:
```python
graph.add_node("refactor", refactor_node)
```
And add edges: `refactor → validator` (reuses existing validator path).

**Other integration points:**
- **LspManager** injected at graph construction (inside the `execute()` background task in `server/main.py`), not inside any node
- **receive_node** calls `detect_languages()` to populate `ast_available`

### State Additions to AgentState

```python
class AgentState(TypedDict):
    # ... existing fields ...
    ast_available: dict[str, bool]  # per-language ast-grep support flags
    invalidated_files: list[str]    # files modified by exec/test steps, cleared after reader re-reads
```

`LspManager` is **not** in state — it lives in `config["configurable"]["lsp_manager"]`.

---

## Section 6: Enhanced Editor Flow

**Modified file:** `agent/nodes/editor.py`

### Updated Flow

**File selection fix:** The current editor (line 23) does `file_path = list(file_buffer.keys())[0]` — always picking the first file. With typed `PlanStep` objects, the editor should use `step["target_files"][0]` when available, falling back to the first buffer key for legacy string steps. This ensures the correct file is edited when `file_buffer` contains multiple entries.

```
Determine file_path:
    → if step is dict with target_files: file_path = step["target_files"][0]
    → else: file_path = list(file_buffer.keys())[0]  [existing fallback]

LLM → parse {"anchor", "replacement"}
    → ast_ops.validate_anchor(file_path, content, anchor)
        → structural_match:
            new_content = ast_ops.structural_replace(content, anchor, replacement, language)
            [pure function, returns string — does NOT write to disk]
        → not structural / unsupported:
            new_content = content.replace(anchor, replacement, 1)
            [existing path]
    → approval flow:
        → approval_manager present + supervised: propose_edit() → wait for human
        → approval_manager present + autonomous: propose_edit() → auto-approve → apply
        → no approval_manager: apply directly (legacy path)
    → write to disk
    → validator_node (LSP-powered when available, subprocess fallback)
```

The editor prompt (`agent/prompts/editor.py`) is **unchanged**. The LLM still outputs `{"anchor": "...", "replacement": "..."}`. The ast-grep layer is transparent to the LLM.

### Enhanced Retry Messages

| Scenario | Retry Message |
|---|---|
| `structural_match: False` | "Anchor cuts across AST node boundaries at `{node_type}`. Expand anchor to include the full statement/expression/block." |
| `structural_match: True` but LSP validation fails | "Edit applied but produced errors: `{diagnostic_messages}`. Fix: `{specific error details at line N}`." |
| Anchor not found (existing) | "Anchor not found in `{file_path}`." (unchanged) |
| Anchor not unique (existing) | "Anchor not unique in `{file_path}` (found {count} occurrences)." (unchanged) |

LSP diagnostics in retry context give the LLM actionable, specific error information (e.g., "Type 'string' is not assignable to type 'number' at line 42") instead of generic syntax error output.

---

## Section 7: Cache & Buffer Invalidation

**Modified files:** `agent/nodes/executor.py`, `agent/tools/ast_ops.py`

### Problem

The executor runs shell commands (formatters, code generators, build scripts) that can modify files on disk. After execution, `file_buffer` and the ast-grep parse tree cache may hold stale content. A subsequent edit step working from stale content produces incorrect results.

### Solution

After `executor_node` and test steps return successfully:

1. **Invalidate file_buffer:** Clear entries for files in the step's target scope. The next reader node re-reads from disk.
2. **Clear parse tree cache:** Remove entries for affected files from the LRU cache.

Implementation: `executor_node` returns a new state field `invalidated_files: list[str]` listing files that may have changed. Downstream nodes check this before using cached data.

For refactor steps: `refactor_node` updates `file_buffer` with post-refactor content for all changed files before returning. No invalidation needed — the buffer is authoritative.

---

## Section 8: Observability

Beyond TraceLogger node-boundary logging:

### Per-Server Health

`LspManager.server_status()` returns a dict of server states. Logged at:
- Run start (after auto-discovery)
- Any state transition (running → degraded)
- Run end (final status)

### Diagnostic Latency

Each `get_diagnostics()` call records wall-clock time. Aggregated per-language at run end:
- `avg_diagnostic_ms`
- `max_diagnostic_ms`
- `timeout_count`

Useful for tuning timeout configuration.

### ast-grep Match Statistics

Per-run counters in `ast_ops`:
- `structural_matches` — anchors that aligned with AST boundaries
- `fallbacks_to_text` — anchors that didn't match structurally, fell back to str.replace()
- `unsupported_language_skips` — files in unsupported languages
- `cache_hits` / `cache_misses` — parse tree cache performance

### Refactor Scope Metrics

`refactor_node` logs:
- `files_scanned` — total files in scope
- `files_matched` — files with pattern matches
- `files_changed` — files actually modified
- `batch_id` — for tracing rollbacks

All metrics flow through `TraceLogger` (and LangSmith when configured). No new observability infrastructure.

---

## Section 9: Failure Modes & Fallbacks

| Scenario | Fallback |
|---|---|
| ast-grep-py not installed | All edits use `str.replace()`, refactor steps error with actionable message |
| Language has no tree-sitter grammar | `validate_anchor()` returns `unsupported_language`, skip to text replace |
| No LSP server found for language | `validator_node` uses current subprocess syntax checks |
| LSP server crashes mid-run | Manager marks language degraded, falls back to subprocess checks |
| LSP diagnostics timeout (first) | Retry once with 2x timeout, then mark degraded |
| LSP diagnostics timeout (incremental) | Treat as "no diagnostics", log warning, don't block |
| LSP server doesn't support diagnostics | Detected at init via capability check, fall back to subprocess |
| Refactor dry-run finds 0 matches | Informational message, no error |
| ast-grep structural_replace fails | Fall back to `str.replace()` + log reason |
| Parallel steps touch same file | Per-file asyncio.Lock serializes LSP interactions |
| Graph errors before reporter_node | `async with LspManager` context manager guarantees server cleanup |
| Refactor validation fails on any file | Entire batch rolled back atomically via `batch_id` |
| Exec step modifies files on disk | `file_buffer` and parse tree cache invalidated for affected files |
| LSP rollback without document sync | `notify_rollback()` sends `didChange` with restored content |

---

## Section 10: Dependencies & Configuration

### New Python Dependencies

- `ast-grep-py` — ast-grep Python bindings (PyPI, ~5MB)
- No new deps for LSP client — thin JSON-RPC over `asyncio.subprocess`

### Configuration (shipyard.toml / project settings)

```toml
[ast_grep]
enabled = true
cache_size = 64  # LRU parse tree cache entries

[lsp]
enabled = true
timeout_first = 30        # seconds, first diagnostic after server start
timeout_incremental = 5   # seconds, subsequent edits
readiness_timeout = 60    # seconds, wait for server readiness (workDoneProgress)

[lsp.servers.typescript]
cmd = ["typescript-language-server", "--stdio"]
timeout_first = 10

[lsp.servers.python]
cmd = ["pyright-langserver", "--stdio"]
fallback_cmd = ["pylsp"]

[lsp.servers.rust]
cmd = ["rust-analyzer"]
timeout_first = 45
readiness_timeout = 120

[lsp.servers.go]
cmd = ["gopls", "serve"]
```

### External Requirements

LSP servers must be installed in the user's environment. Shipyard discovers what's available but does not install anything. For containerized runs, include required servers in the container image.

---

## Section 11: Testing Strategy

### Phase 1 Tests (ast-grep)

**Pre-implementation:** 5-10 indentation test cases as acceptance criteria for `structural_replace()`:
1. Single-line replacement in a function body
2. Multi-line replacement at top level (0 indent)
3. Nested replacement: method body inside class inside module (3+ levels)
4. Python-specific: replacing an indented function body
5. Replacement containing string literals with embedded newlines
6. Multi-line replacement with mixed indentation (switch/case)
7. Replacement that adds/removes indent levels
8. Empty replacement (deletion)

**Unit tests for `ast_ops.py`:**
- `validate_anchor()` with structural match, partial match, string literal match, unsupported language
- `structural_replace()` correctness against each indentation test case
- `detect_languages()` with known and unknown extensions
- Parse tree cache: hit/miss/invalidation behavior

**Integration tests:**
- Full editor flow: LLM output → validate → replace → approval → validate
- Fallback path: unsupported language → text-based edit (no regression)

### Phase 2 Tests (Refactor)

- `apply_rule()` dry-run: correct match count, no files modified
- `apply_rule()` apply: files modified, snapshots stored
- `rollback_batch()`: all files reverted atomically
- Coordinator: refactor steps in sequential_first, never parallel
- Planner: LLM reliably distinguishes edit vs refactor steps

### Phase 3 Tests (LSP)

**Integration test (critical):** Start a real `typescript-language-server`, open a file with a known type error, verify the diagnostic comes back through `get_diagnostics()`. This single test will flush out ~80% of protocol issues.

- `LspConnection`: JSON-RPC framing, Content-Length parsing, notification dispatch
- `LspDiagnosticClient`: capability detection (push vs pull), timeout handling, rollback document sync
- `LspManager`: server discovery, startup, crash detection, degradation
- `validator_node` async migration: same results as sync path for subprocess fallback

### Phase 4 Tests

- Multi-language LSP: Python, Rust, Go servers produce diagnostics
- Parallel step file locking: concurrent edits to different files succeed; same-file edits serialize
- Observability: metrics are logged at run end

---

## Section 12: Rollout Plan

| Phase | Scope | Risk | Deliverable | Includes |
|---|---|---|---|---|
| **Phase 1** | ast-grep edit layer + editor integration | Low | Better edit accuracy, actionable retry messages | Sections 1a-1e, 6, 7. RC1 (pure-function structural_replace), RC5 (language detection), RC6 (cache invalidation). Pre-req: 5-10 indentation test cases. |
| **Phase 2** | Refactor node + planner changes + batch rollback | Medium | Codebase-wide refactoring capability | Sections 1c, 4, 5 (graph edges). RC3 (refactors always sequential). Batch approval on ApprovalManager. |
| **Phase 3** | LSP client + lifecycle manager — **TypeScript only** | High | LSP validation for TS/JS files | Sections 2, 3. RC2 (rollback document sync), RC4 (readiness tracking). Stderr piping. Integration test: start real server, open file with type error, verify diagnostic. |
| **Phase 4** | Expand LSP to Python, Rust, Go + full observability | Medium | Full multi-language LSP support | Section 3 (registry expansion), Section 8 (all metrics). Parallel step file locking. |

Phase 1 delivers immediate value with zero operational complexity. Phase 3 is scoped to one LSP server to contain blast radius while protocol edge cases are discovered.

---

## New Files Summary

| File | Purpose |
|---|---|
| `agent/tools/ast_ops.py` | ast-grep wrapper: validate_anchor, structural_replace, apply_rule, detect_languages, parse cache |
| `agent/tools/lsp_client.py` | Two-layer LSP client: LspConnection (transport) + LspDiagnosticClient (diagnostics) |
| `agent/tools/lsp_manager.py` | LSP server lifecycle: registry, auto-discovery, context manager, per-file locking |
| `agent/nodes/refactor.py` | Codebase-wide refactoring: dry-run, batch approval, atomic rollback |

## Modified Files Summary

| File | Changes |
|---|---|
| `agent/nodes/editor.py` | Add ast-grep validate/replace before approval flow; use step target_files for file selection |
| `agent/nodes/validator.py` | **Migrate to async** (Phase 3); add config param; use LSP diagnostics when available; add notify_rollback; wrap _syntax_check in asyncio.to_thread |
| `agent/nodes/coordinator.py` | Handle typed PlanStep dicts (not just strings); route refactor steps to sequential_first |
| `agent/nodes/receive.py` | Call detect_languages() at run start |
| `agent/nodes/executor.py` | Return invalidated_files for cache busting |
| `agent/nodes/reporter.py` | Log final observability metrics |
| `agent/graph.py` | Add refactor_node; add `"refactor"` to classify_step routing and conditional edges map |
| `agent/state.py` | Add ast_available and invalidated_files fields |
| `agent/steps.py` | Add `"refactor"` to PlanStep.kind Literal and validate_kind allowed set; add optional refactor fields (pattern, refactor_replacement, language, scope) |
| `agent/tools/file_ops.py` | Add rollback_batch() function |
| `agent/prompts/planner.py` | Add refactor step type documentation and heuristics |
| `agent/approval.py` | Add propose_batch() and approve_batch() methods for batch refactor approval |
| `store/models.py` | Add batch_id field to EditRecord |
| `server/main.py` | Wrap graph.ainvoke inside LspManager context manager in execute() background coroutine |
