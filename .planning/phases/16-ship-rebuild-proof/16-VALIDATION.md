---
phase: 16
slug: ship-rebuild-proof
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python) + Playwright 1.58.2 (E2E) |
| **Config file** | `pyproject.toml` (pytest), `web/playwright.config.ts` (Playwright) |
| **Quick run command** | `python3 -m pytest tests/test_ship_smoke.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/test_ship_smoke.py tests/test_rebuild_pipeline.py -x -q && npx playwright test web/e2e/ship-rebuild.spec.ts` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_ship_smoke.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/test_ship_smoke.py tests/test_rebuild_pipeline.py -x -q && npx playwright test web/e2e/ship-rebuild.spec.ts`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | SHIP-01 | smoke | `python3 -m pytest tests/test_ship_smoke.py -x -q` | W0 | pending |
| 16-01-02 | 01 | 1 | SHIP-05 | integration | `python3 -m pytest tests/test_rebuild_pipeline.py -x -q` | W0 | pending |
| 16-02-01 | 02 | 1 | SHIP-04 | e2e | `npx playwright test web/e2e/ship-rebuild.spec.ts` | W0 | pending |
| 16-02-02 | 02 | 1 | SHIP-03 | e2e | `npx playwright test web/e2e/ship-rebuild.spec.ts --grep "renders"` | W0 | pending |
| 16-03-01 | 03 | 2 | SHIP-01, SHIP-02, SHIP-03 | smoke+e2e | `python3 -m pytest tests/test_ship_smoke.py --collect-only -q && npx playwright test web/e2e/ship-rebuild.spec.ts --list` | W0 | pending |
| 16-03-02 | 03 | 2 | SHIP-04, SHIP-05 | integration | `python3 -m pytest tests/test_rebuild_pipeline.py --collect-only -q` | W0 | pending |
| 16-04-01 | 04 | 3 | SHIP-01, SHIP-03 | execution | `test -d /tmp/ship-rebuilt && test -f /tmp/ship-rebuilt/package.json` | n/a | pending |
| 16-04-02 | 04 | 3 | SHIP-04 | deployment | `curl -s -o /dev/null -w "%{http_code}" https://${SHIP_DEPLOYED_URL}/health` | n/a | pending |
| 16-04-03 | 04 | 3 | SHIP-01, SHIP-02, SHIP-03, SHIP-04, SHIP-05 | full suite | `SHIP_BASE_URL=https://${SHIP_DEPLOYED_URL} python3 -m pytest tests/test_ship_smoke.py tests/test_rebuild_pipeline.py -x -q && SHIP_BASE_URL=https://${SHIP_DEPLOYED_URL} npx playwright test web/e2e/ship-rebuild.spec.ts` | n/a | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ship_smoke.py` — API smoke tests for rebuilt Ship routes (SHIP-01, SHIP-04)
- [ ] `tests/test_rebuild_pipeline.py` — Integration test for orchestration script (SHIP-05)
- [ ] `web/e2e/ship-rebuild.spec.ts` — Playwright E2E for core workflows (SHIP-02, SHIP-03)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual UI renders correctly | SHIP-03 | Screenshot comparison needed | Open rebuilt Ship URL in browser, verify layout matches original |
| Railway deploy provisions correct resources | SHIP-04 | Requires Railway account access | Check Railway dashboard for project, verify Postgres addon and env vars |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
