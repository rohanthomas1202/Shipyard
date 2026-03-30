# Pitfalls Research

**Domain:** Persistent agent loop, from-scratch code generation, intervention logging, comparative analysis -- added to existing autonomous coding agent (Shipyard v1.3)
**Researched:** 2026-03-30
**Confidence:** HIGH (based on codebase analysis of existing architecture + well-documented patterns for long-running async systems)

## Critical Pitfalls

### Pitfall 1: Fire-and-Forget to Persistent Loop Breaks the Existing Run Lifecycle

**What goes wrong:**
The current `run_rebuild()` in `scripts/ship_rebuild.py` is a standalone script invoked via `asyncio.run()`. It owns the entire event loop lifetime. Converting this to a persistent background task inside the FastAPI server means the rebuild must share the event loop with WebSocket handlers, REST endpoints, and heartbeat tasks. The naive approach -- wrapping `run_rebuild()` in `asyncio.create_task()` from a POST endpoint -- creates a fire-and-forget task with no cancellation handle, no progress reporting, and silent failure if an exception escapes. The `runs` dict in `server/main.py` (line 27) stores run state in memory; if the rebuild task dies, nothing updates the run status to "failed." The frontend shows "running" forever.

**Why it happens:**
Developers assume wrapping an existing `async def` in `create_task` is sufficient for background execution. They forget that: (a) exceptions in detached tasks are silently swallowed unless the task is awaited, (b) the task needs a cancellation mechanism, (c) progress must flow through EventBus, not `print()` statements (the current rebuild script uses `print()` on lines 252, 263, 278, 283, etc.), and (d) server shutdown must await or cancel running rebuild tasks.

**How to avoid:**
1. Store the `asyncio.Task` reference in `app.state.rebuild_task` so it can be cancelled and awaited.
2. Wrap the entire `run_rebuild()` body in a try/except that catches ALL exceptions and updates run status to "failed" via the store + emits a `rebuild_failed` event.
3. Replace all `print()` calls with `EventBus.emit()` events typed for rebuild progress (e.g., `rebuild_phase_started`, `rebuild_phase_completed`).
4. On server shutdown (`lifespan` context manager exit), cancel the rebuild task and await it with a timeout.
5. Add a `POST /rebuild/cancel` endpoint that cancels the stored task.
6. Use `asyncio.shield()` around critical sections (git commits, dependency installs) that must not be interrupted mid-operation.

**Warning signs:**
- Rebuild endpoint returns 200 but no WebSocket events ever arrive
- Server restart during rebuild leaves output directory in corrupted state
- Frontend shows "running" status indefinitely after a rebuild error
- `print()` output only visible in server logs, not in UI

**Phase to address:**
Phase 1 (persistent agent loop) -- the `POST /rebuild` endpoint and task lifecycle management must be the first thing built, because all other features (progress UI, intervention logging, comparative analysis) depend on the rebuild being observable.

---

### Pitfall 2: From-Scratch Generation Hits the Editor Node's "File Must Exist" Assumption

**What goes wrong:**
The entire agent pipeline assumes files already exist. The editor node (`agent/nodes/editor.py`) calls `read_file()` to get current content, then `edit_file()` which does anchor-based string replacement. The reader node populates `file_buffer` by reading existing files. The validator checks syntax of existing files. For from-scratch generation, there is no existing file to read, no anchor to match, and no content to replace. Naively passing "create this file" as an instruction to the existing graph causes: reader fails (file not found), editor has empty `file_buffer`, anchor matching returns no results, and the step fails after 3 retries.

**Why it happens:**
Shipyard v1.0 was designed for "edit existing codebase" -- the entire state machine flows through read -> edit -> validate. From-scratch generation is fundamentally different: it requires generate -> write -> validate. The `_seed_output_from_source()` function (line 168 of `ship_rebuild.py`) exists precisely because the agent cannot generate from scratch -- it copies the source repo first. Removing seeding without adding a generation pathway breaks the core pipeline.

