# Phase 17: Persistent Loop Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 17-persistent-loop-infrastructure
**Areas discussed:** Progress granularity, Rebuild controls, Frontend panel design, Error handling

---

## Progress Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Per-task granular | Stream every task start/complete/fail, CI results per task, token usage per task. ~50+ events. | ✓ |
| Stage-level only | 5-6 high-level stages: cloning, analyzing, planning, executing, building, done. | |
| Both (layered) | Stage-level primary, per-task on expand. More frontend work. | |
| You decide | Claude picks balance based on EventBus patterns | |

**User's choice:** Per-task granular
**Notes:** Matches what DAGScheduler already emits internally

| Option | Description | Selected |
|--------|-------------|----------|
| New rebuild_* types | rebuild_started, rebuild_stage, rebuild_task_started, etc. Clean separation. | ✓ |
| Reuse existing types | Use run_started, node_started with rebuild flag. Less frontend changes. | |
| You decide | Claude picks based on EventBus patterns | |

**User's choice:** New rebuild_* types
**Notes:** Clean separation from agent run events

---

## Rebuild Controls

| Option | Description | Selected |
|--------|-------------|----------|
| Cancel only | Simple, matches existing cancel pattern | |
| Cancel + retry | Cancel plus re-trigger from scratch | |
| Cancel + retry + history | Cancel, retry, and view past rebuilds with results/metrics | ✓ |
| You decide | Claude picks minimal viable set | |

**User's choice:** Cancel + retry + history
**Notes:** Needs a rebuilds table in SQLite

| Option | Description | Selected |
|--------|-------------|----------|
| One at a time | Reject new rebuild if one running. Matches single-process constraint. | ✓ |
| Allow concurrent | Multiple rebuilds with different configs | |

**User's choice:** One at a time

---

## Frontend Panel Design

| Option | Description | Selected |
|--------|-------------|----------|
| Replace agent panel | Right-side panel switches to rebuild progress when active | ✓ |
| Dedicated route/page | New /rebuild page separate from IDE | |
| Tab in agent panel | 'Rebuild' tab alongside agent activity stream | |
| You decide | Claude picks based on layout | |

**User's choice:** Replace agent panel

| Option | Description | Selected |
|--------|-------------|----------|
| TopBar button | "Rebuild Ship" button in TopBar, always visible | ✓ |
| Menu/dropdown | Add to project actions dropdown | |
| Instruction input | Type 'rebuild ship' in instruction input | |
| You decide | Claude picks what fits TopBar | |

**User's choice:** TopBar button

---

## Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Show error + retry button | Display what failed and offer retry | |
| Show error + detailed log | Same plus full task-level log leading up to failure | ✓ |
| You decide | Claude picks right error display | |

**User's choice:** Show error + detailed log

| Option | Description | Selected |
|--------|-------------|----------|
| Keep output | Leave partial output for debugging | ✓ |
| Clean up | Delete output directory on failure | |
| You decide | Claude picks based on debugging value | |

**User's choice:** Keep output

---

## Claude's Discretion

- Event priority levels for rebuild events
- Exact rebuild_* event data payloads
- SQLite schema for rebuilds table
- Server shutdown handling during active rebuild

## Deferred Ideas

None
