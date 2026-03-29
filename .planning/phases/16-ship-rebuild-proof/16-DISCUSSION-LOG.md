# Phase 16: Ship Rebuild Proof - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 16-ship-rebuild-proof
**Areas discussed:** Target scope, Execution strategy, Deployment pipeline, Validation approach

---

## Target Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Core workflows only | Focus on critical user journeys — auth, CRUD, navigation | ✓ |
| All 47 API routes | Full coverage of every endpoint | |
| Vertical slice | Pick one complete feature and rebuild it perfectly | |

**User's choice:** Core workflows only
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Local copy available | Ship codebase already on machine | |
| Clone from GitHub | Pipeline clones Ship from GitHub repo URL | ✓ |
| Not sure yet | Need to figure out access | |

**User's choice:** Clone from GitHub
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Auth + CRUD + Nav | Specific preset of core journeys | |
| Whatever the pipeline discovers | Let analyzer determine highest-impact routes | ✓ |
| I'll specify routes | User provides specific route list | |

**User's choice:** Whatever the pipeline discovers
**Notes:** None

---

## Execution Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Analyze-then-execute | Full pipeline: clone → analyze → plan DAG → execute | ✓ |
| Incremental modules | Break Ship into modules manually, feed separately | |
| Scaffold first | Generate scaffolding first, then fill in implementations | |

**User's choice:** Analyze-then-execute
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Retry with smaller scope | Auto-narrow scope on failure | |
| Human intervention | Stop and report for manual decision | |
| Claude decides | Trust the pipeline's failure classification + retry engine | ✓ |

**User's choice:** Claude decides
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh repo | New empty git repo, clean slate | ✓ |
| Fork of Ship | Fork original and modify in-place | |
| Subdirectory here | Build inside Shipyard project | |

**User's choice:** Fresh repo
**Notes:** None

---

## Deployment Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Railway | Simple CLI deploy, auto-HTTPS | ✓ |
| Heroku | Classic PaaS, Procfile-based | |
| Vercel/Netlify | For frontend/JAMstack apps | |
| Claude decides | Pick based on Ship's tech stack | |

**User's choice:** Railway
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Fully automated | Pipeline generates scripts, provisions, deploys, verifies | ✓ |
| Semi-automated | Pipeline generates config, user triggers deploy | |
| Manual deploy | Pipeline builds, user deploys | |

**User's choice:** Fully automated
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Railway env vars | Set through Railway CLI/API automatically | ✓ |
| Dotenv template | Generate .env.example, user fills in values | |
| Claude decides | Pipeline figures out config approach | |

**User's choice:** Railway env vars
**Notes:** None

---

## Validation Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Automated E2E tests | Playwright/Cypress E2E against deployed URL | |
| API smoke tests | Hit routes, verify status codes and response shapes | |
| Both E2E + API | API for route coverage, E2E for workflow coverage | ✓ |

**User's choice:** Both E2E + API
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Green CI + live URL | Tests pass and app is clickable in browser | ✓ |
| Live URL walkthrough | Screen recording of navigating rebuilt Ship | |
| Pipeline replay | Demo shows the pipeline journey, not just output | |

**User's choice:** Green CI + live URL
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Core pass = ship it | Auth+CRUD+nav work = pass. Non-critical failures OK | ✓ |
| Strict: all must pass | Every rebuilt route must pass | |
| 80% threshold | At least 80% of routes must pass | |

**User's choice:** Core pass = ship it
**Notes:** None

## Claude's Discretion

- Which specific Ship routes to prioritize (analyzer decides)
- E2E test framework details
- Railway project configuration
- Ship tech stack dependency handling

## Deferred Ideas

None — discussion stayed within phase scope
