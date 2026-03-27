# Phase 2: Validation & Infrastructure - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Validator catches real errors without false positives, and infrastructure does not block the event loop or cause data contention. This phase adds Python syntax validation (py_compile), hardens LSP diagnostic diffing with graceful fallback, implements circuit breaker for repeated failures, converts synchronous subprocess calls to async, and enables SQLite WAL mode.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from research:
- Python syntax checking via py_compile or ast.parse
- LSP diffing must gracefully fall back to subprocess checks when unavailable
- Circuit breaker: after 2 identical errors, escalate model tier or skip step
- Async subprocesses: use asyncio.create_subprocess_exec instead of subprocess.run
- SQLite WAL mode: set on connection open via PRAGMA journal_mode=WAL

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/nodes/validator.py` — validator with 3-tier validation (LSP, subprocess, pass-through) and rollback
- `agent/tools/shell.py` — shell execution (currently synchronous subprocess.run calls)
- `agent/tools/lsp_client.py` — LSP protocol client
- `agent/tools/lsp_manager.py` — LSP server lifecycle management
- `store/sqlite.py` — SQLiteSessionStore with aiosqlite
- `agent/graph.py` — should_continue() retry logic

### Established Patterns
- Validator returns partial AgentState dict with error_state and last_validation_error
- LSP validation uses baseline diffing (baseline vs post-edit diagnostics)
- Phase 1 added: structured error outputs (last_validation_error dict), fuzzy matching, content hashing

### Integration Points
- validator_node checks file extensions to route validation (TS/JS -> esbuild, JSON -> json.loads, YAML -> yaml.safe_load)
- shell.py run_command() used by executor_node for shell commands
- SQLiteSessionStore.__init__ opens DB connection — WAL pragma goes here
- should_continue() in graph.py reads error_state for retry decisions

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
