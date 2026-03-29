# Shipyard

## What This Is

Shipyard is an autonomous AI coding agent that takes natural language instructions and plans, edits, validates, and commits code changes across multiple files without human intervention. Built as a Python/LangGraph agent with a FastAPI server and React frontend, it features surgical anchor-based editing, 3-tier fuzzy matching, circuit-breaker validation, crash recovery, and parallel agent execution. The frontend is a VS Code-style three-panel IDE with live file explorer, syntax-highlighted diff viewer, and real-time agent activity stream. Proven by rebuilding the Ship app from scratch.

## Core Value

The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

## Requirements

### Validated

- ✓ LangGraph state graph with 11 nodes orchestrating plan-read-edit-validate-commit pipeline — v1.0
- ✓ FastAPI server with REST + WebSocket endpoints for frontend communication — v1.0
- ✓ React frontend with initial UI — v1.0
- ✓ SQLite persistence with WAL mode for projects, runs, events, edits — v1.0
- ✓ Tiered LLM routing with OpenAI models (o3/gpt-4o/gpt-4o-mini) and auto-escalation — v1.0
- ✓ Supervised edit approval state machine with human-in-the-loop gates — v1.0
- ✓ Real-time WebSocket streaming with priority routing (P0/P1/P2) and reconnect replay — v1.0
- ✓ ast-grep structural code rewrites via refactor node — v1.0
- ✓ LSP integration for TypeScript diagnostic diffing with timeout fallback — v1.0
- ✓ Surgical file editing with 3-tier fuzzy anchor matching and indentation preservation — v1.0 (Phase 1)
- ✓ Structured LLM outputs via EditResponse with retry feedback loop — v1.0 (Phase 1)
- ✓ Python syntax checking via ast.parse and LSP fallback hardening — v1.0 (Phase 2)
- ✓ Circuit breaker stops retrying identical validation errors — v1.0 (Phase 2)
- ✓ Async infrastructure (no blocking subprocess.run in agent nodes) — v1.0 (Phase 2)
- ✓ Token tracking with cost estimation and model-aware context budgets — v1.0 (Phase 3)
- ✓ ContextAssembler with skeleton views for large files — v1.0 (Phase 3)
- ✓ Crash recovery via LangGraph checkpointing with automatic resume — v1.0 (Phase 4)
- ✓ Run cancellation with snapshot-based edit rollback — v1.0 (Phase 4)
- ✓ LangSmith shared trace links — v1.0 (Phase 4)
- ✓ Context injection (spec, schema, test_results, extra) through all LLM nodes — v1.0 (Phase 5)
- ✓ Auto-git pipeline (reporter -> branch -> stage -> commit -> push) — v1.0 (Phase 5)
- ✓ Parallel batch execution via asyncio.gather with conflict detection — v1.0 (Phase 5)
- ✓ Ship rebuild orchestration with 5 graduated instructions — v1.0 (Phase 6)
- ✓ Integration tests with Ship-like fixtures — v1.0 (Phase 6)
- ✓ CODEAGENT.md with all 8 sections populated — v1.0 (Phase 7)
- ✓ AI Development Log and demo video script — v1.0 (Phase 7)

### Active

- [ ] DAG-based orchestrator that decomposes complex apps into spec-driven task graphs
- [ ] Analyzer agent that parses codebases into module maps with dependency graphs
- [ ] Planner agent with three-layer decomposition (PRD → Tech Spec → Task DAG)
- [ ] Versioned contract layer (DB schema, OpenAPI, shared types) as source of truth
- [ ] Bounded parallel execution (5-15 agents, ≤300 LOC / ≤3 files per task)
- [ ] Failure classification system (syntax→auto-fix, contract→spec, test→debug, structural→replan)
- [ ] CI engine maintaining always-working main branch after every merge
- [ ] Module ownership model preventing cross-agent conflicts
- [ ] Checkpointing and recovery for long-running multi-agent builds
- [ ] Ship rebuild proof — 47 API routes, core E2E flows, deployed to public URL

### Validated in v1.1

- ✓ VS Code-style three-panel IDE layout (file explorer | code/diff | agent stream) — v1.1 (Phase 8)
- ✓ Top bar with instruction input, project selector, run status indicator — v1.1 (Phase 8)
- ✓ Zustand state architecture preventing WebSocket render storms — v1.1 (Phase 8)
- ✓ Live file explorer with real-time M/A/D indicators — v1.1 (Phase 9)
- ✓ Lazy-loaded directory tree with gitignore filtering — v1.1 (Phase 9)
- ✓ Backend /browse and /files endpoints with path traversal protection — v1.1 (Phase 9)
- ✓ Side-by-side diff view with jsdiff line-level algorithm and Shiki highlighting — v1.1 (Phase 10)
- ✓ Tabbed editor with VS Code-style preview/pin behavior — v1.1 (Phase 10)
- ✓ Real-time agent activity stream with auto-scroll and new-event badge — v1.1 (Phase 11)