**How to avoid:**
1. Add a new `PlanStep.kind = "create"` alongside existing "read", "edit", "exec", etc. Route it to a new `creator_node` or extend editor to handle creation.
2. The creator node flow: LLM generates full file content -> write to disk -> validate syntax -> commit to file_buffer. No anchor matching, no old_content.
3. Extend `EditRecord` model to support `old_content=None` (already nullable) for creation events.
4. The planner must output "create" steps for new files and "edit" steps only for files that already exist. Include file path in the step so the creator knows where to write.
5. Add `file_ops.write_file()` (create new file) distinct from `edit_file()` (modify existing). Ensure parent directories are created with `os.makedirs(exist_ok=True)`.
6. Update the validator to handle newly created files that have no baseline for LSP diagnostic diffing.
7. Critical: the DAG task descriptions from the planner must specify which files to create vs edit. If the planner says "implement the API routes" without specifying file paths, the creator node cannot determine what to write or where.

**Warning signs:**
- "FileNotFoundError" in reader node logs during rebuild
- Steps failing on retry loop with "anchor not found" when the file does not exist yet
- Agent creates file content in LLM output but has no mechanism to write it to disk
- All DAG tasks produce 0 edits despite "completing" without error

**Phase to address:**
Phase 2 (from-scratch code generation) -- this requires new node logic, new plan step kinds, and changes to how the planner generates tasks. Must be built and tested before the full rebuild pipeline runs.

---

### Pitfall 3: SQLite Write Contention During Long-Running Concurrent Rebuilds

**What goes wrong:**
The DAGScheduler runs up to 10 concurrent tasks (`max_concurrency=10`). Each task invokes the full LangGraph graph, which writes events, edit records, and run updates to SQLite via `SQLiteSessionStore`. The EventBus also writes events. The intervention logger will add more writes. SQLite in WAL mode handles concurrent reads well but serializes writes. With 10+ concurrent writers hammering the same database file, write latency spikes from <1ms to 50-200ms. Worse, `aiosqlite` wraps synchronous sqlite3 in a thread -- under high concurrency, the thread pool saturates and writes queue up, causing event delivery delays that make the frontend appear frozen.

**Why it happens:**
WAL mode allows concurrent readers but still serializes writers. The existing system works for single-run scenarios (1 graph invocation = modest write rate). A multi-hour rebuild with 10 concurrent graph invocations multiplies write volume by 10x. Each graph invocation emits dozens of events per step (P0, P1, P2). The intervention logger adds human-triggered writes. The event sequence counter needs atomic increment. All of this hits one SQLite file.

**How to avoid:**
1. Batch event writes: accumulate events in memory for 100ms, then write in a single transaction. The existing `TokenBatcher` (50ms flush) provides the pattern -- apply it to event persistence.
2. Separate the rebuild event log from the main `shipyard.db`. Use a dedicated `rebuild_{id}.db` file for rebuild-specific events and intervention logs. This eliminates contention with the server's normal operations.
3. Use `PRAGMA journal_size_limit` and `PRAGMA synchronous=NORMAL` (not FULL) for the rebuild database -- data loss of the last 100ms of events on crash is acceptable.
4. Write intervention logs to an append-only JSON Lines file (`rebuild_{id}.jsonl`) rather than SQLite. This avoids all contention -- file appends are atomic on POSIX for small writes.
5. Keep the main store writes (run status updates) infrequent -- update status at phase boundaries, not per-event.

**Warning signs:**
- Event delivery latency >500ms (events arrive in bursts instead of smoothly)
- "database is locked" errors in logs
- Frontend progress jumps from 10% to 40% in one update instead of smooth progression
- Intervention log writes block agent task completion

**Phase to address:**
Phase 1 (persistent loop) for event write batching, Phase 3 (intervention logging) for the separate log file strategy.

---

### Pitfall 4: Intervention Logger Captures the Wrong Granularity

**What goes wrong:**
The intervention logger is supposed to capture every human intervention during the multi-hour rebuild for the comparative analysis. Developers typically log too little (just "user intervened at step X") or too much (full terminal transcripts that are impossible to analyze). Without structured schemas, the logs become a grab bag of unrelated data that the comparative analysis generator cannot parse into the 7 required sections.

**Why it happens:**
"Intervention logging" sounds simple but requires answering hard design questions upfront: What counts as an intervention? (Manual code fix? Restart? Configuration change? Approving a stuck step?) What context surrounds it? (What was the agent doing? What error triggered it? What files were affected?) What is the outcome? (Did the intervention resolve the issue? Did the agent continue successfully?) Without a schema, each intervention is logged ad-hoc, and the comparative analysis step cannot extract patterns.

