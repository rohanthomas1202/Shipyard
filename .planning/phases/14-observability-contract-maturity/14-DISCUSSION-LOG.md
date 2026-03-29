# Phase 14: Observability + Contract Maturity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 14-observability-contract-maturity
**Areas discussed:** Structured logging format, Progress metrics view, Decision traces & failure heatmap, Contract compatibility checks
**Mode:** batch

---

## Structured Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Extend TraceLogger (Recommended) | Add unified format to existing file-based JSON TraceLogger. No new dependencies. | ✓ |
| EventBus-based logging | All logs through EventBus as P1/P2 events. Persisted via event store. | |
| New logging layer | Separate structured logging with own SQLite tables. | |

**User's choice:** Extend TraceLogger (Recommended)
**Notes:** None

---

## Decision Trace Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Error + LLM context (Recommended) | Error, LLM prompt/response, files read, final state. | ✓ |
| Full step-by-step | Every action: file reads, edit attempts, validation results, retries. | |
| Error summary only | Just error message and task metadata. | |

**User's choice:** Error + LLM context (Recommended)
**Notes:** None

---

## Failure Heatmap Aggregation

| Option | Description | Selected |
|--------|-------------|----------|
| By error type (Recommended) | Group by failure category (syntax, test, contract, structural). | |
| By file path | Which files keep breaking across tasks. | |
| By module + error type | Two-dimensional: module × error type. | ✓ |

**User's choice:** By module + error type
**Notes:** Most informative approach, aligns with Analyzer module map

---

## Progress Metrics View Location

| Option | Description | Selected |
|--------|-------------|----------|
| Extend activity stream (Recommended) | Collapsible metrics header in existing agent activity panel. | ✓ |
| New dedicated panel | Separate 'Metrics' panel/tab in IDE layout. | |
| Status bar overlay | Compact metrics in top bar. | |

**User's choice:** Extend activity stream (Recommended)
**Notes:** None

---

## Contract Backward Compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| Schema diffing (Recommended) | Compare old vs new contract file content. | ✓ |
| Rule-based per type | Specific rules per contract type. | |
| LLM-assisted review | LLM compares old and new contract semantically. | |

**User's choice:** Schema diffing (Recommended)
**Notes:** None

---

## Migration Strategy Format

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown document (Recommended) | migration.md with what broke, why, and steps. Git-tracked. | ✓ |
| Structured JSON | Machine-readable migration.json with auto-apply steps. | |
| Inline annotations | Comments in contract file marking changes. | |

**User's choice:** Markdown document (Recommended)
**Notes:** None

---

## Claude's Discretion

- TraceLogger internal refactoring details
- Specific diff algorithm per contract type
- Progress metrics WebSocket event format and frequency
- Failure heatmap data structure and aggregation logic
- Contract version detection method
- Activity stream header component design

## Deferred Ideas

- Failure classification A/B/C/D (Phase 15)
- Module ownership model (Phase 15)
- DAG visualization graph/tree view
- Alert/notification system for CI failures
- Historical metrics trending
