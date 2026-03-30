# Milestones

## v1.2 Autonomous Software Factory (Shipped: 2026-03-30)

**Phases completed:** 5 phases, 19 plans

**Key accomplishments:**

- DAG orchestrator with NetworkX dependency graph, SQLite persistence, and EventBus extension for real-time progress streaming
- Analyzer agent parsing codebases into module maps with dependency graphs and LLM-enriched per-module summaries
- Planner agent with three-layer decomposition (PRD → Tech Spec → Task DAG) with validation gates and bounded task sizes (≤300 LOC / ≤3 files)
- Contract store with versioned DB schema, OpenAPI definitions, and shared types readable/writable by agents
- Observability layer: unified TraceLogger, progress metrics WebSocket, decision traces, failure heatmap
- Execution engine with BranchManager (asyncio.Lock git isolation), CIRunner (4-stage pipeline), FailureClassifier (tiered retry budgets), ContextPackAssembler, OwnershipValidator
- Ship rebuild proof: orchestration script, Ship CI pipeline, Railway deploy scripts, API smoke tests, Playwright E2E framework
- Blocked at Railway deployment (trial expired) — billing unresolved

**Pending from v1.2:** PLAN-04, CNTR-03, EXEC-01, EXEC-03, OBSV-01 (deferred, not blocking v1.3)

---

## v1.1 IDE UI Rebuild (Shipped: 2026-03-27)

**Phases completed:** 4 phases, 9 plans, 17 tasks

**Key accomplishments:**

- Zustand state layer with wsStore for WebSocket events and workspaceStore for tab management, replacing React Context event distribution
- Three-panel resizable IDE shell with react-resizable-panels v4, persistent TopBar with instruction input, project selector, and run status indicator, replacing CSS grid AppShell
- Tabbed editor area with Shiki syntax highlighting, VS Code-style preview/pin tabs, and file viewer with line numbers
- Side-by-side diff with jsdiff structuredPatch algorithm, Shiki syntax highlighting on both sides, 3-context-line hunks, and auto-open on edit proposals
- Event rendering components (EventTypeBadge, EventCard, StreamingBlock, RunSection, NewEventBadge) with 11-type mapping, ref-based streaming, and CSS animations
- Full AgentPanel rewrite with real-time activity stream, sticky-bottom auto-scroll, run grouping by run_id, and new-event badge
- Cast `event.data.error` from `unknown` to `string` via `String()` wrapper, fixing the sole remaining TypeScript build error

---

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
