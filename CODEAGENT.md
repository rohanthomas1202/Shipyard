# CODEAGENT.md

## Agent Architecture (MVP)

Shipyard uses a single LangGraph StateGraph with the following nodes wired in sequence:

`receive_instruction → planner → coordinator → [reader → editor → validator] (loop per step) → reporter`

**State:** `AgentState` TypedDict with messages, instruction, working_directory, context, plan, current_step, file_buffer, edit_history, error_state, is_parallel, parallel_batches, sequential_first, has_conflicts.

**Entry condition:** POST /instruction with instruction + optional context
**Normal exit:** All plan steps completed, validator passes on each
**Error exit:** 3 consecutive failures on same step → reporter surfaces status `waiting_for_human`

**Loop design:** FastAPI server keeps the graph alive. New instructions create or continue threads. Between instructions, server is idle but alive.

## File Editing Strategy (MVP)

**Strategy:** Anchor-based replacement (same pattern as Claude Code and OpenCode)

**Mechanism:**
1. Reader loads target file into file_buffer
2. Editor LLM produces (anchor, replacement) JSON
3. Agent validates anchor uniqueness: `file_content.count(anchor) == 1`
4. Snapshot saved to edit_history
5. `content.replace(anchor, replacement, 1)` applied
6. Validator runs language-appropriate syntax check (.ts → esbuild, .json → json.load, .yaml → yaml.safe_load)
7. If syntax fails → rollback from snapshot, retry with error context (max 3)

**When it gets the location wrong:** Validator detects intent mismatch, rollback triggers, reader re-runs to find correct file.

## Multi-Agent Design (MVP)

**Orchestration:** Coordinator node groups plan steps by directory prefix (api/, web/, shared/). Steps targeting different directories can run as parallel subgraphs. shared/ always runs first (dependency).

**Communication:** Subgraphs don't communicate directly. Each writes to isolated edit_log. Merger collects all logs and checks for file conflicts.

**Conflict resolution:** Different files → merge directly. Same file, different anchors → apply sequentially. Overlapping regions → flag to human.

## Trace Links (MVP)

- Trace 1 (normal run): _to be filled after first successful run_
- Trace 2 (error/recovery path): _to be filled after first error recovery run_

## Architecture Decisions (Final Submission)

_To be filled after Ship rebuild._

## Ship Rebuild Log (Final Submission)

_To be filled during Ship rebuild._

## Comparative Analysis (Final Submission)

_To be filled after Ship rebuild._

## Cost Analysis (Final Submission)

| Item | Amount |
|------|--------|
| Claude API — input tokens | |
| Claude API — output tokens | |
| Total invocations during development | |
| Total development spend | |

| 100 Users | 1,000 Users | 10,000 Users |
|-----------|-------------|--------------|
| $___/month | $___/month | $___/month |

**Assumptions:**
- Average agent invocations per user per day:
- Average tokens per invocation (input / output):
- Cost per invocation:
