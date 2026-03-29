# Phase 12: Orchestrator + DAG Engine + Contract Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 12-orchestrator-dag-engine-contract-foundation
**Areas discussed:** DAG storage & execution engine, Contract store design, Agent-to-orchestrator communication, Scope of MVP proof

---

## DAG Storage & Execution Engine

| Option | Description | Selected |
|--------|-------------|----------|
| NetworkX DAG + custom scheduler | Python standard graph library, topological sort built-in, custom async scheduler, SQLite persistence | ✓ |
| Build on LangGraph | Use StateGraph as DAG engine, gets checkpointing free, but designed for linear flows not 100+ node DAGs | |
| Celery/Dramatiq task queue | Production distributed execution, needs Redis/RabbitMQ, overkill for single-machine | |
| Custom DAG from scratch | Dict of tasks with deps, topological sort, asyncio pool, no dependencies, more code | |

**User's choice:** NetworkX DAG + custom scheduler
**Notes:** Mature library, no new infrastructure, topological sort built-in. Custom scheduler handles async worker pool and SQLite state persistence.

---

## Contract Store Design

| Option | Description | Selected |
|--------|-------------|----------|
| Git-tracked files | Contracts as .json/.yaml/.sql in contracts/ directory, versioned through git history, diffable | ✓ |
| SQLite tables | Contracts as rows with version numbers, faster lookups, less human-readable | |
| Hybrid | Files on disk + SQLite index/metadata layer for querying versions | |

**User's choice:** Git-tracked files
**Notes:** Simple, transparent, agents treat them like any other file. Git provides version history naturally.

---

## Agent-to-Orchestrator Communication

| Option | Description | Selected |
|--------|-------------|----------|
| Event bus (extend existing) | Extend EventBus with task lifecycle events, reuses P0/P1/P2 and WebSocket streaming | ✓ |
| Return values only | Agents as async functions returning result dicts, simpler but no real-time visibility | |
| Shared state in SQLite | Agents write status to DB, orchestrator polls, decoupled but adds latency | |

**User's choice:** Event bus (extend existing)
**Notes:** Natural extension of existing infrastructure. Already has priority routing and frontend streaming.

---

## Scope of MVP Proof

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded test DAG | 5-10 manual tasks with dependencies, real agents writing files, proves all moving parts | ✓ |
| Single-file rebuild | Point at tiny app, requires planning logic from Phase 13 | |
| DAG dry-run mode | Simulate execution, log ordering, no actual code generation | |

**User's choice:** Hardcoded test DAG
**Notes:** Proves scheduling, persistence, resume, contracts, and event bus without bleeding into Phase 13 analyzer/planner work. Real agents write real files — not just simulation.

---

## Claude's Discretion

- SQLite schema design for DAG state tables
- NetworkX integration details
- Worker pool implementation
- Contract file structure and naming
- EventBus event type definitions

## Deferred Ideas

- Analyzer/planner agents (Phase 13)
- Failure classification A/B/C/D (Phase 15)
- DAG visualization in frontend (Phase 14)
- Module ownership model (Phase 15)
