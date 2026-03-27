# Phase 4: Crash Recovery & Run Lifecycle - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Runs survive crashes and disconnects, can be cancelled cleanly, and produce complete observable traces. This phase adds LangGraph AsyncSqliteSaver checkpointing for crash recovery, graceful cancellation with clean state rollback, and LangSmith tracing with shared trace links.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase.

Key constraints:
- LangGraph checkpointing via AsyncSqliteSaver (or MemorySaver if SQLite checkpointer unavailable)
- Cancellation: set a cancel flag, check between nodes, roll back partial work
- LangSmith: env vars already configured (LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT)
- Need 2 shared trace links: one normal run, one error recovery path

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/graph.py` — build_graph() creates the StateGraph
- `agent/tracing.py` — TraceLogger writes JSON traces to traces/
- `server/main.py` — graph invocation via graph.ainvoke(), run state in memory dict
- `agent/events.py` — EventBus for WebSocket streaming

### Integration Points
- graph.ainvoke(initial_state, config) in server/main.py — checkpointer goes in config
- Run state stored in-memory `runs` dict in server/main.py — needs persistence
- LangSmith tracing auto-activates when env vars set + langgraph is used

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
