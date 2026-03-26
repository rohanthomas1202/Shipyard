# Shipyard

## What This Is

Shipyard is an autonomous AI coding agent that takes natural language instructions and plans, edits, validates, and commits code changes across multiple files without human intervention. Built as a Python/LangGraph agent with a FastAPI server and React frontend, it targets developers who want to automate multi-file code changes with surgical precision and full observability. This is a Gauntlet AI project — the agent must prove itself by rebuilding the Ship app from scratch.

## Core Value

The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

## Requirements

### Validated

<!-- Inferred from existing codebase — architecture exists but reliability unproven -->

- ~ LangGraph state graph with 11 nodes orchestrating plan-read-edit-validate-commit pipeline — existing (architecture works, reliability needs hardening)
- ~ FastAPI server with REST + WebSocket endpoints for frontend communication — existing
- ~ React frontend with glassmorphic IDE-style UI (project picker, run progress, diff viewer, settings) — existing
- ~ SQLite persistence for projects, runs, events, edits — existing
- ~ Tiered LLM routing with OpenAI models (o3/gpt-4o/gpt-4o-mini) and auto-escalation — existing
- ~ Supervised edit approval state machine with human-in-the-loop gates — existing
- ~ Real-time WebSocket streaming with priority routing (P0/P1/P2) and reconnect replay — existing
- ~ ast-grep structural code rewrites via refactor node — existing
- ~ LSP integration for TypeScript diagnostic diffing (baseline vs post-edit) — existing (recent work)

### Active

- [ ] Agent runs in a persistent loop accepting new instructions without restarting
- [ ] Surgical file editing produces correct, targeted changes without rewriting entire files
- [ ] Editor anchor-based replacement reliably locates correct blocks in files >200 lines
- [ ] Validator catches real errors and doesn't flag false positives (LSP + esbuild + syntax checks)
- [ ] Validator rollback + retry (3 attempts) recovers from bad edits
- [ ] Planner correctly decomposes natural language instructions into typed PlanSteps
- [ ] Multi-agent coordination: spawn and coordinate parallel/sequential agents, merge outputs
- [ ] Context injection: accept external context (specs, schemas, test results) at runtime and use in generation
- [ ] LangSmith tracing enabled with at least two shared trace links showing different execution paths
- [ ] Git operations: branch, commit, push, PR creation work end-to-end
- [ ] Server handles WebSocket drops, reconnects, and run resumption gracefully
- [ ] Ship app rebuild: agent successfully rebuilds the Ship app from scratch with minimal intervention
- [ ] Comparative analysis: 7-section structured report comparing agent-built Ship vs original
- [ ] Deploy to Heroku/Railway — both agent and agent-built Ship app publicly accessible
- [ ] CODEAGENT.md complete with all sections (architecture, file editing strategy, multi-agent design, trace links, decisions, rebuild log, comparative analysis, cost analysis)
- [ ] AI Development Log submitted (tools, prompts, code analysis, learnings)
- [ ] AI Cost Analysis with dev spend tracking and production cost projections (100/1K/10K users)
- [ ] Demo video (3-5 min) showing surgical edit, multi-agent task, and Ship rebuild example

### Out of Scope

- Authentication/authorization on the API — single-user tool, unnecessary for v1
- Multiple LLM provider support (Claude SDK) — unlimited OpenAI tokens, no business need to switch
- Mobile UI — desktop browser is the only target
- Real-time collaboration — single-user agent
- Custom plugin/extension system — hardcoded pipeline sufficient for v1

## Context

- **Project type:** Gauntlet AI weekly project with submission deadlines (MVP, Early, Final)
- **Existing codebase:** ~11 agent nodes, FastAPI server, React frontend already built but unreliable
- **The integration test:** Rebuild the Ship app using Shipyard — every shortcoming surfaces here
- **Key insight from PDF:** "A focused agent that surgical edits and runs continuously beats a feature-rich agent that rewrites files and crashes"
- **Critical guidance:** Get surgical editing working completely before multi-agent. Test against files >200 lines. Document every intervention during Ship rebuild. Add tracing early. No mocking.
- **Architecture already chosen:** LangGraph, anchor-based string replacement, tiered OpenAI routing
- **Recent work:** LSP manager for TypeScript server lifecycle and diagnostic diffing to reduce false positives in validation
- **Known pain points:** Edit quality (bad anchors, partial replacements), validation gaps (false positives/negatives), planner misunderstanding intent, infra crashes (WebSocket drops, hanging runs)
- **ContextAssembler exists but not wired in:** `agent/context.py` has ranked priority context filling but nodes build prompts directly — this is the context injection gap

## Constraints

- **LLM Provider:** OpenAI (o3/gpt-4o/gpt-4o-mini) — unlimited tokens available, no budget constraint
- **Deployment:** Heroku/Railway PaaS — single-process uvicorn, SQLite file DB, static frontend from web/dist/
- **Runtime:** Python 3.11 + Node.js — pinned in runtime.txt
- **Framework:** LangGraph 1.1.3 — committed, not switching
- **File editing:** Anchor-based string replacement — committed, not switching (per PDF: "switching strategies mid-week is a planning failure")
- **Observability:** LangSmith tracing required — env vars already configured
- **Demo target:** Ship app rebuild must work flawlessly for the demo video

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph for orchestration | Built-in state management, retry, human-in-the-loop, LangSmith tracing | — Pending |
| Anchor-based editing over unified diff/AST | More robust than line numbers, less complex than AST, LLM can generate anchors reliably | — Pending |
| OpenAI over Claude | Unlimited tokens available, already integrated, no cost constraints | — Pending |
| Tiered model routing | o3 for planning (needs reasoning), gpt-4o for edits (needs precision), gpt-4o-mini for classify/validate (needs speed) | — Pending |
| SQLite over Postgres | Single-user, local-first, zero config, sufficient for demo scale | — Pending |
| Priority event streaming (P0/P1/P2) | Approvals need immediate delivery, token streams can batch, status updates can queue | — Pending |
| LSP diagnostic diffing | Baseline vs post-edit comparison prevents flagging pre-existing errors as edit failures | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-26 after initialization*
