# Phase 1: Edit Reliability - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Edits succeed on first attempt far more often, and retries that do occur are informed by specific failure context. This phase implements layered fuzzy anchor matching, actionable error feedback in retry prompts, indentation preservation, file freshness checking via checksums, and structured LLM outputs (strict: true).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from research:
- Fuzzy matching should cascade: exact -> whitespace-normalized -> fuzzy Levenshtein (threshold ~0.85)
- Error feedback must include: which anchor failed, what was found instead, similarity score
- Indentation detection must handle tabs vs spaces, nesting level
- File freshness via content hash (hashlib), not timestamps
- OpenAI structured outputs with `strict: True` and `response_format` on all LLM calls

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/tools/file_ops.py` — current `edit_file()` with `str.replace()` (exact match only)
- `agent/nodes/editor.py` — editor node that calls LLM for anchor/replacement JSON
- `agent/nodes/validator.py` — validator with rollback + 3 retries
- `agent/state.py` — `AgentState` with `file_buffer`, `edit_history`, `error_state`
- `agent/llm.py` — OpenAI wrapper with tiered routing
- `agent/router.py` — `ModelRouter` with `ROUTING_POLICY` and auto-escalation

### Established Patterns
- Nodes return partial `AgentState` dicts merged by LangGraph
- `file_buffer: Dict[str, str]` caches full file contents
- `edit_history: List[dict]` stores snapshots for rollback
- `error_state: Optional[str]` carries error info (currently string, should be structured)

### Integration Points
- `edit_file()` in `file_ops.py` is called by `editor_node` — fuzzy matching goes here
- `validator_node` reads `error_state` — error feedback wiring connects validator output to editor retry
- `should_continue()` in `graph.py` checks `error_state` for retry decisions
- All LLM calls go through `agent/llm.py` — structured outputs change goes here

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