### Out of Scope

- Authentication/authorization on the API — single-user tool, unnecessary for v1
- Multiple LLM provider support (Claude SDK) — unlimited OpenAI tokens, no business need to switch
- Mobile UI — desktop browser is the only target
- Real-time collaboration — single-user agent
- Custom plugin/extension system — hardcoded pipeline sufficient for v1

## Current Milestone: v1.2 Autonomous Software Factory

**Goal:** Build a spec-driven, DAG-orchestrated multi-agent system proven by rebuilding Ship (133K LOC) end-to-end.

**Target features:**
- Analyzer agent — module map, dependency graph, per-module summaries
- Planner agent — PRDs → Tech Specs → Task DAG with plan validation phase
- Contract layer — versioned DB schema, OpenAPI, shared types, migration strategy
- Execution layer — 5-15 concurrent agents, context packs ≤5 files, git branch+PR per agent
- Validation layer — CI after every task, failure classification (A/B/C/D types)
- CI engine — always-working main branch, rejects unstable PRs, mock services for external deps
- Orchestrator — owns DAG, failure-type retries, structured logging, observability
- Ownership model — designated owner per module, orchestrator-mediated cross-module changes
- Checkpointing — persist DAG state, resume from failure, re-run failed branches
- Progress metrics — tasks completed, DAG coverage %, CI pass rate, scale gates
- Automated deployment scripts for Ship rebuild proof

**Build order:** Orchestrator+DAG → Planner+specs → CI+validation → Full Ship rebuild

## Current State

Phase 12 complete — DAG-based orchestrator foundation delivered with task engine, contract store, async scheduler, SQLite persistence, and FastAPI endpoints. 42 tests passing.
Shipped v1.0 (agent core) and v1.1 (IDE UI rebuild) on 2026-03-27.

## Context

Shipped with ~5,900 LOC Python + ~5,400 LOC TypeScript.
Tech stack: Python 3.11, LangGraph 1.1.3, FastAPI, React 19, Zustand, SQLite, OpenAI.
11 phases completed across 30 plans (2026-03-23 → 2026-03-27).
v1.0 delivered agent core: edit reliability, validation, crash recovery, parallel execution.
v1.1 delivered IDE frontend: three-panel layout, file explorer, diff viewer, activity stream.

### Known Tech Debt (from v1.1 audit)
- ProjectPicker filesystem browse broken (Phase 9 `/browse` requires `project_id`)
- Dead code: `AppShell.tsx`, `DiffViewer.tsx` (replaced by `IDELayout`, `SideBySideDiff`)
- ESLint warning in `FileTree.tsx`
- Gitignore filtering uses static blocklist, not `.gitignore` parsing

## Constraints

- **LLM Provider:** OpenAI (o3/gpt-4o/gpt-4o-mini) — unlimited tokens available, no budget constraint
- **Deployment:** Heroku/Railway PaaS — single-process uvicorn, SQLite file DB, static frontend from web/dist/
- **Runtime:** Python 3.11 + Node.js — pinned in runtime.txt
- **Framework:** LangGraph 1.1.3 — committed, not switching
- **File editing:** Anchor-based string replacement — committed, not switching
- **Observability:** LangSmith tracing required — env vars already configured
- **Demo target:** Ship app rebuild must work flawlessly for the demo video

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph for orchestration | Built-in state management, retry, human-in-the-loop, LangSmith tracing | ✓ Good — state graph worked reliably across 11 nodes |
| Anchor-based editing over unified diff/AST | More robust than line numbers, less complex than AST, LLM can generate anchors reliably | ✓ Good — 3-tier fuzzy matching resolved anchor failures |
| OpenAI over Claude | Unlimited tokens available, already integrated, no cost constraints | ✓ Good — o3 reasoning tier excellent for planning |
| Tiered model routing | o3 for planning, gpt-4o for edits, gpt-4o-mini for classify/validate | ✓ Good — auto-escalation catches edge cases |
| SQLite over Postgres | Single-user, local-first, zero config, sufficient for demo scale | ✓ Good — WAL mode eliminated write contention |
| Priority event streaming (P0/P1/P2) | Approvals need immediate delivery, token streams can batch | ✓ Good — responsive UI |
| LSP diagnostic diffing | Baseline vs post-edit comparison prevents flagging pre-existing errors | ✓ Good — 30s timeout fallback prevents hangs |
| Circuit breaker (threshold=2) | Stop wasting tokens on identical unfixable errors | ✓ Good — normalized error comparison works |
| Separate auto_git from plan-step git_ops | Avoid cycle in graph edges | ✓ Good — conditional reporter->auto_git edge clean |
| Duplicate _normalize_error in graph.py and validator.py | Avoid circular imports | ⚠️ Revisit — consider shared utils module |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-29 after Phase 12 completion — orchestrator DAG engine + contract foundation*
