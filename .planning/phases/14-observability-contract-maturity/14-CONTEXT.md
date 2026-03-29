# Phase 14: Observability + Contract Maturity - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Add structured logging across all agents with unified format and filtering, a real-time progress metrics view in the frontend activity stream, decision traces with failure heatmaps for debugging failed tasks, and backward compatibility validation for contract changes with migration strategy support.

</domain>

<decisions>
## Implementation Decisions

### Structured Logging
- **D-01:** Extend existing TraceLogger with unified format — add `agent_id`, `task_id`, `severity` (debug/info/warn/error), and structured data fields to the existing file-based JSON trace system. No new dependencies or persistence layers.
- **D-02:** Logs filterable by agent, task, and severity. TraceLogger already has `run_id` and `node` — extend with DAG-level identifiers.

### Decision Traces & Failure Analysis
- **D-03:** Decision trace depth: error + LLM context — capture error message, LLM prompt/response, files read, and final state for failed tasks. Not full step-by-step, not error-only.
- **D-04:** Failure heatmap aggregated by module × error type — two-dimensional: module from Analyzer's module map crossed with error category (syntax, test, contract, structural). Aligns with Phase 15's A/B/C/D failure classification.

### Progress Metrics View
- **D-05:** Extend the existing agent activity stream panel — add a collapsible metrics header showing DAG progress bar, task completion counts, DAG coverage percentage, and CI pass rate. No new panel or tab.
- **D-06:** Metrics pushed via WebSocket — extend existing WS infrastructure with new event types for progress updates. Frontend subscribes via existing Zustand store.

### Contract Backward Compatibility
- **D-07:** Schema diffing approach — compare old vs new contract file content to detect removed fields, changed types, removed endpoints. Works for all contract types (.sql, .yaml, .ts, .json).
- **D-08:** Migration strategy as markdown document — when breaking changes are detected, generate a `migration.md` file alongside the contract change listing what broke, why, and step-by-step migration instructions. Git-tracked, human-readable.

### Claude's Discretion
- TraceLogger internal refactoring to support new fields
- Specific diff algorithm for each contract type (text diff vs structural diff)
- Progress metrics WebSocket event format and update frequency
- Failure heatmap data structure and aggregation logic
- How to detect "old" vs "new" contract versions (git diff, snapshot, etc.)
- Activity stream header component design details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Observability
- `agent/tracing.py` — TraceLogger with JSON file output and LangSmith integration. Extend this, don't replace.
- `agent/events.py` — EventBus with P0/P1/P2 priority routing, sequence numbers, batching. Extend for structured log events.
- `agent/orchestrator/events.py` — 7 task lifecycle event constants (TASK_STARTED/COMPLETED/FAILED, DAG_STARTED/COMPLETED/FAILED, CONTRACT_UPDATE_REQUESTED).

### Contract Store
- `agent/orchestrator/contracts.py` — ContractStore with read/write/list for .sql/.yaml/.ts/.json files. Add backward compatibility checks here.
- `agent/orchestrator/models.py` — TaskNode, TaskExecution Pydantic models. TaskExecution has `error_message` and `result_summary` fields for trace data.

### Frontend
- `web/src/stores/wsStore.ts` — Zustand store receiving WebSocket events. Add new event types for progress metrics.
- `web/src/context/WebSocketContext.tsx` — WebSocket bridge to Zustand. Routes new event types.
- `web/src/components/AgentPanel.tsx` — Agent activity stream panel. Extend with collapsible metrics header.

### Server
- `server/main.py` — FastAPI server with DAG REST endpoints. Add metrics endpoints if needed.
- `server/websocket.py` — WebSocket connection manager. Progress events flow through here.

### Analyzer (for module-based heatmap)
- `agent/analyzer/models.py` — ModuleInfo, ModuleMap. Heatmap maps failures to modules from this map.

### Requirements
- `.planning/REQUIREMENTS.md` — CNTR-03, OBSV-01, OBSV-02, OBSV-03 define acceptance criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TraceLogger` (agent/tracing.py) — JSON trace writer with run_id/node/data fields. Extend with agent_id, task_id, severity.
- `EventBus` (agent/events.py) — Priority-based event dispatch with WebSocket streaming. Extend for log and progress events.
- Task lifecycle events (agent/orchestrator/events.py) — 7 event types already defined. Add trace and progress events.
- `ContractStore` (agent/orchestrator/contracts.py) — File-based CRUD. Add diff and compatibility checking.
- `DAGPersistence` (agent/orchestrator/persistence.py) — SQLite state for task executions. Query for metrics.
- Zustand wsStore (web/src/stores/wsStore.ts) — WebSocket event handler. Add progress event handling.

### Established Patterns
- Events flow: EventBus → WebSocket → Zustand store → React components
- Pydantic models for all data structures
- React components in `web/src/components/` with Tailwind CSS
- Frosted glassmorphic design system (from user design preferences)

### Integration Points
- Extend TraceLogger with unified format fields
- Extend EventBus with log/progress event types
- Extend ContractStore with diff and compatibility methods
- Extend AgentPanel with collapsible metrics header
- New migration.md template for breaking contract changes
- New failure heatmap data model (module × error type)

</code_context>

<specifics>
## Specific Ideas

- The progress metrics header in the activity stream should be collapsible so it doesn't take space when users are focused on individual events
- Failure heatmap is a data structure/API first — frontend visualization can be minimal (table or simple grid) since the data model matters more than the UI at this stage
- Contract diffing should leverage git history where possible (contracts are git-tracked per Phase 12 D-04/D-05)
- Migration docs should follow a consistent template: What Broke → Why → Migration Steps → Verification

</specifics>

<deferred>
## Deferred Ideas

- Failure classification system A/B/C/D (Phase 15 — heatmap error categories align with this)
- Module ownership model (Phase 15)
- DAG visualization graph/tree view in frontend (could be a future enhancement)
- Alert/notification system for CI failures
- Historical metrics trending across runs

</deferred>

---

*Phase: 14-observability-contract-maturity*
*Context gathered: 2026-03-29*
