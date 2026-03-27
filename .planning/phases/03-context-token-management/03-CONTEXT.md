# Phase 3: Context & Token Management - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

LLM prompts are token-budgeted and context-aware, and token spend is tracked per run. This phase wires the existing ContextAssembler into all LLM-calling nodes, adds line-range reads for large files, and implements per-run token usage tracking with cost estimation.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase.

Key constraints:
- ContextAssembler already exists at agent/context.py with ranked priority filling — wire it in, don't rebuild
- Line-range reads: for files >200 lines, read only relevant sections (use offset/limit or line extraction)
- Token tracking: capture input/output tokens from OpenAI response.usage, aggregate per run
- Cost estimation: use model-specific pricing (o3, gpt-4o, gpt-4o-mini rates)
- Surface cost in traces (TraceLogger) and via WebSocket events to frontend

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/context.py` — ContextAssembler with ranked priorities (NOT WIRED IN — this is the main gap)
- `agent/llm.py` — call_llm() and call_llm_structured() — OpenAI response includes usage field
- `agent/tracing.py` — TraceLogger for JSON trace files
- `agent/events.py` — EventBus for WebSocket streaming
- `agent/nodes/reader.py` — reader node that loads files into file_buffer

### Integration Points
- All LLM-calling nodes: planner, editor, reader, validator, refactor — currently build prompts via string concatenation
- call_llm() returns response content but discards usage stats
- TraceLogger.log_step() can be extended to include token counts

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
