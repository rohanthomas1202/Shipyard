# PRESEARCH.md — Shipyard Pre-Search Checklist

Completed before writing any code. This document captures architecture decisions and research findings.

---

## Phase 1: Open Source Research

### 1. Agents Studied

#### Agent: OpenCode (github.com/opencode-ai/opencode)

- **Parts of source code read:** Core agent loop (`internal/agent/`), tool implementations (`internal/tools/`), context window management (`internal/context/`), file editing tool (`internal/tools/edit.go`)
- **How it handles file editing:** Anchor-based replacement. The edit tool takes an `old_string` and `new_string` — finds the exact match in the file and replaces it. If `old_string` is empty, it creates a new file. If `old_string` appears multiple times, the edit fails and asks for more context. This is the same pattern Claude Code uses.
  - **Tradeoffs:** Simple, language-agnostic, robust against line drift. Fails gracefully when anchors aren't unique.
  - **Failure modes:** Non-unique anchors, stale file content in context (file changed since last read), anchor spans too many lines and LLM truncates it.
- **How it manages context across turns:** Maintains a message history with automatic summarization. When context grows too large, older messages are compressed into a summary. Tool results are included in full for the current turn but summarized in subsequent turns.
- **How it handles failed tool calls and unexpected output:** Returns the error as a tool result message back to the LLM, allowing it to self-correct. Retries up to 3 times with the error context before surfacing to the user.
- **What I would take from it:** The anchor-based edit strategy — it's proven, simple, and matches what the most successful coding agents use. Also the pattern of returning errors as context for self-correction.
- **What I would do differently:** OpenCode is a CLI tool with no multi-agent support. I need an API server with persistent state and subgraph coordination, which it doesn't provide.

#### Agent: Claude Code (docs.anthropic.com/claude-code)

- **Parts of source code read:** Architecture documentation, permission model docs, sub-agent patterns, human-in-the-loop design
- **How it handles file editing:** Same anchor-based pattern as OpenCode — `old_string` → `new_string` replacement. The `Edit` tool requires the old_string to be unique in the file. Has a `replace_all` flag for bulk renames.
  - **Tradeoffs:** Battle-tested at scale, handles every file type, clear error messages.
  - **Failure modes:** old_string not found (file changed), old_string not unique, new_string identical to old_string.
- **How it manages context across turns:** Automatic context compression when approaching limits. Prior messages are compressed while preserving key information. Recent tool results kept in full.
- **How it handles failed tool calls:** Surfaces errors clearly, allows the model to adjust approach. Does not blindly retry — adapts strategy based on the error type.
- **What I would take from it:** The sub-agent pattern — spawning specialized agents for independent tasks with isolated state, then collecting results. Also the permission model concept (though simplified for our use case).
- **What I would do differently:** Claude Code is an interactive CLI. Shipyard needs to be an API-driven persistent agent that accepts programmatic instructions, not interactive terminal input.

#### Agent: LangChain Open Engineer (github.com/langchain-ai/open-engineer)

- **Parts of source code read:** Multi-agent orchestration patterns, tool composition, memory management
- **How it handles file editing:** Uses LangGraph tool nodes with file operation tools. Generates edits through the LLM and applies them via tool calls.
  - **Tradeoffs:** Good integration with LangGraph state management. Tracing comes for free.
  - **Failure modes:** Context window overflow on large files, tool call formatting errors.
- **How it manages context across turns:** LangGraph state persistence with checkpointing. Message history is part of the graph state.
- **How it handles failed tool calls:** LangGraph's built-in error handling — failed nodes can route to retry or escalation nodes via conditional edges.
- **What I would take from it:** The LangGraph patterns for state management and multi-agent coordination via subgraphs. The `Send` API for fan-out to parallel workers.
- **What I would do differently:** Open Engineer is a reference/demo. I need production-grade error recovery, structured tracing beyond what LangSmith provides automatically, and a persistent server loop.

### 2. File Editing Strategy Decision

**Chosen strategy: Anchor-based replacement**

**Why:** Both OpenCode and Claude Code — the two most successful real-world coding agents — use this exact pattern. It's language-agnostic (works on TS, TSX, JSON, CSS, YAML, MD, SH), resilient to line number drift, and has clear failure modes that are easy to detect and recover from.

