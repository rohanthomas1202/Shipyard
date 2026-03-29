---
phase: 15
slug: execution-engine-ci-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python), tsc --noEmit (TypeScript) |
| **Config file** | `pyproject.toml` (pytest section) |
| **Quick run command** | `python3 -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python3 -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `python3 -m pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | EXEC-01 | unit | `python3 -m pytest tests/test_branch_manager.py -x -q` | ❌ W0 | ⬜ pending |
| 15-02-01 | 02 | 1 | VALD-01,VALD-02,VALD-03 | unit | `python3 -m pytest tests/test_ci_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 15-03-01 | 03 | 1 | ORCH-03,VALD-02 | unit | `python3 -m pytest tests/test_failure_classifier.py -x -q` | ❌ W0 | ⬜ pending |
| 15-04-01 | 04 | 2 | EXEC-02,EXEC-04 | unit | `python3 -m pytest tests/test_context_packs.py -x -q` | ❌ W0 | ⬜ pending |
| 15-05-01 | 05 | 2 | ORCH-03,ORCH-04,EXEC-01,EXEC-03 | integration | `python3 -m pytest tests/test_execution_engine.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_branch_manager.py` — stubs for branch create/checkout/merge/cleanup
- [ ] `tests/test_ci_runner.py` — stubs for pipeline stage execution and reporting
- [ ] `tests/test_failure_classifier.py` — stubs for rule-based and LLM classification
- [ ] `tests/test_context_packs.py` — stubs for context assembly and ownership validation
- [ ] `tests/test_execution_engine.py` — stubs for end-to-end execution with branch isolation

*All test files are new — TDD tasks will create them.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Concurrent git operations don't corrupt repo | EXEC-01 | Race conditions require real parallel execution | Run 5+ agents in parallel on a test repo, verify no git corruption |
| Idempotent re-run after failure | EXEC-03 | Requires stateful failure + retry sequence | Fail a task mid-execution, re-run, verify same result |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
