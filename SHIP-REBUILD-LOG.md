# Ship Rebuild Log

This document tracks every instruction sent to the Shipyard agent during the
Ship app rebuild, along with every human intervention required.  It serves as
both a project diary and a deliverable that feeds into the comparative analysis
and CODEAGENT.md.

---

## Overview

| Field                | Value |
|----------------------|-------|
| Start Date           | —     |
| End Date             | —     |
| Total Instructions   | 0     |
| Successful (1st try) | 0     |
| Success Rate         | —     |
| Total Interventions  | 0     |

---

## Instructions Log

| # | Instruction | Status | Duration | Intervention? | Notes |
|---|-------------|--------|----------|---------------|-------|
| 1 | Add status field to Document | error | 0s | Yes |  |
| 2 | Add GET /ready health endpoint | error | 0s | Yes |  |
| 3 | Add documents CRUD routes | error | 0s | Yes |  |
| 4 | Add tags field and filter | error | 0s | Yes |  |
| 5 | Parallel: priority field + DELETE endpoint | error | 0s | Yes |  |
| 1 | Add status field to Document | error | 4s | Yes |  |
| 2 | Add GET /ready health endpoint | error | 3s | Yes |  |
| 3 | Add documents CRUD routes | error | 3s | Yes |  |
| 4 | Add tags field and filter | error | 3s | Yes |  |
| 5 | Parallel: priority field + DELETE endpoint | error | 3s | Yes |  |
| 1 | Add status field to Document | error | 4s | Yes |  |
| 2 | Add GET /ready health endpoint | error | 3s | Yes |  |
| 3 | Add documents CRUD routes | error | 3s | Yes |  |
| 4 | Add tags field and filter | error | 3s | Yes |  |
| 5 | Parallel: priority field + DELETE endpoint | error | 3s | Yes |  |
| 1 | Add status field to Document | completed | 19s | No |  |
| 2 | Add GET /ready health endpoint | completed | 33s | No |  |
| 3 | Add documents CRUD routes | completed | 33s | No |  |
| 4 | Add tags field and filter | failed | 188s | Yes |  |
| 5 | Parallel: priority field + DELETE endpoint | completed | 46s | No |  |

---

## Interventions

Each intervention is numbered and linked back to its instruction.

### Intervention 1 (template)

- **Instruction #:** —
- **What Broke:** (agent error or incorrect behavior observed)
- **What Was Done Manually:** (human fix applied)
- **Root Cause:** (why the agent failed — anchor mismatch, wrong file, bad plan, etc.)
- **What It Reveals:** (agent limitation category — see below)
- **Time Spent:** —

---


### Intervention (Instruction 1)

- **Instruction #:** 1
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 2)

- **Instruction #:** 2
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 3)

- **Instruction #:** 3
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 4)

- **Instruction #:** 4
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 5)

- **Instruction #:** 5
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 1)

- **Instruction #:** 1
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 2)

- **Instruction #:** 2
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 3)

- **Instruction #:** 3
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 4)

- **Instruction #:** 4
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 5)

- **Instruction #:** 5
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 1)

- **Instruction #:** 1
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 2)

- **Instruction #:** 2
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 3)

- **Instruction #:** 3
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 4)

- **Instruction #:** 4
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 5)

- **Instruction #:** 5
- **What Broke:** error — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO


### Intervention (Instruction 4)

- **Instruction #:** 4
- **What Broke:** failed — see trace: N/A
- **What Was Done Manually:** TODO
- **Root Cause:** TODO
- **What It Reveals:** TODO
- **Time Spent:** TODO

## Agent Limitation Categories

Track recurring failure modes to quantify agent weaknesses.

| Category                  | Count | Example |
|---------------------------|-------|---------|
| Edit Precision            | 0     | —       |
| Context Understanding     | 0     | —       |
| Multi-File Coordination   | 0     | —       |
| Validation Gaps           | 0     | —       |
| Planning Quality          | 0     | —       |

### Category Definitions

- **Edit Precision** — Anchor mismatches, partial replacements, whitespace errors,
  edits applied to wrong location in file.
- **Context Understanding** — Agent misreads existing code, ignores imports or
  dependencies, misunderstands the codebase structure.
- **Multi-File Coordination** — Changes in one file break another, agent fails to
  update related files, import/export mismatches.
- **Validation Gaps** — Agent misses real errors, flags false positives, or
  validation passes but the code is still broken.
- **Planning Quality** — Plan steps are in wrong order, missing steps, overly
  broad instructions, or wrong decomposition of the task.

---

## Success Metrics

| Metric                              | Value |
|-------------------------------------|-------|
| First-attempt success rate          | —     |
| Average retries per instruction     | —     |
| Most common failure mode            | —     |
| Instructions requiring intervention | —     |
| Total human time spent              | —     |

---

## Lessons for CODEAGENT.md

_To be filled during and after the rebuild. Each lesson should note the
instruction that surfaced it and the specific agent behavior observed._

1. —
