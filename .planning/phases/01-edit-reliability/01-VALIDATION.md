---
phase: 1
slug: edit-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `python -m pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `python -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | EDIT-01 | unit | `python -m pytest tests/test_file_ops.py -k fuzzy` | ❌ W0 | pending |
| 1-01-02 | 01 | 1 | EDIT-02 | unit | `python -m pytest tests/test_file_ops.py -k error_feedback` | ❌ W0 | pending |
| 1-01-03 | 01 | 1 | EDIT-03 | unit | `python -m pytest tests/test_file_ops.py -k indent` | ❌ W0 | pending |
| 1-01-04 | 01 | 1 | EDIT-04 | unit | `python -m pytest tests/test_file_ops.py -k freshness` | ❌ W0 | pending |
| 1-02-01 | 02 | 1 | VALID-01 | unit | `python -m pytest tests/test_validator.py -k error_context` | ❌ W0 | pending |
| 1-03-01 | 03 | 1 | INFRA-03 | unit | `python -m pytest tests/test_llm.py -k structured` | ❌ W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_file_ops.py` — stubs for EDIT-01 through EDIT-04 (fuzzy matching, error feedback, indent preservation, freshness)
- [ ] `tests/test_validator.py` — stubs for VALID-01 (error context in retries)
- [ ] `tests/test_llm.py` — stubs for INFRA-03 (structured outputs)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LLM returns valid structured output with o3 model | INFRA-03 | Requires live OpenAI API call | Run agent with o3 tier, verify no parse errors in trace |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
