---
phase: 14
slug: observability-contract-maturity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0 + pytest-asyncio >=0.24.0 |
| **Config file** | pyproject.toml (test section) |
| **Quick run command** | `python -m pytest tests/test_contracts.py tests/test_tracing.py tests/test_scheduler.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_contracts.py tests/test_tracing.py tests/test_scheduler.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | OBSV-01 | unit | `python -m pytest tests/test_tracing.py -x -q` | Exists (extend) | ⬜ pending |
| 14-01-02 | 01 | 1 | OBSV-01 | unit | `python -m pytest tests/test_tracing.py -x -q` | Exists (extend) | ⬜ pending |
| 14-02-01 | 02 | 1 | OBSV-02 | unit | `python -m pytest tests/test_scheduler.py -x -q` | Exists (extend) | ⬜ pending |
| 14-02-02 | 02 | 1 | OBSV-02 | integration | `python -m pytest tests/test_event_streaming_integration.py -x -q` | Exists (extend) | ⬜ pending |
| 14-03-01 | 03 | 1 | OBSV-03 | unit | `python -m pytest tests/test_observability.py -x -q` | ❌ W0 | ⬜ pending |
| 14-03-02 | 03 | 1 | OBSV-03 | unit | `python -m pytest tests/test_observability.py -x -q` | ❌ W0 | ⬜ pending |
| 14-04-01 | 04 | 1 | CNTR-03 | unit | `python -m pytest tests/test_contracts.py -x -q` | Exists (extend) | ⬜ pending |
| 14-04-02 | 04 | 1 | CNTR-03 | unit | `python -m pytest tests/test_contracts.py -x -q` | Exists (extend) | ⬜ pending |
| 14-04-03 | 04 | 1 | CNTR-03 | unit | `python -m pytest tests/test_contracts.py -x -q` | Exists (extend) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_observability.py` — stubs for OBSV-03 (decision traces + heatmap aggregation)
- [ ] Extend `tests/test_tracing.py` — agent_id/task_id/severity test cases for OBSV-01
- [ ] Extend `tests/test_contracts.py` — backward compatibility and migration doc tests for CNTR-03
- [ ] Extend `tests/test_scheduler.py` — progress_update event emission tests for OBSV-02

*Existing infrastructure covers framework installation — pytest already configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ProgressHeader renders in AgentPanel | OBSV-02 | Visual UI component | Open agent panel, run a DAG, verify collapsible progress bar appears |
| FailureHeatmap renders correctly | OBSV-03 | Visual UI component | Trigger task failures, verify heatmap grid shows module x error type |
| DecisionTrace expandable view | OBSV-03 | Visual UI component | Click failed task in activity stream, verify trace details expand |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
