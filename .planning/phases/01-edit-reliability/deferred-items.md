# Deferred Items - Phase 01: Edit Reliability

## Pre-existing Test Failures

- **tests/test_llm.py::test_call_llm_forwards_params** — Asserts `max_tokens` but `call_llm` uses `max_completion_tokens` (changed in Plan 02). Not caused by Plan 03 changes. Test assertion needs updating to match the new parameter name.
