# Phase 15: Execution Engine + CI Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 15-execution-engine-ci-validation
**Areas discussed:** Branch Isolation + PR Strategy, Context Packs + Module Ownership, Failure Classification + Retry Strategy, CI Gate + Main Branch Protection
**Mode:** --batch (all questions presented simultaneously)

---

## Branch Isolation + PR Strategy

### Q1: Branch naming and lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Per-task branches, auto-merge after CI pass | Clean isolation — each task gets agent/task-{id}, CI runs, merges on green | ✓ |
| Per-task branches, accumulate into module branch | Extra layer of aggregation before main | |
| Per-agent branches reused across tasks | Agent keeps one branch across multiple tasks | |

**User's choice:** Per-task branches, auto-merge after CI pass
**Notes:** "Clean isolation — each task gets agent/task-{id}, CI runs, merges to main on green. No accumulation branches adding complexity."

### Q2: PR mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Real GitHub PRs via httpx | Uses existing agent/github.py | |
| Local git branch + merge simulation | No GitHub dependency | ✓ |

**User's choice:** Local git branch + merge
**Notes:** "Real GitHub PRs add network latency and API rate limits for every task in a 100+ task DAG. Local branches give you the same isolation and merge semantics without the dependency. You can always add real PRs later for human-reviewed milestones."

### Q3: Merge conflict handling

| Option | Description | Selected |
|--------|-------------|----------|
| Fail the later agent, requeue with updated base | Simple, deterministic | ✓ |
| LLM-assisted merge (o3 resolves conflicts) | Flexible but unpredictable | |
| Lock files during agent execution | Prevents conflicts but kills parallelism | |

**User's choice:** Fail-and-requeue
**Notes:** "LLM merge is unpredictable, file locking kills parallelism. Fail-and-requeue is simple, deterministic, and the DAG scheduler already handles requeueing. The requeued agent gets a fresh base with the conflicting changes already merged — clean resolution."

---

## Context Packs + Module Ownership

### Q4: Context pack assembly

| Option | Description | Selected |
|--------|-------------|----------|
| Static from task definition | Planner picks files | |
| Dynamic based on module map + import graph | Analyzer enriches at execution time | |
| Hybrid — Planner picks primary, Analyzer adds transitive | Best of both | ✓ |

**User's choice:** Hybrid
**Notes:** "Planner picks primary files (it knows the task intent), Analyzer adds transitive dependencies from the import graph (it knows the module structure). Neither alone is sufficient."

### Q5: Ownership enforcement mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Hard enforcement — filesystem sandboxing | Cannot write outside owned paths | |
| Soft enforcement — validator rejects unauthorized changes | Writes freely, validator checks diff | ✓ |
| Contract-based — self-policing via instructions | LLMs follow ownership constraints | |

**User's choice:** Soft enforcement via validator
**Notes:** "Hard filesystem sandboxing is complex to implement for marginal benefit. Contract-based self-policing is unreliable — LLMs don't reliably follow constraints. Validator rejection is the sweet spot: simple, reliable, debuggable."

---

## Failure Classification + Retry Strategy

### Q6: Classification method

| Option | Description | Selected |
|--------|-------------|----------|
| Rule-based — regex patterns on error output | Fast, deterministic | |
| LLM-classified — gpt-4o-mini categorizes | Flexible, handles novel errors | |
| Hybrid — rule-based first, LLM fallback | Matches ModelRouter pattern | ✓ |

**User's choice:** Hybrid
**Notes:** "Rule-based catches the common patterns fast. LLM fallback handles novel/ambiguous errors. This matches your existing ModelRouter pattern — try the cheap thing first, escalate when needed."

### Q7: Retry budget

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed: 2 retries per failure type | Simple, uniform | |
| Tiered: 3/2/1 by failure type | Matches fix probability | ✓ |

**User's choice:** Tiered
**Notes:** "Syntax errors are usually trivial to auto-fix (3 retries). Test failures may need a different approach (2 retries). Contract/structural failures indicate a planning problem — 1 retry then escalate."

---

## CI Gate + Main Branch Protection

### Q8: CI runner architecture

| Option | Description | Selected |
|--------|-------------|----------|
| In-process subprocess calls | Works but lacks structure | |
| GitHub Actions on PR creation | External dependency and latency | |
| Local CI runner module — structured pipeline | Proper stage tracking, feeds heatmap | ✓ |

**User's choice:** Local CI runner module
**Notes:** "Structured pipeline definition (typecheck -> lint -> test -> build) with stage-level pass/fail reporting that feeds into the failure heatmap. Subprocess-based but with proper stage tracking."

### Q9: Main branch merge policy

| Option | Description | Selected |
|--------|-------------|----------|
| Fast-forward only — rebase on latest main | Linear history, true CI state | ✓ |
| Merge commits — standard merge | Diamond history | |
| Squash merge — one commit per task | Loses intermediate granularity | |

**User's choice:** Fast-forward only
**Notes:** "Each task rebases on latest main before merge. Guarantees linear history, every CI run reflects true state, easier to bisect."

---

## Claude's Discretion

- Branch naming convention details
- Context pack file selection algorithm
- Failure classification regex patterns
- CI pipeline stage ordering and timeouts
- Rebase-on-main integration with scheduler queue
- Ownership map data structure
- CI runner result reporting to EventBus

## Deferred Ideas

None — discussion stayed within phase scope.