**How to avoid:**
1. Define an `Intervention` schema upfront with required fields:
   - `id`, `timestamp`, `rebuild_id`
   - `trigger`: what caused the intervention (error, timeout, quality issue, missing file, wrong output)
   - `agent_state_snapshot`: current DAG task, step number, files being processed
   - `description`: human-written explanation of what was done
   - `files_affected`: list of file paths modified
   - `resolution`: how the intervention resolved the issue
   - `category`: one of (code_fix, config_fix, restart, approval, skip, dependency_fix)
   - `time_spent_seconds`: wall clock time of the intervention
   - `could_agent_have_done_this`: boolean + explanation (feeds directly into comparative analysis)
2. Build a CLI or simple web form for logging interventions -- friction must be minimal or they will not be logged during a multi-hour session.
3. Auto-capture context: when the user triggers "log intervention," automatically snapshot the current DAG state, recent events, and error logs. Do not require the human to type all context manually.
4. Log the agent's state BEFORE and AFTER intervention so the comparative analysis can calculate "time saved" and "error fixed."

**Warning signs:**
- Intervention log entries have inconsistent fields (some have file paths, some do not)
- No way to correlate an intervention with the DAG task or agent step that triggered it
- Comparative analysis section on "human vs agent capabilities" has no data to draw from
- Interventions logged as free-text paragraphs with no structured fields

**Phase to address:**
Phase 3 (intervention logging) -- the schema must be defined before the first rebuild run, because retroactively structuring unstructured logs is unreliable.

---

### Pitfall 5: Comparative Analysis Becomes Marketing Fiction Instead of Honest Assessment

**What goes wrong:**
The 7-section comparative analysis must be generated from actual rebuild data. If the rebuild has significant failures (tasks fail, human interventions needed, output does not build), the analysis generator will either: (a) hallucinate positive results because the LLM prompt says "generate analysis," or (b) produce an honest but devastating assessment that the developer does not ship. Either outcome defeats the purpose.

**Why it happens:**
The LLM generating the comparative analysis has no ground truth -- it sees rebuild logs and intervention data but has no independent verification of whether the rebuilt app actually works. If the prompt is "analyze the rebuild" without guardrails, o3 will produce confident-sounding analysis regardless of quality. If metrics are not pre-computed from hard data (task success rate, build pass/fail, test pass/fail, lines of code generated, time to complete), the analysis is just LLM prose.

**How to avoid:**
1. Pre-compute hard metrics BEFORE invoking the LLM for analysis:
   - Task completion rate: `completed / total` from DAGRun
   - Build success: boolean from final `pnpm build` exit code
   - Test pass rate: from CI runner results
   - Total interventions: count from intervention log
   - Time breakdown: wall clock per phase from event timestamps
   - Lines of code generated: `wc -l` on output directory
   - Token usage and estimated cost: from `router.get_usage_summary()`
2. Feed hard metrics as structured data to the LLM, not raw logs. The LLM's job is to write prose around verified numbers, not to derive numbers from logs.
3. Include a "Limitations and Failures" section as a required output section. Prompt the LLM to explicitly list what did NOT work.
4. Validate generated claims against the metrics: if the analysis says "95% task success" but metrics show 60%, flag the discrepancy.
5. Human reviews the draft before it is finalized -- the analysis is a deliverable, not fire-and-forget.

**Warning signs:**
- Analysis claims "all tasks completed successfully" but DAGRun shows failures
- No quantitative data in the analysis (all qualitative assertions)
- Analysis avoids mentioning interventions or minimizes them
- The "Limitations" section is empty or vague

**Phase to address:**
Phase 4 (comparative analysis) -- metric computation must be built into the rebuild pipeline (Phase 1-2), and the analysis generator must receive structured metrics as input.

---

### Pitfall 6: Railway Deployment Blocks on Expired Trial with No Fallback

**What goes wrong:**
The milestone lists Railway deployment as a target. Railway trials expire after 30 days or $5 of usage. If the trial has expired, deployment is blocked entirely. Since the rebuilt Ship app uses SQLite (file-based), Railway's ephemeral filesystem means the database resets on every deploy. The Procfile assumes `uvicorn` but the rebuilt Ship app is a different stack (pnpm monorepo with API + web packages). Deployment fails silently with a build error or starts but crashes on first request.

