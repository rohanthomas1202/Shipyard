---
phase: 8
slug: foundation-layout-state-architecture-topbar
status: draft
nyquist_compliant: true
wave_0_complete: true
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

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 08-01-01 | 01 | 1 | LAYOUT-05 | Build | `npx tsc --noEmit` | pending |
| 08-01-02 | 01 | 1 | LAYOUT-05 | Build | `npx tsc --noEmit` | pending |
| 08-02-01 | 02 | 2 | LAYOUT-01, LAYOUT-02, LAYOUT-03, LAYOUT-04 | Build | `npx tsc --noEmit` | pending |
| 08-02-02 | 02 | 2 | LAYOUT-01, LAYOUT-02, LAYOUT-03, LAYOUT-04 | Build + E2E | `npm run build && npx playwright test app.spec.ts` | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Justification

E2E test updates are embedded in Plan 02 Task 2 (the final task of the phase) rather than a separate Wave 0 task. This is acceptable because:

1. **Plan 01 (Wave 1)** creates Zustand stores and refactors WebSocketContext. These are internal state changes that do not alter the rendered DOM or break existing E2E tests. The existing `app.spec.ts` tests interact with the UI layer (AppShell), which is untouched in Plan 01.
2. **Plan 02 Task 1** creates new layout component files but does not wire them into App.tsx. The existing AppShell still renders, so existing E2E tests remain valid through Task 1.
3. **Plan 02 Task 2** is where `<IDELayout />` replaces `<AppShell />` in App.tsx AND where E2E tests are updated simultaneously. Both changes happen in the same task, ensuring tests always match the rendered UI.
4. No task leaves the E2E suite in a broken state between commits.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drag resize feels smooth | LAYOUT-02 | Subjective UX quality | Drag panel borders, verify no jank at 60fps |
| Layout persists reload | LAYOUT-02 | Requires visual confirmation | Resize panels, reload page, verify sizes match |
| Collapse/expand animation | LAYOUT-03 | Animation smoothness | Click collapse button, verify smooth transition |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 addressed (justified inline — no separate Wave 0 task needed)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
