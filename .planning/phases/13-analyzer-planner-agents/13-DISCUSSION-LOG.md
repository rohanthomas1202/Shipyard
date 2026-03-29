# Phase 13: Analyzer + Planner Agents - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 13-analyzer-planner-agents
**Areas discussed:** Analyzer output format, Planner decomposition, Task bounding rules, Test target strategy

---

## Analyzer Output Format

### Module Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Directory-based (Recommended) | Each top-level directory = module. Fast, deterministic. | |
| Import-graph based | Trace imports to discover clusters. More accurate but slower. | |
| Hybrid | Directory-based initial structure, then LLM enrichment per module. | ✓ |

**User's choice:** Hybrid
**Notes:** None

### Module Map Contents

| Option | Description | Selected |
|--------|-------------|----------|
| Lean map (Recommended) | Name, file list, exports, dependency edges, 1-sentence summary. | |
| Rich map | Lean map + per-file function signatures, class hierarchies, LOC counts. | |
| Tiered map | Lean map for all, rich detail only for Planner-flagged complex modules. | ✓ |

**User's choice:** Tiered map
**Notes:** Two-pass approach — Planner requests enrichment for complex modules.

### Dependency Representation

| Option | Description | Selected |
|--------|-------------|----------|
| Import edges only (Recommended) | Static import/require analysis. Deterministic. | ✓ |
| Import + runtime edges | Static imports plus LLM-inferred runtime dependencies. | |
| Weighted edges | Import edges with coupling strength metrics. | |

**User's choice:** Import edges only (Recommended)
**Notes:** None

### Output Format

| Option | Description | Selected |
|--------|-------------|----------|
| Single JSON (Recommended) | One module-map.json with all modules, edges, summaries. | ✓ |
| Per-module files | analysis/{module}.json for each module + index.json. | |
| Both | Per-module files + merged summary JSON. | |

**User's choice:** Single JSON (Recommended)
**Notes:** None

---

## Planner Decomposition

### Pipeline Design

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential single-pass (Recommended) | PRD → Tech Spec → Task DAG, one LLM call per layer. | ✓ |
| Iterative refinement | Each layer validates and loops back for fixes. | |
| Parallel then merge | Generate PRDs in parallel, merge into one DAG. | |

**User's choice:** Sequential single-pass (Recommended)
**Notes:** None

### Validation Gates

| Option | Description | Selected |
|--------|-------------|----------|
| Structural validation only (Recommended) | Check DAG acyclic, valid contracts, coverage, bounds. | ✓ |
| Structural + LLM review | Structural plus LLM reviewing decomposition quality. | |
| Structural + cost gate | Structural plus token/cost estimation with approval threshold. | |

**User's choice:** Structural validation only (Recommended)
**Notes:** None

### LLM Tier

| Option | Description | Selected |
|--------|-------------|----------|
| o3 for all layers (Recommended) | Reasoning tier for all three pipeline stages. | ✓ |
| Tiered by layer | o3 for PRD, gpt-4o for Tech Spec, gpt-4o-mini for DAG. | |
| o3 with gpt-4o fallback | o3 first, fall back on timeout/failure. | |

**User's choice:** o3 for all layers (Recommended)
**Notes:** Cost is irrelevant per project constraints.

### Artifact Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Git-tracked markdown (Recommended) | PRDs and Tech Specs as .md files in plans/ directory. | ✓ |
| In-memory only | Exist only as LLM context between stages. | |
| JSON in SQLite | Structured JSON in DAG state tables. | |

**User's choice:** Git-tracked markdown (Recommended)
**Notes:** None

---

## Task Bounding Rules

### Enforcement Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Hard reject (Recommended) | Validation rejects any task exceeding bounds. | |
| Soft warning | Log warning but allow oversized tasks. | |
| Hard with escape hatch | Hard reject, but Planner can mark tasks "indivisible" with justification. | ✓ |

**User's choice:** Hard with escape hatch
**Notes:** Rare exceptions for tightly coupled code.

### LOC Estimation

| Option | Description | Selected |
|--------|-------------|----------|
| LLM estimation (Recommended) | o3 estimates LOC based on Tech Spec description. | ✓ |
| Reference-based estimation | Compare to existing similar code in module map. | |
| Fixed heuristic | Average LOC per task type. | |

**User's choice:** LLM estimation (Recommended)
**Notes:** None

---

## Test Target Strategy

### Ship Repo Access

| Option | Description | Selected |
|--------|-------------|----------|
| Fixture subset (Recommended) | Representative 5-10 file fixture mimicking Ship structure. | ✓ |
| Clone Ship repo | Clone actual Ship repo as test target. | |
| Both | Fixture for unit tests, Ship clone for E2E smoke test. | |

**User's choice:** Fixture subset (Recommended)
**Notes:** None

### Fixture Design

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal Ship-like (Recommended) | 5-10 files: 2 Express routes, 1 Prisma schema, 2 React components, 1 shared type. | ✓ |
| Realistic Ship subset | 15-20 files covering Ship's main patterns. | |
| Shipyard itself | Use Shipyard's own codebase as test target. | |

**User's choice:** Minimal Ship-like (Recommended)
**Notes:** None

---

## Claude's Discretion

- Analyzer prompt engineering for module summarization
- Module map JSON schema design
- PRD and Tech Spec markdown template structure
- How Planner invokes Analyzer's enrichment pass for complex modules
- Validation error message format and reporting
- Cost estimation formula for validation gate

## Deferred Ideas

- Failure classification system A/B/C/D (Phase 15)
- Module ownership model (Phase 15)
- Contract backward compatibility (Phase 14)
- DAG visualization in frontend (Phase 14)
- Using Shipyard codebase as secondary test target
