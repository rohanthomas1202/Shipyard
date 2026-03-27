---
phase: 10-code-diff-viewing
plan: 02
subsystem: ui
tags: [react, jsdiff, shiki, diff-viewer, side-by-side, syntax-highlighting]

requires:
  - phase: 10-code-diff-viewing
    provides: TabBar, EditorArea tab routing, Shiki highlighter singleton, workspaceStore with openDiff
provides:
  - SideBySideDiff component with jsdiff structuredPatch, Shiki highlighting, context lines
  - DiffHeader with Accept Edit / Reject Edit labels and inline reject confirmation
  - EditorArea diff tab routing with edit data fetching
  - Auto-open diff tabs on WebSocket edit_proposed events
affects: [11-agent-stream]

tech-stack:
  added: ["@types/diff"]
  patterns: [structuredPatch for line-level diffing, synchronized scroll via refs, inline confirmation with timeout]

key-files:
  created:
    - web/src/components/editor/SideBySideDiff.tsx
  modified:
    - web/src/components/editor/DiffHeader.tsx
    - web/src/components/editor/EditorArea.tsx
    - web/src/context/WebSocketContext.tsx
    - web/package.json

key-decisions:
  - "structuredPatch over diffLines for hunk-based diffing with context control"
  - "Synchronized scroll via onScroll handlers with requestAnimationFrame guard to prevent infinite loops"
  - "Edit data fetched on-demand in EditorArea and cached in component state"

patterns-established:
  - "structuredPatch with context:3 for hunk-based side-by-side diff rendering"
  - "Inline reject confirmation: first click shows 'Confirm Reject?', 3s timeout reverts"
  - "extractLineHtml: parse Shiki codeToHtml output to get per-line highlighted HTML spans"

requirements-completed: [DIFF-01, DIFF-04]

duration: 4min
completed: 2026-03-27
---

# Phase 10 Plan 02: Side-by-Side Diff View Summary

**Side-by-side diff with jsdiff structuredPatch algorithm, Shiki syntax highlighting on both sides, 3-context-line hunks, and auto-open on edit proposals**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T17:46:12Z
- **Completed:** 2026-03-27T17:49:56Z
- **Tasks:** 1 of 2 (Task 2 is checkpoint:human-verify -- awaiting verification)
- **Files modified:** 6

## Accomplishments
- Built SideBySideDiff component with real line-level diffing using jsdiff's structuredPatch algorithm
- Both diff sides render with Shiki syntax highlighting (extracting per-line HTML from codeToHtml output)
- DiffHeader updated with "Accept Edit" / "Reject Edit" labels and inline reject confirmation with 3-second timeout
- EditorArea wired to render SideBySideDiff when diff tab is active, with on-demand edit data fetching
- WebSocket auto-opens diff tabs on edit_proposed approval events

## Task Commits

Each task was committed atomically:

1. **Task 1: Install jsdiff types, build SideBySideDiff, update DiffHeader, wire EditorArea and auto-open** - `dde1243` (feat)

## Files Created/Modified
- `web/src/components/editor/SideBySideDiff.tsx` - Core two-column diff with structuredPatch, Shiki highlighting, context lines, hunk separators, accept/reject handlers
- `web/src/components/editor/DiffHeader.tsx` - Updated button labels to "Accept Edit"/"Reject Edit", added inline reject confirmation with setTimeout
- `web/src/components/editor/EditorArea.tsx` - Added SideBySideDiff rendering for diff tabs with edit data fetching and cache
- `web/src/context/WebSocketContext.tsx` - Added openDiff call on edit_proposed WebSocket events
- `web/package.json` - Added @types/diff devDependency
- `web/package-lock.json` - Updated lockfile

## Decisions Made
- Used structuredPatch over diffLines for proper hunk-based output with configurable context lines
- Synchronized scroll between sides using onScroll + requestAnimationFrame guard to prevent infinite bounce
- Edit data fetched on-demand in EditorArea via api.getEdits and cached in component state (not global store)
- Shiki HTML parsed per-line by splitting code element inner HTML on newlines

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Worktree was behind main (missing Plan 01 output files). Resolved by merging main into worktree before execution.
- WebSocketContext.tsx had been restructured since the plan was written (uses Zustand bridge pattern now). Adapted the openDiff wiring to use the new pattern.

## Known Stubs
None - all data paths are wired to real APIs.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Task 2 (checkpoint:human-verify) awaits human verification of the visual diff rendering
- After verification, diff viewing is complete and Phase 11 (agent stream) can proceed

---
*Phase: 10-code-diff-viewing*
*Completed: 2026-03-27*