**Failure modes and handling:**
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Anchor not found | `anchor not in file_content` | Re-read file, ask LLM for updated anchor |
| Anchor not unique | `file_content.count(anchor) > 1` | Ask LLM for longer anchor with more surrounding context |
| Edit breaks syntax | Post-edit syntax check fails | Revert from snapshot, retry with more conservative edit |
| Edit breaks tests | Executor runs tests, they fail | Revert, feed test output as context, retry |
| Wrong file targeted | Validator reads result, doesn't match intent | Revert, re-run reader to find correct file |

**Why not the others:**
- **Unified diff:** LLMs produce malformed diffs ~15-20% of the time. One bad hunk offset and the patch silently misapplies.
- **Line-range replacement:** Edits earlier in the file shift line numbers for later edits. Requires offset tracking for no added benefit.
- **AST-based editing:** Ship has .ts, .tsx, .json, .css, .yaml, .md, .sh files. Building parsers for each is a week of work by itself.

---

## Phase 2: Architecture Design

### 3. System Diagram

```
User Instruction + Context
        |
        v
+---------------------+
| receive_instruction | <-- FastAPI POST /instruction
+---------+-----------+
          |
          v
+---------------------+
|      planner        | -- Breaks instruction into steps
+---------+-----------+    with dependency markers
          |
          v
+---------------------+     +-------------------+
|    coordinator      |---->|  Is multi-agent?  |
+---------+-----------+     +----+----------+---+
          |                      No         Yes
          v                      |          |
+------------------+             |    +-----v-----------+
|      reader      | <----------+    | Spawn subgraphs |
|   (read files)   |                 |  via Send API   |
+---------+--------+                 +---+----------+--+
          |                              |          |
          v                         Agent A     Agent B
+------------------+               (reader->    (reader->
|      editor      |                editor->     editor->
| (anchor-based)   |                validator)  validator)
+---------+--------+                   |          |
          |                            v          v
          v                      +--------------------+
+------------------+             |      merger        |
|    validator     |             | (conflict resolve) |
+-----+------+-----+            +---------+----------+
      |      |                             |
   pass    fail                            v
      |      |                   +------------------+
      |      v                   |    validator     |
      |  +------------+         +-----+------+-----+
      |  | error_     |            pass    fail
      |  | recovery   |              |      |
      |  +-----+------+              |      v
      |        | (retry <=3)         |    (same error
      |        v                     |     recovery)
      |      reader (re-read)        |
      |        |                     |
      v        v                     v
+------------------+        +------------------+
|    reporter      |        |    reporter      |
|  (summarize)     |        |  (summarize)     |
+------------------+        +------------------+
          |
          v
   +--------------+
   |    Output    | -- Status: completed / failed / waiting_for_human
   +--------------+

Error Branch (after 3 retries):
  validator (fail) -> reporter -> Status: waiting_for_human
  Human provides input via POST /instruction/{run_id} -> receive_instruction (resume)
```

### 4. File Editing Strategy — Mechanism

**Step-by-step:**
1. `reader` reads the target file, adds it to `file_buffer` in state
2. `planner` determines what needs to change and passes intent to `editor`
3. `editor` LLM call receives: file content, edit instruction, and produces `(anchor: str, replacement: str)`
4. Agent validates: `file_content.count(anchor) == 1` — if not, retry with request for longer anchor
5. Store snapshot: `edit_history.append({"file": path, "before": content})`
6. Apply: `new_content = content.replace(anchor, replacement)`
7. Write file to disk
8. `validator` re-reads the file and runs a language-appropriate syntax check:
   - `.ts`/`.tsx` → `npx tsc --noEmit --pretty` (or `esbuild --bundle --write=false` for speed)
   - `.js`/`.jsx` → `node --check`
   - `.json` → `python -m json.tool` or `node -e "JSON.parse(require('fs').readFileSync(f))"`
   - `.css` → `npx stylelint` (if available) or skip (CSS is forgiving)
   - `.yaml`/`.yml` → `python -c "import yaml; yaml.safe_load(open(f))"`
   - `.md`/`.sh` → skip syntax check, rely on intent verification only
9. If syntax fails → restore from snapshot, feed error to `editor`, retry (max 3)
10. If syntax passes → proceed to next step or run tests via `executor`

**When it gets the location wrong:**
The validator catches this — if the edit doesn't match the planner's intent (checked by a quick LLM verification), the edit is reverted and the `reader` re-runs to locate the correct file/section.

### 5. Multi-Agent Design

**Orchestration model:** LangGraph subgraphs via `Send` API