**Why it happens:**
Developers plan deployment as the last step and discover infrastructure issues too late. Railway's trial limitations are not visible until you try to deploy. The rebuilt Ship app's deployment requirements (build command, start command, port binding, environment variables) differ from Shipyard's own Procfile. The deployment is treated as a checkbox rather than a technical challenge.

**How to avoid:**
1. Verify Railway account status FIRST -- before writing any code. Log in, check billing status, add payment method if trial expired. This takes 5 minutes but blocks everything if postponed.
2. Create a minimal Railway deployment test early: deploy a "hello world" Node.js app to verify the account works, the build pipeline runs, and the app is accessible at a public URL.
3. For the Ship app specifically: determine its build/start commands from `package.json` scripts. Ship is a pnpm monorepo -- Railway needs `pnpm install && pnpm build` and a start command that serves the built web app.
4. If Railway is blocked (expired, billing issues), have a fallback: Render.com free tier or Fly.io hobby tier. Both support Node.js apps with similar configuration.
5. For SQLite persistence on Railway: use a Railway volume mount, or switch to Postgres (Railway provides managed Postgres). For a demo, SQLite with volume mount is sufficient.
6. Set `PORT` environment variable -- Railway injects it dynamically. The app must bind to `process.env.PORT`.

**Warning signs:**
- Railway dashboard shows "trial expired" or payment required
- Build succeeds but app crashes on startup (port binding, missing env vars)
- App starts but returns 404 on all routes (wrong start command, static files not built)
- Database operations fail after redeploy (ephemeral filesystem wiped SQLite file)

**Phase to address:**
Phase 5 (Railway deployment) -- but account verification should happen in Phase 1 as a prerequisite check. Do not wait until the end.

---

### Pitfall 7: Persistent Loop Leaks Memory Over Multi-Hour Rebuilds

**What goes wrong:**
The rebuild runs for hours. The LangGraph graph is compiled once (`build_graph()`) and invoked per task. Each invocation accumulates state in `AgentState`: `messages` (Annotated with `add_messages` -- a reducer that APPENDS), `edit_history`, `validation_error_history`, `file_buffer`. Over hundreds of task invocations, these lists grow without bound. The `runs` dict in `server/main.py` stores full `AgentState` results in memory. The EventBus accumulates events. After 4-6 hours, the Python process exceeds available memory.

**Why it happens:**
The current architecture assumes short-lived runs (one instruction, ~10 plan steps, done). A persistent rebuild loop runs hundreds of tasks sequentially through the same server process. No cleanup happens between tasks. The `add_messages` reducer on `AgentState.messages` means LangGraph appends to the list on every node invocation -- for a single task with 10 nodes, that is 10+ message additions. Across 100 tasks, that is 1000+ messages in state if state is reused.

**How to avoid:**
1. Each DAG task gets a FRESH `AgentState` (the current `ship_executor.py` already does this correctly -- verify it stays this way).
2. After each task completes, do NOT store the full `AgentState` result. Extract only summary data (edit count, files modified, success/failure, token usage) and discard the rest.
3. Limit the `runs` dict to a sliding window of recent runs (e.g., last 50). Older runs are in the database, not memory.
4. After each rebuild phase completes, force garbage collection with `gc.collect()`. This is not normally needed but helps with long-running processes that accumulate many short-lived objects.
5. Monitor memory usage: emit a `memory_usage` event every 60 seconds with `psutil.Process().memory_info().rss`. Alert if >2GB.
6. The EventBus `TokenBatcher` accumulates items in a list -- ensure the flush callback actually clears the buffer (it does: `self._buffer.clear()` on line 37).

**Warning signs:**
- Server RSS memory grows continuously during rebuild (check with `ps aux`)
- "MemoryError" or OOM kill after 3-4 hours
- Response times for REST endpoints degrade over time
- WebSocket heartbeats start timing out

**Phase to address:**
Phase 1 (persistent loop) -- memory management strategy must be designed into the task lifecycle from the start.

---

## Moderate Pitfalls

### Pitfall 8: Progress Reporting Lies About Completion Percentage

