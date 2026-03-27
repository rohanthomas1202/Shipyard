# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Agent Core MVP

**Shipped:** 2026-03-27
**Phases:** 7 | **Plans:** 21 | **Tasks:** 37

### What Was Built
- 3-tier fuzzy anchor matching with indentation preservation for reliable surgical editing
- Circuit-breaker validation with Python syntax checking and LSP fallback hardening
- Token-budgeted context assembly with skeleton views for large files
- Crash recovery via LangGraph checkpointing with automatic resume on server restart
- Auto-git pipeline (reporter -> branch -> stage -> commit -> push) with parallel batch execution
- Ship rebuild orchestration with 5 graduated instructions and intervention tracking
- Complete CODEAGENT.md, AI Development Log, and demo video script

### What Worked
- Dependency-ordered phasing: edit reliability first, then validation, then context, then recovery — each phase built on solid foundations
- Parallel executor agents in worktrees: 2 plans executed simultaneously without interference
- GSD workflow: structured planning with must_haves and key_links caught integration gaps early
- Brownfield approach: hardening existing code was more effective than rewriting

### What Was Inefficient
- Merge conflicts from parallel worktree execution required manual resolution of STATE.md, graph.py, and git_ops.py — agents had stale views of main
- Phase execution order (2 and 5 finished last despite being lower-numbered) caused confusing state tracking
- Test assertion mismatch in git_ops_e2e (project_id in branch name) was a spec ambiguity that surfaced late in verification
- DELIV requirements (documentation/deployment) were planned in Phase 7 but some remain unfulfilled — deliverables need their own milestone

### Patterns Established
- `_normalize_error()` pattern for deduplicating validation errors across retries
- `asyncio.wait_for(timeout=30)` as outer safety net around LSP calls
- `ContextAssembler.add_file()` with priority tiers for token-budgeted prompts
- Conditional graph edges (reporter -> auto_git) for post-run automation

### Key Lessons
1. Parallel worktree agents need a merge strategy — STATE.md conflicts are near-guaranteed when 2+ agents update it
2. Circuit breaker threshold=2 is right — catches genuine unfixable errors without being too aggressive
3. Documentation deliverables should be scoped separately from code — they have different completion criteria
4. Fuzzy matching with 0.85 threshold balances anchor recall vs false positive risk well

### Cost Observations
- Model mix: ~70% opus (planning/execution), ~25% sonnet (verification), ~5% haiku (research)
- Sessions: ~10 across 5 days
- Notable: Parallel agent execution saved ~40% wall-clock time on multi-plan waves

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~10 | 7 | Initial milestone — established GSD workflow with wave-based parallel execution |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 48+ | ~60% (agent core) | 7 (ast, re, asyncio, json, hashlib, logging, dataclasses) |

### Top Lessons (Verified Across Milestones)

1. Dependency-ordered phasing prevents cascading rework — always validate foundations first
2. Parallel agent execution trades merge complexity for speed — worth it for independent plans
