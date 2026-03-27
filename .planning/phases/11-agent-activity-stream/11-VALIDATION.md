---
phase: 11
slug: agent-activity-stream
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright 1.58.2 |
| **Config file** | `web/playwright.config.ts` |
| **Quick run command** | `cd web && npm run build` |
| **Full suite command** | `cd web && npx playwright test` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd web && npm run build`
- **After every plan wave:** Run `cd web && npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | STREAM-01 | e2e | `cd web && npx playwright test e2e/activity-stream.spec.ts --grep "timeline"` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | STREAM-02 | e2e | `cd web && npx playwright test e2e/activity-stream.spec.ts --grep "scroll"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `web/e2e/activity-stream.spec.ts` — stubs for STREAM-01 and STREAM-02
- [ ] Update existing `web/e2e/app.spec.ts` — AgentPanel body changes

*Existing infrastructure covers test framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Smooth scroll animation feels natural | STREAM-02 | Visual quality subjective | Trigger 10+ rapid events, verify scroll is smooth not janky |
| Glassmorphic card styling matches design system | STREAM-01 | Visual fidelity | Compare rendered cards against UI-SPEC color/spacing tokens |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
