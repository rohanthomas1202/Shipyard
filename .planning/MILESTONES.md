# Milestones

## v1.0 Agent Core MVP (Shipped: 2026-03-27)

**Phases completed:** 7 phases, 21 plans, 37 tasks

**Key accomplishments:**

- 3-tier fuzzy matching chain (exact/whitespace-normalized/fuzzy) with indentation preservation and SHA-256 content hashing for edit_file()
- Closed editor retry feedback loop with two error sources, migrated to structured LLM outputs via EditResponse, and added file freshness detection via content_hash
- SQLite WAL mode on init, async executor_node via run_command_async, async _syntax_check eliminating all blocking subprocess.run from agent nodes
- Python syntax checking via ast.parse and bulletproof LSP fallback with timeout guard and defensive error handling
- Circuit breaker in should_continue() stops retrying after 2 identical normalized validation errors on same step, routing to advance or reporter instead
- LLMResult/LLMStructuredResult dataclasses wrapping OpenAI responses with token usage, TokenTracker with MODEL_PRICING cost estimation, and ModelRouter usage accumulation
- Skeleton views and line-range reading in reader_node to reduce token waste on large files
- ContextAssembler with model-aware budgets in planner/editor nodes, token usage reporting in reporter traces
- AsyncSqliteSaver checkpointing wired into LangGraph graph with automatic crash recovery resuming interrupted runs on server restart
- POST /runs/{run_id}/cancel endpoint with asyncio.Task cancellation, CancelledError handling, and snapshot-based edit rollback across all execution paths
- LangSmith shared trace links via tag-based lookup with graceful degradation when tracing unavailable
- External context (spec, schema, test_results, extra) wired through all LLM-calling nodes with tests proving state isolation across sequential runs
- Conditional reporter->auto_git edge triggers branch/stage/commit after edits, with plan-step git routing to advance
- Parallel batch execution via asyncio.gather with edit_history merging and same-file conflict detection
- Ship project registration script with --dry-run validation and structured rebuild log template with intervention tracking taxonomy
- Integration tests with Ship-like TypeScript/React fixtures validating reader, editor, and planner nodes via mocked LLM responses
- Async CLI script orchestrating 5 graduated instructions to Shipyard agent with polling, retry, and automatic SHIP-REBUILD-LOG.md logging
- All 8 CODEAGENT.md sections populated with substantive content: 8 architecture decisions with rationale, Ship rebuild log with structured placeholders, 7-section comparative analysis, and cost analysis with dev spend table and 3-tier production projections
- 5-section AI Development Log documenting Claude Code + GSD workflow across 7 phases, plus 3-scene demo video script covering surgical edit, multi-agent coordination, and Ship rebuild
- 1. No Dockerfile in worktree

---
