---
phase: 03-context-token-management
plan: 01
subsystem: agent
tags: [openai, token-tracking, cost-estimation, dataclass, llm]

# Dependency graph
requires:
  - phase: 01-edit-reliability
    provides: "Structured LLM outputs via OpenAI parse() API"
provides:
  - "LLMResult and LLMStructuredResult dataclasses wrapping LLM responses with usage"
  - "TokenTracker module with per-model cost estimation"
  - "ModelRouter usage accumulation via get_usage_log/get_usage_summary"
affects: [03-context-token-management, 04-crash-recovery]

# Tech tracking
tech-stack:
  added: []
  patterns: ["LLM result wrapper pattern — internal rich objects, external simple types"]

key-files:
  created:
    - agent/token_tracker.py
  modified:
    - agent/llm.py
    - agent/router.py
    - tests/test_llm.py
    - tests/test_router.py
    - tests/test_token_tracker.py

key-decisions:
  - "LLMResult/LLMStructuredResult are dataclasses not Pydantic models — lightweight, no validation overhead"
  - "Router external API unchanged (str/BaseModel) — no breaking changes to node callers"
  - "Unknown models fall back to gpt-4o pricing in cost estimation"
  - "call_llm_structured added to router as call_structured method for future node usage"

patterns-established:
  - "Rich internal result objects with simple external return types"
  - "TokenTracker as per-router accumulator, reset per run"

requirements-completed: [LIFE-02]

# Metrics
duration: 4min
completed: 2026-03-27
---

# Phase 3 Plan 1: LLMResult, TokenTracker, and Router Usage Accumulation Summary

**LLMResult/LLMStructuredResult dataclasses wrapping OpenAI responses with token usage, TokenTracker with MODEL_PRICING cost estimation, and ModelRouter usage accumulation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T00:28:06Z
- **Completed:** 2026-03-27T00:32:03Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- call_llm and call_llm_structured now return rich result objects with .content/.parsed, .usage dict, and .model name
- TokenTracker module computes per-model cost estimates using MODEL_PRICING (o3, gpt-4o, gpt-4o-mini rates)
- ModelRouter accumulates usage from every LLM call (including escalation) without changing external API
- 19 tests covering all new functionality including backward compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: LLMResult dataclasses and TokenTracker module** - `d076587` (feat)
2. **Task 2: Router usage accumulation** - `6994003` (feat)

## Files Created/Modified
- `agent/token_tracker.py` - TokenTracker dataclass with MODEL_PRICING and cost estimation
- `agent/llm.py` - Added LLMResult, LLMStructuredResult dataclasses; updated call_llm/call_llm_structured to return them
- `agent/router.py` - Added TokenTracker wiring, call_structured method, get_usage_log/get_usage_summary/reset_usage
- `tests/test_token_tracker.py` - Tests for record/totals, cost estimation (single, mixed, unknown model)
- `tests/test_llm.py` - Updated for LLMResult return type, added no-usage and structured tests
- `tests/test_router.py` - Updated mocks for LLMResult, added accumulation/reset/structured tests

## Decisions Made
- LLMResult/LLMStructuredResult are plain dataclasses (not Pydantic) for lightweight overhead
- Router external API unchanged: call() returns str, call_structured() returns BaseModel
- Unknown models fall back to gpt-4o pricing in estimated_cost()
- Added call_structured to router (was missing) to support structured output routing with usage tracking

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added call_llm_structured function to agent/llm.py**
- **Found during:** Task 1
- **Issue:** Plan referenced call_llm_structured but it did not exist in agent/llm.py
- **Fix:** Implemented call_llm_structured using client.beta.chat.completions.parse with LLMStructuredResult return
- **Files modified:** agent/llm.py
- **Verification:** test_call_llm_structured_returns_result passes
- **Committed in:** d076587 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for router.call_structured to work. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- LLMResult/LLMStructuredResult ready for consumption by ContextAssembler in plan 03-03
- TokenTracker ready for reporter node token summary in plan 03-03
- Router usage methods ready for per-run cost surfacing

---
*Phase: 03-context-token-management*
*Completed: 2026-03-27*
