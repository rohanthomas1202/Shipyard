---
phase: 02-validation-infrastructure
plan: 02
subsystem: validation
tags: [ast, python, lsp, fallback, syntax-check]

requires:
  - phase: 02-validation-infrastructure-01
    provides: "async _syntax_check, validator_node with LSP support, structured errors"
provides:
  - "Python syntax checking via ast.parse in _syntax_check"
  - "Hardened LSP fallback with 30s timeout wrapper and defensive error handling"
affects: [agent-core-features, ship-rebuild]

tech-stack:
  added: [ast]
  patterns: [asyncio.wait_for timeout wrapping, defensive try/except in LSP calls]

key-files:
  created: []
  modified:
    - agent/nodes/validator.py
    - tests/test_validator_node.py

key-decisions:
  - "Used encoding='utf-8' with errors='replace' for ast.parse to avoid encoding false negatives"
  - "30s timeout on _lsp_validate via asyncio.wait_for as outer safety net"
  - "Defensive try/except around each get_diagnostics call returns None to trigger syntax fallback"

patterns-established:
  - "Timeout wrapping: asyncio.wait_for around external service calls for safety"
  - "Graceful degradation: LSP errors fall back to syntax check, never crash"

requirements-completed: [VALID-02, VALID-03]

duration: 6min
completed: 2026-03-27
---

# Phase 02 Plan 02: Python Syntax Checking and LSP Fallback Hardening Summary

**Python syntax checking via ast.parse and bulletproof LSP fallback with timeout guard and defensive error handling**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-27T05:39:23Z
- **Completed:** 2026-03-27T05:45:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Python .py files are now syntax-checked via ast.parse with line/col error reporting
- LSP validation has a 30s asyncio.wait_for timeout wrapper preventing indefinite hangs
- LSP get_diagnostics calls are wrapped in defensive try/except, falling back to syntax check on any error
- 4 new tests covering Python syntax valid/invalid cases and LSP unavailable/timeout fallback

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Python syntax checking via ast.parse** - `2cfcc90` (feat)
2. **Task 2: Harden LSP fallback paths** - `e4f6f6b` (feat)

## Files Created/Modified
- `agent/nodes/validator.py` - Added ast.parse .py branch, asyncio.wait_for LSP timeout, defensive get_diagnostics wrapping
- `tests/test_validator_node.py` - Added 4 tests: python_syntax_valid, python_syntax_error, lsp_unavailable_falls_back, lsp_timeout_falls_back

## Decisions Made
- Used `encoding="utf-8", errors="replace"` for reading Python files to avoid encoding-related false negatives
- 30s timeout on _lsp_validate as outer safety net (inner timeouts exist in LspDiagnosticClient)
- Each get_diagnostics call wrapped individually so baseline failure still allows fallback

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Validator now covers Python, JSON, JS/JSX, TS/TSX, YAML syntax checking
- LSP fallback is bulletproof -- connection errors, timeouts, and crashes all gracefully degrade
- Ready for agent-core-features work that depends on reliable validation

---
*Phase: 02-validation-infrastructure*
*Completed: 2026-03-27*
