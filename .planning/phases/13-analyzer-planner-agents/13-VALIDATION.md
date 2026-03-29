---
phase: 13
slug: analyzer-planner-agents
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing) |
| **Config file** | pyproject.toml |
| **Quick run command** | `python3 -m pytest tests/test_analyzer.py tests/test_planner_v2.py -q --tb=short` |
| **Full suite command** | `python3 -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command (analyzer + planner tests)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | ANLZ-01 | unit | `python3 -m pytest tests/test_analyzer.py -q` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | ANLZ-02 | unit | `python3 -m pytest tests/test_analyzer.py -q` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 2 | PLAN-01, PLAN-02 | unit | `python3 -m pytest tests/test_planner_v2.py -q` | ❌ W0 | ⬜ pending |
| 13-02-02 | 02 | 2 | PLAN-03 | unit | `python3 -m pytest tests/test_planner_v2.py -q` | ❌ W0 | ⬜ pending |
| 13-03-01 | 03 | 3 | PLAN-04 | unit | `python3 -m pytest tests/test_plan_validator.py -q` | ❌ W0 | ⬜ pending |
| 13-03-02 | 03 | 3 | ANLZ-01, PLAN-03 | integration | `python3 -m pytest tests/test_analyzer_planner_integration.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analyzer.py` — stubs for ANLZ-01, ANLZ-02
- [ ] `tests/test_planner_v2.py` — stubs for PLAN-01, PLAN-02, PLAN-03
- [ ] `tests/test_plan_validator.py` — stubs for PLAN-04
- [ ] `tests/test_analyzer_planner_integration.py` — end-to-end fixture test
- [ ] `tests/fixtures/ship_sample/` — minimal Ship-like fixture (5-10 files)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Module map covers all directories | ANLZ-01 | Requires human review of completeness | Run analyzer on fixture, review module-map.json |
| PRD quality assessment | PLAN-01 | Subjective quality check | Read generated PRD, verify it captures module responsibilities |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