- `coordinator` node receives the task list from `planner`
- Tasks with `depends_on: []` are grouped into a parallel batch
- Each task spawns a subgraph containing: `reader → editor → validator`
- Subgraphs share read-only `file_buffer` from parent state
- Each subgraph writes to its own isolated `edit_log`
- `merger` node collects all edit logs and applies them:
  - Different files → apply all directly
  - Same file, different anchors → apply sequentially, re-validate after each
  - Same file, overlapping regions → flag to human

**For the Ship rebuild:** Two-agent split by package — one handles `api/`, one handles `web/`. The `shared/` package is handled sequentially first since both depend on it.

### 6. Context Injection Spec

**Types of context accepted:**

| Type | Format | Injection Point |
|------|--------|-----------------|
| Spec/PRD | Plain text or markdown | `planner` system prompt — guides task decomposition |
| Schema | JSON, OpenAPI YAML, TypeScript types | `reader` + `editor` prompts — ensures type-correct edits |
| Test results | Plain text (stdout/stderr) | `validator` → `editor` retry loop — drives fix attempts |
| Previous output | JSON (prior run summary) | `planner` — enables continuation across runs |
| File hints | List of file paths | `reader` — skips search, reads directly |

**Format:** All context arrives as a JSON object in the `POST /instruction` body under the `context` key. Each field is optional.

**When in the loop:** Context is loaded at `receive_instruction` and stored in `AgentState.context`. Each node reads the fields relevant to it. Context persists for the duration of the run but can be overwritten by the next instruction.

### 7. Context Injection — Additional Detail

The context injection system supports two modes:

1. **Upfront injection:** Context provided with the instruction. Used for specs, schemas, file hints.
2. **Runtime injection:** Context generated during execution. Test results from `executor` are automatically injected into the retry loop. File contents from `reader` become context for `editor`.

Context window budget: ~150K tokens total. Priority order when trimming:
1. Current instruction (always kept)
2. Injected spec/schema (always kept)
3. Current file contents (always kept)
4. Recent messages (last 20)
5. Older messages (summarized)
6. Previous file reads (evicted LRU)

### 8. Additional Tools

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read a file and return its contents with line numbers |
| `edit_file(path, anchor, replacement)` | Anchor-based surgical edit with snapshot and rollback |
| `list_files(directory, pattern)` | Glob-based file listing for codebase exploration |
| `search_content(pattern, path)` | Grep-based content search across files |
| `run_command(command, cwd)` | Execute a shell command and return stdout/stderr/exit code |
| `create_file(path, content)` | Create a new file (used for new features, not edits) |
| `delete_file(path)` | Delete a file with confirmation |

---

## Phase 3: Stack and Operations

### 9. Framework Choice

**LangGraph (Python)** for the agent loop and multi-agent coordination.

**Why:**
- Built-in state management with `StateGraph` and typed state schemas
- Subgraph support via `Send` API for parallel agent fan-out
- Native checkpointing with `SqliteSaver` for persistent loop state
- Automatic LangSmith tracing — every node, every tool call, every LLM invocation
- Conditional edges make error recovery and branching clean
- Mature Python ecosystem — well-documented, active development

**Why not alternatives:**
- LangChain (without LangGraph): No graph-based state management, harder to model the agent loop
- Custom Python loop: Would need to build state management, checkpointing, and tracing from scratch
- Node.js LangGraph: Less mature, weaker ecosystem for agent tooling

### 10. Persistent Loop

**Where it runs:** FastAPI server, local process (for MVP). Deployed for final submission.

**How it's kept alive:**
- FastAPI server runs as a long-lived process
- LangGraph `SqliteSaver` checkpointer persists graph state to disk
- Each instruction creates or continues a "thread" — a named checkpoint chain
- Between instructions, the server is idle but alive. No cold starts.
- If the server crashes, state is recovered from the last checkpoint on restart.

**API surface:**
- `POST /instruction` — new instruction (creates new thread or continues existing)
- `GET /status/{run_id}` — poll for completion
- `POST /instruction/{run_id}` — human intervention on a paused run

### 11. Token Budget

**Per invocation estimates:**

| Call | Input Tokens | Output Tokens |
|------|-------------|---------------|
| Planner | ~2,000 (instruction + context) | ~500 (task list) |
| Reader | ~1,000 (request) | ~100 (file path decisions) |
| Editor | ~4,000 (file content + instruction) | ~1,000 (anchor + replacement) |
| Validator | ~3,000 (file content + expected outcome) | ~200 (pass/fail + reason) |
| Coordinator | ~1,500 (task list + dependencies) | ~300 (assignment) |