**What goes wrong:**
The frontend shows rebuild progress as "X% complete." The naive calculation is `completed_tasks / total_tasks * 100`. But tasks vary wildly in duration -- a "create package.json" task takes 10 seconds while "implement all API routes" takes 20 minutes. The progress bar jumps from 5% to 6% in 20 minutes, then from 6% to 30% in 2 minutes. Users think the rebuild is stuck.

**How to avoid:**
Use phase-based progress with estimated weights: clone (5%), analyze (10%), plan (10%), execute (65%), build (5%), deploy (5%). Within the execute phase, use task count but show "Task 15/47" alongside the percentage. Add elapsed time and estimated remaining time based on average task duration so far.

**Phase to address:** Phase 1 (persistent loop / frontend progress panel).

---

### Pitfall 9: Git Worktree Cleanup Failure Leaves Stale Branches

**What goes wrong:**
The `BranchManager` creates git worktrees for task isolation. If a task fails or the rebuild is cancelled, worktrees are not cleaned up. Stale worktrees lock branches and prevent re-runs. Over multiple rebuild attempts, `/tmp` fills with abandoned worktree directories.

**How to avoid:**
Add a cleanup step to the scheduler's `finally` block that removes all worktrees created during the run. Use `git worktree prune` after cleanup. Track created worktrees in the `DAGRun` metadata for reliable cleanup even after crashes.

**Phase to address:** Phase 1 (persistent loop) -- cleanup must be part of the task lifecycle.

---

### Pitfall 10: Planner Generates Edit Instructions for Non-Existent Files

**What goes wrong:**
When transitioning from seeded-file editing to from-scratch generation, the planner still generates instructions like "modify the user model to add email field" for files that do not exist yet. The planner was trained/prompted with the assumption that source files exist. Without explicit context that the output directory is empty, the planner produces invalid task descriptions.

**How to avoid:**
Pass a `generation_mode: "from_scratch"` flag to the planner pipeline. Modify planner prompts to explicitly state: "The output directory is empty. All files must be created, not edited. Each task must specify the complete file path and describe the full content to generate." Include the PRD and tech spec as the sole source of truth, not the analyzed source repo.

**Phase to address:** Phase 2 (from-scratch code generation) -- planner prompt changes must happen before DAG task generation.

---

### Pitfall 11: Created Files Have No Import Coordination Across Concurrent Tasks

**What goes wrong:**
Two concurrent tasks both create files that import from each other. Task A creates `models.py` importing from `utils.py`. Task B creates `utils.py` importing from `models.py`. Both tasks pass validation individually (each has the imports it needs in its own file), but when merged, circular imports cause runtime failures. Worse, Task A's file might import a function from `utils.py` that Task B never created because its task description was different from what Task A assumed.

**How to avoid:**
1. Define shared interfaces/contracts BEFORE individual module tasks execute. The existing `ContractStore` (Phase 12) should contain API contracts that both tasks reference.
2. Order tasks so foundational modules (types, models, utils, config) are created BEFORE consumers. The DAG dependencies should enforce this ordering.
3. After all tasks complete, run a global validation pass (full build + import check) that catches cross-module issues. This is the "final web build" in the current script -- ensure it actually catches import errors.
4. The `OwnershipValidator` prevents cross-task file conflicts but does not prevent cross-task import assumption mismatches. Add post-merge import validation.

**Phase to address:** Phase 2 (from-scratch generation) -- DAG ordering and contract-first generation must be designed together.

---

### Pitfall 12: Comparative Analysis Missing Required Sections

**What goes wrong:**
The comparative analysis requires 7 specific sections. The LLM generates 5 or generates sections with different names. The output cannot be used as-is for the deliverable.

**How to avoid:**
Hard-code the 7 section headings in the prompt. Use structured output (JSON with 7 required keys) rather than freeform markdown. Validate that all 7 sections are present and non-empty before accepting the output. Retry with explicit "you missed section X" feedback if incomplete.

