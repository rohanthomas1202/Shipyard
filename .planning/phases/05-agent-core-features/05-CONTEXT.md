# Phase 5: Agent Core Features - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Agent operates as a persistent, context-aware system that coordinates work and manages git workflows. This phase implements: persistent agent loop (accept new instructions without restart), external context injection (specs, schemas, test results used in generation), multi-agent coordination (2+ agents parallel/sequential with merged outputs), and end-to-end git operations (branch, commit, push, PR).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion.

Key constraints:
- Persistent loop: server already runs continuously, agent needs to accept new instructions on the same process
- Context injection: the /instruction endpoint already accepts a context field — wire it through to ContextAssembler
- Multi-agent: coordinator node already groups steps into parallel/sequential batches — ensure it actually works
- Git ops: git_ops node exists with GitManager — verify branch/commit/push/PR flow works end-to-end
- Must demonstrate with at least 2 agents working in parallel or sequence

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `server/main.py` — POST /instruction endpoint with context field
- `agent/nodes/coordinator.py` — groups PlanSteps into parallel/sequential batches
- `agent/nodes/git_ops.py` — GitManager with branch, commit, push, PR operations
- `agent/state.py` — AgentState with is_parallel, parallel_batches fields
- `agent/context.py` — ContextAssembler (wired in Phase 3)

### Integration Points
- /instruction already accepts `context` dict — needs to flow into AgentState.context
- Coordinator already produces batches — merger node needs to actually merge results
- GitManager uses httpx for GitHub API — needs PAT from project settings

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
