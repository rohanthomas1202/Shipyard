---
phase: 01-edit-reliability
plan: 02
subsystem: llm-structured-output
tags: [structured-output, pydantic, openai-parse, llm]
dependency_graph:
  requires: []
  provides: [call_llm_structured, EditResponse, ValidatorFeedback, ModelRouter.call_structured]
  affects: [agent/llm.py, agent/router.py, agent/schemas.py]
tech_stack:
  added: [pydantic-response-models, openai-parse-api]
  patterns: [structured-output, schema-enforced-responses]
key_files:
  created:
    - agent/schemas.py
  modified:
    - agent/llm.py
    - agent/router.py
    - tests/test_llm.py
    - tests/test_router.py
decisions:
  - Used OpenAI non-beta parse() path (client.chat.completions.parse) per SDK 2.x recommendation
  - Kept call_llm() completely unchanged for backward compatibility
metrics:
  duration: 2m 12s
  completed: "2026-03-26T23:33:24Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 10
  tests_total: 17
---

# Phase 01 Plan 02: Structured LLM Output Summary

Pydantic response models (EditResponse, ValidatorFeedback) with OpenAI non-beta parse() API for schema-enforced structured LLM output, eliminating JSON parse failures.

## What Was Done

### Task 1: Create Pydantic schemas and add call_llm_structured() to llm.py
- Created `agent/schemas.py` with `EditResponse` (anchor, replacement) and `ValidatorFeedback` (file_path, error_message, line, suggestion) Pydantic models
- Added `call_llm_structured()` to `agent/llm.py` using `client.chat.completions.parse()` (non-beta path for SDK 2.x)
- Added `from pydantic import BaseModel` import to llm.py
- Added 7 new tests: schema validation (2), structured call behavior (4), backward compat (1)
- Commit: `6280144`

### Task 2: Add call_structured() to ModelRouter
- Added `call_structured()` method to `ModelRouter` class with same tier/escalation policy as `call()`
- Imports `call_llm_structured` from `agent.llm` and `BaseModel` from pydantic
- Added 2 new tests: correct routing and escalation on error
- Commit: `8add232`

## Deviations from Plan

None -- plan executed exactly as written.

## Key Implementation Details

- `call_llm_structured()` uses `client.chat.completions.parse()` (non-beta namespace) which is the correct path for OpenAI SDK 2.x
- `response_format=response_model` tells OpenAI to enforce the Pydantic schema server-side
- `max_completion_tokens` used instead of `max_tokens` for parse() API compatibility
- Existing `call_llm()` and `router.call()` are completely untouched -- zero backward compat risk

## Verification Results

- `python -m pytest tests/test_llm.py tests/test_router.py -x -q` -- 17 passed
- `python -c "from agent.schemas import EditResponse, ValidatorFeedback; print('OK')"` -- OK
- `python -c "from agent.router import ModelRouter; assert hasattr(ModelRouter, 'call_structured')"` -- OK

## Known Stubs

None -- all functionality is fully wired.

## Self-Check: PASSED

- agent/schemas.py: FOUND
- agent/llm.py: FOUND
- agent/router.py: FOUND
- Commit 6280144: FOUND
- Commit 8add232: FOUND