**Phase to address:** Phase 4 (comparative analysis).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `print()` for rebuild progress | Works for CLI script | Invisible when run as background task | Never in persistent loop -- must use EventBus |
| Storing full AgentState in `runs` dict | Easy to inspect, enables resume | Memory grows unbounded over hours | Single short runs only. For persistent loop, store summaries |
| Single SQLite DB for everything | No config, no connection management | Write contention under 10x concurrent load | OK for server operations. Separate file for rebuild events |
| Intervention logs as unstructured text | Fastest to implement | Cannot be parsed for comparative analysis | Never -- schema must be defined before first rebuild |
| Hardcoded Railway config | Works for one deploy | Breaks if account changes, no fallback | OK for demo if verified early |
| Seeding output dir as "from-scratch" workaround | Rebuild runs today | Does not prove autonomous generation capability | Only for v1.2 proof-of-concept. Must remove for v1.3 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `run_rebuild()` in FastAPI background task | Wrapping in `create_task()` without error handling or cancellation | Store task reference, wrap in try/except, emit lifecycle events |
| LangGraph `add_messages` reducer in persistent loop | Messages accumulate across tasks | Fresh `AgentState` per task (current executor does this, verify) |
| EventBus + intervention logger | Both write events to same DB table concurrently | Separate tables or separate DB files for intervention logs |
| DAG scheduler + from-scratch generation | Scheduler assumes files exist for worktree copy | Initialize empty worktrees, creator node writes files |
| Comparative analysis LLM + rebuild metrics | Feeding raw logs and hoping LLM extracts numbers | Pre-compute all metrics, feed as structured data |
| Railway + pnpm monorepo | Using default build command (npm) | Set `NIXPACKS_BUILD_CMD` or use Railway `railway.toml` for pnpm |
| Git worktrees + empty output directory | Worktrees created from repo with seeded files | For from-scratch, worktrees branch from empty initial commit |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full AgentState stored per task in memory | RSS grows 50MB/hour | Store only summary, discard state after task | >50 tasks in single rebuild |
| Event writes per-message to SQLite | Write latency spikes, "database locked" | Batch writes in 100ms windows | >5 concurrent graph invocations |
| Unbounded intervention log queries | Analysis generation takes minutes | Index by rebuild_id, limit result sets | >100 interventions per rebuild |
| LLM calls for comparative analysis on full logs | Token limit exceeded, slow | Pre-aggregate metrics, send summaries not raw logs | Rebuild logs >100K tokens |
| Git worktree creation per task | Disk space exhaustion in /tmp | Cleanup in finally blocks, reuse worktrees | >30 tasks with large codebases |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Railway deploy with env vars in code | API keys exposed in deployed app | Use Railway environment variables, never hardcode |
| Intervention logs contain API keys typed during debug | Credential leak in deliverable | Sanitize intervention log entries, redact patterns matching `sk-*`, `ghp_*` |
| Rebuild output dir outside project boundary | Agent writes to arbitrary filesystem locations | Validate output_dir is within allowed paths |
| SQLite rebuild DB accessible via `/browse` endpoint | Rebuild data exposed | Exclude `.db` files from browse endpoint |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Progress bar jumps erratically | User thinks rebuild is broken | Phase-weighted progress + "Task 15/47" + elapsed time |
| No intervention logging UI during rebuild | User must remember to log interventions | Floating "Log Intervention" button always visible during rebuild |
| Comparative analysis shown as raw LLM output | Hard to read, no formatting | Render as structured HTML with sections, metrics tables, charts |
| Rebuild errors shown as stack traces | Intimidating, not actionable | Translate to user-facing messages: "Task 'create API routes' failed: build error in routes.ts line 42" |
| No way to retry a single failed task | Must restart entire rebuild | "Retry" button per failed task in progress panel |

## "Looks Done But Isn't" Checklist

