---
phase: 8
slug: foundation-layout-state-architecture-topbar
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (E2E) + TypeScript build check (vitest not in project) |
| **Config file** | `web/playwright.config.ts` |
| **Quick run command** | `cd web && npx tsc --noEmit` |
| **Full suite command** | `cd web && npx playwright test` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd web && npx tsc --noEmit`
- **After every plan wave:** Run `cd web && npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | LAYOUT-01 | E2E | `npx playwright test app.spec.ts` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | LAYOUT-02 | E2E | `npx playwright test app.spec.ts` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | LAYOUT-03 | E2E | `npx playwright test app.spec.ts` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | LAYOUT-04 | E2E | `npx playwright test app.spec.ts` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 2 | LAYOUT-05 | E2E + perf | `npx playwright test app.spec.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `web/e2e/app.spec.ts` — update existing E2E tests for new IDE layout (14 existing tests will break)
- [ ] Playwright installed (already in devDependencies)

*Existing infrastructure covers framework needs. E2E test content must be updated for new UI.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drag resize feels smooth | LAYOUT-02 | Subjective UX quality | Drag panel borders, verify no jank at 60fps |
| Layout persists reload | LAYOUT-02 | Requires visual confirmation | Resize panels, reload page, verify sizes match |
| Collapse/expand animation | LAYOUT-03 | Animation smoothness | Click collapse button, verify smooth transition |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