**Typical single-edit run:** ~12,000 input + ~2,100 output ≈ 14,100 tokens

**Cost cliffs:**
- Files > 500 lines: File content dominates input tokens. Mitigation: read only relevant sections, not whole files.
- Retry loops: Each retry re-sends file content. 3 retries = 3x the editor cost. Mitigation: send only the changed region + error on retries.
- Multi-agent: Parallel subgraphs multiply cost linearly. Two agents = 2x. Mitigation: only parallelize when tasks are truly independent.

**Budget ceiling:** ~100K tokens per complex instruction (multi-file, multi-agent). Simple edits should stay under 20K.

### 12. Bad Edit Recovery

**Detection:**
1. Post-edit file re-read — does the file contain the expected change?
2. Language-appropriate syntax check — `npx tsc --noEmit` for TS/TSX, `node --check` for JS, `json.tool` for JSON, `yaml.safe_load` for YAML
3. Test execution — run relevant tests after edit
4. LLM verification — quick check: "does this edit match the intent?"

**Recovery:**
1. Restore file from pre-edit snapshot in `edit_history`
2. Feed the error (syntax error, test failure, intent mismatch) as context to the next `editor` call
3. Retry with more conservative edit (smaller change, more context)
4. After 3 failed retries, pause and surface to human with full error log

### 13. Logging — Complete Run Trace

A typical edit produces this trace (also visible in LangSmith):

```json
[
  {
    "timestamp": "2026-03-23T15:00:01Z",
    "node": "receive_instruction",
    "data": {
      "instruction": "Add a due_date field to the Issue model",
      "context": {"schema": "...", "files": ["api/src/models/issue.ts"]}
    }
  },
  {
    "timestamp": "2026-03-23T15:00:02Z",
    "node": "planner",
    "data": {
      "plan": [
        "1. Add due_date column to Issue model",
        "2. Update Issue TypeScript type in shared/",
        "3. Add due_date to issue creation API endpoint",
        "4. Add due_date input to issue form in web/"
      ],
      "tokens": {"input": 2100, "output": 480}
    }
  },
  {
    "timestamp": "2026-03-23T15:00:03Z",
    "node": "reader",
    "data": {
      "file": "api/src/models/issue.ts",
      "lines": 142,
      "tokens": {"input": 1050, "output": 85}
    }
  },
  {
    "timestamp": "2026-03-23T15:00:05Z",
    "node": "editor",
    "data": {
      "file": "api/src/models/issue.ts",
      "anchor": "  description: text('description'),\n  status: varchar('status', { length: 20 }),",
      "replacement": "  description: text('description'),\n  due_date: timestamp('due_date'),\n  status: varchar('status', { length: 20 }),",
      "anchor_unique": true,
      "snapshot_saved": true,
      "tokens": {"input": 4200, "output": 920}
    }
  },
  {
    "timestamp": "2026-03-23T15:00:06Z",
    "node": "validator",
    "data": {
      "file": "api/src/models/issue.ts",
      "syntax_check": "pass",
      "edit_matches_intent": true,
      "tokens": {"input": 3100, "output": 150}
    }
  },
  {
    "timestamp": "2026-03-23T15:00:06Z",
    "node": "reporter",
    "data": {
      "summary": "Added due_date timestamp column to Issue model",
      "status": "step_1_complete",
      "total_tokens": {"input": 10450, "output": 1635}
    }
  }
]
```

---

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph (Python) |
| LLM | Claude (Anthropic SDK) |
| Observability | LangSmith + local JSON traces |
| Backend | FastAPI |
| State Persistence | LangGraph SqliteSaver |
| Deployment | Local for MVP; deployed for final submission |
| Target Codebase | Ship (TypeScript/pnpm monorepo) |
| File Editing | Anchor-based replacement |

---

## Build Priority Order

1. Persistent loop — FastAPI + LangGraph graph with `receive_instruction` and checkpointing
2. Basic tool calls — `read_file` and `edit_file` working end-to-end
3. Surgical file editing — anchor-based strategy with validation and rollback
4. Context injection — accept and use external context in the loop
5. Multi-agent coordination — coordinator + subgraphs via Send API
6. Ship rebuild — direct the agent at the Ship codebase, document everything
7. Comparative analysis — write the full seven-section report
