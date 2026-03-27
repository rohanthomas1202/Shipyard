# Phase 6: Ship Rebuild - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Use the Shipyard agent to rebuild/extend the Ship app, document every intervention, and prove the agent works on a real codebase. The Ship app is a pnpm monorepo with Express API + React frontend + shared types at ship-rebuild/.

</domain>

<decisions>
## Implementation Decisions

### Rebuild Strategy
- Direct Shipyard at the ship-rebuild/ directory with natural language instructions
- Start with simpler tasks (add a field, modify a route) and escalate to complex ones (add a feature, refactor a module)
- Document every intervention: what broke, what the agent did wrong, what was done manually
- Track success rate: instructions that completed without intervention vs those that needed help

### Ship App Structure
- Monorepo: api/ (Express + TypeScript), web/ (React + Vite + Tailwind), shared/ (types)
- Package manager: pnpm
- Database: likely PostgreSQL or SQLite
- Build: pnpm --recursive run build

### Claude's Discretion
- Choice of rebuild tasks (must demonstrate surgical edits, multi-agent coordination, and error recovery)
- Order of instructions given to the agent
- How to handle agent failures

</decisions>

<code_context>
## Existing Code Insights

### Ship App Assets
- `ship-rebuild/api/src/` — Express routes, services, middleware, DB, types
- `ship-rebuild/web/src/` — React components, Vite, Tailwind
- `ship-rebuild/package.json` — pnpm monorepo root

### Shipyard Agent Entry Points
- POST /instruction — send instruction to agent
- WebSocket /ws/{project_id} — monitor progress
- GET /status/{run_id} — check run status

</code_context>

<specifics>
## Specific Ideas

Demo tasks for the rebuild:
1. Simple: Add a field to an API model and update the route handler
2. Medium: Add a new API endpoint with validation and tests
3. Complex: Add a feature across API + web (e.g., add filtering to a list view)
4. Multi-agent: Two parallel edits in different directories

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