- [ ] **Persistent loop:** Server shutdown gracefully cancels running rebuild (not just kills the process)
- [ ] **Persistent loop:** Rebuild status survives server restart (persisted to DB, not just in-memory `runs` dict)
- [ ] **From-scratch generation:** Agent can create a file in a directory that does not exist yet (makedirs)
- [ ] **From-scratch generation:** Generated files have correct imports referencing other generated files (cross-module coherence)
- [ ] **From-scratch generation:** package.json is generated with correct dependencies (not copied from source)
- [ ] **Intervention logging:** Every intervention has a timestamp AND duration (not just "when started")
- [ ] **Intervention logging:** Logs are queryable by category for the comparative analysis
- [ ] **Comparative analysis:** All 7 required sections present and non-empty
- [ ] **Comparative analysis:** Quantitative claims match pre-computed metrics (no hallucinated numbers)
- [ ] **Railway deployment:** App binds to `process.env.PORT` (not hardcoded port)
- [ ] **Railway deployment:** App works after redeploy (persistent data survives or is unnecessary)
- [ ] **Railway deployment:** Public URL is accessible without authentication
- [ ] **Memory:** Server RSS stable (not growing) after 100+ task executions

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Background task silently dies | LOW | Add try/except wrapper, emit failure event, update run status. 1 hour fix |
| Editor node cannot create files | MEDIUM | Add creator_node or extend editor with "create" mode. New node + planner changes. 1-2 days |
| SQLite write contention | MEDIUM | Add write batching to EventBus persistence. Separate rebuild DB. 0.5-1 day |
| Unstructured intervention logs | HIGH | Must re-run rebuild with proper schema. Cannot retroactively structure free-text logs. Prevention only |
| Comparative analysis hallucinations | LOW | Add metric pre-computation step, validate LLM output against metrics. 0.5 day |
| Railway trial expired | LOW | Add payment method or switch to Render.com/Fly.io. 1 hour |
| Memory leak over multi-hour rebuild | MEDIUM | Add state cleanup between tasks, memory monitoring. 0.5-1 day |
| Git worktree accumulation | LOW | Add cleanup to scheduler finally block, run `git worktree prune`. 1 hour |
| Cross-module import failures | HIGH | Redesign DAG ordering, add contract-first generation, post-merge validation. 1-2 days |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Background task lifecycle (#1) | Phase 1 (persistent loop) | POST /rebuild returns, events stream to frontend, cancel works |
| File creation capability (#2) | Phase 2 (from-scratch gen) | Agent creates 10+ files in empty directory, all pass syntax check |
| SQLite write contention (#3) | Phase 1 (persistent loop) | 10 concurrent tasks, event latency <100ms, no "locked" errors |
| Intervention schema (#4) | Phase 3 (intervention logging) | 5 test interventions logged, all fields populated, queryable by category |
| Honest comparative analysis (#5) | Phase 4 (comparative analysis) | Metrics in analysis match pre-computed values, all 7 sections present |
| Railway account verification (#6) | Phase 1 (prerequisite check) | Hello world app deployed to Railway public URL |
| Memory management (#7) | Phase 1 (persistent loop) | RSS stable after 50 task executions (no upward trend) |
| Progress reporting (#8) | Phase 1 (persistent loop) | Progress updates every 30s during long tasks, time estimates shown |
| Git worktree cleanup (#9) | Phase 1 (persistent loop) | No stale worktrees after rebuild completes or is cancelled |
| Planner from-scratch prompts (#10) | Phase 2 (from-scratch gen) | Planner outputs "create" steps, not "edit" steps, for empty output dir |
| Cross-module imports (#11) | Phase 2 (from-scratch gen) | Full build passes after all tasks merge to main branch |
| Analysis completeness (#12) | Phase 4 (comparative analysis) | Automated check: all 7 section headings present, each >100 words |

## Sources

- Codebase audit: `scripts/ship_rebuild.py` -- `print()` calls, `_seed_output_from_source()`, `run_rebuild()` as standalone script
- Codebase audit: `agent/nodes/editor.py` -- `read_file()` and `edit_file()` require existing file content
- Codebase audit: `agent/state.py` -- `add_messages` reducer appends without bound
- Codebase audit: `server/main.py` -- `runs` dict in-memory, `asyncio.create_task()` pattern for runs
- Codebase audit: `agent/orchestrator/ship_executor.py` -- fresh AgentState per task (good pattern)
- Codebase audit: `agent/orchestrator/scheduler.py` -- DAGScheduler with worktree isolation
- Codebase audit: `agent/events.py` -- TokenBatcher flush pattern, EventBus write path
- Codebase audit: `store/models.py` -- EditRecord with nullable old_content
- SQLite WAL mode concurrency characteristics: documented in SQLite official docs
- asyncio.create_task exception handling: Python asyncio documentation
- Railway deployment: ephemeral filesystem, PORT binding, trial limitations

---
*Pitfalls research for: Persistent agent loop, from-scratch generation, intervention logging, comparative analysis (Shipyard v1.3)*
*Researched: 2026-03-30*
