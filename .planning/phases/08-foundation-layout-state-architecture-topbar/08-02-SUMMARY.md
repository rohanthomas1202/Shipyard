---
phase: 08-foundation-layout-state-architecture-topbar
plan: 02
subsystem: ui
tags: [react-resizable-panels, layout, topbar, zustand, ide-shell]

requires:
  - phase: 08-foundation-layout-state-architecture-topbar
    plan: 01
    provides: Zustand wsStore and workspaceStore, WebSocket bridge
provides:
  - Three-panel resizable IDE shell with react-resizable-panels v4
  - TopBar with InstructionInput, ProjectSelector, RunStatusIndicator
  - PanelHeader reusable component for panel title and collapse toggle
  - All WS consumers migrated from subscribe pattern to Zustand selectors
affects: [phase-09-file-tree, phase-10-tabbed-editor, phase-11-agent-panel]

tech-stack:
  added: [react-resizable-panels]
  patterns: [v4-group-panel-separator, useDefaultLayout-persistence, usePanelRef-imperative, panelSize-object-callback]

key-files:
  created:
    - web/src/components/layout/IDELayout.tsx
    - web/src/components/layout/TopBar.tsx
    - web/src/components/layout/InstructionInput.tsx
    - web/src/components/layout/ProjectSelector.tsx
    - web/src/components/layout/RunStatusIndicator.tsx
    - web/src/components/layout/PanelHeader.tsx
    - web/src/stores/wsStore.ts
    - web/src/stores/workspaceStore.ts
  modified:
    - web/src/App.tsx
    - web/src/components/agent/AgentPanel.tsx
    - web/src/components/agent/StreamingText.tsx
    - web/src/components/home/RunProgress.tsx
    - web/src/components/editor/DiffViewer.tsx
    - web/src/context/WebSocketContext.tsx
    - web/e2e/app.spec.ts
    - web/package.json

key-decisions:
  - "react-resizable-panels v4 uses panelRef prop (not ref), PanelSize object (not number) in onResize, orientation (not direction)"
  - "WebSocketContext kept as dual-write bridge to Zustand for backward compatibility during migration"
  - "Zustand stores created in this worktree since Plan 01 output was on a different worktree"

patterns-established:
  - "v4 Panel API: panelRef prop for imperative control, PanelSize.asPercentage for collapse detection"
  - "TopBar compact-to-expanded instruction input pattern with Cmd+Enter submit"

requirements-completed: [LAYOUT-01, LAYOUT-02, LAYOUT-03, LAYOUT-04]

duration: 8min
completed: 2026-03-27
---

# Phase 8 Plan 2: IDE Layout Shell and TopBar Summary

**Three-panel resizable IDE shell with react-resizable-panels v4, persistent TopBar with instruction input, project selector, and run status indicator, replacing CSS grid AppShell**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-27T15:09:31Z
- **Completed:** 2026-03-27T15:17:00Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- Installed react-resizable-panels v4.7.6 and created the three-panel IDE shell (IDELayout) replacing the CSS grid AppShell
- Created TopBar with InstructionInput (compact-to-expanded pattern, Cmd+Enter submit), ProjectSelector (dropdown), and RunStatusIndicator (colored dot + label)
- Created reusable PanelHeader component with title and collapse toggle
- Wired panel collapse/expand via header buttons, double-click on separator, and keyboard shortcuts (Cmd+B, Cmd+J)
- Panel sizes persist to localStorage via useDefaultLayout hook
- Migrated all 4 WS consumer components (AgentPanel, StreamingText, RunProgress, DiffViewer) from useWebSocketContext subscribe to Zustand selectors
- Updated WebSocketContext to bridge events to Zustand wsStore (dual-write for compatibility)
- Updated E2E tests for new IDE layout structure and copy text

## Task Commits

Each task was committed atomically:

1. **Task 1: Install react-resizable-panels and create layout components** - `e06396d` (feat)
2. **Task 2: Wire IDELayout into App.tsx, migrate WS consumers, update E2E tests** - `eb0b63c` (feat)

## Files Created/Modified
- `web/src/components/layout/IDELayout.tsx` - Three-panel resizable IDE shell with Group/Panel/Separator v4 API
- `web/src/components/layout/TopBar.tsx` - Persistent top bar with instruction input, project selector, run status
- `web/src/components/layout/InstructionInput.tsx` - Compact-to-expanded textarea with Cmd+Enter submit
- `web/src/components/layout/ProjectSelector.tsx` - Dropdown project selector from ProjectContext
- `web/src/components/layout/RunStatusIndicator.tsx` - Colored dot + label from wsStore snapshot
- `web/src/components/layout/PanelHeader.tsx` - Reusable panel header with title + collapse toggle
- `web/src/stores/wsStore.ts` - Zustand store for WebSocket event state (created as Plan 01 dependency)
- `web/src/stores/workspaceStore.ts` - Zustand store for workspace UI state (created as Plan 01 dependency)
- `web/src/App.tsx` - Replaced AppShell with IDELayout
- `web/src/components/agent/AgentPanel.tsx` - Migrated to useWsStore selector
- `web/src/components/agent/StreamingText.tsx` - Migrated from subscribe to useWsStore agentEvents
- `web/src/components/home/RunProgress.tsx` - Migrated from subscribe to useWsStore agentEvents
- `web/src/components/editor/DiffViewer.tsx` - Migrated from subscribe to useWsStore agentEvents
- `web/src/context/WebSocketContext.tsx` - Added Zustand bridge, useWebSocketSend, deprecated useWebSocketContext
- `web/e2e/app.spec.ts` - Updated for new IDE layout with EXPLORER/AGENT labels, TopBar tests
- `web/package.json` - Added react-resizable-panels and zustand dependencies

## Decisions Made
- react-resizable-panels v4 uses `panelRef` prop (not `ref`), `PanelSize` object (not number) in `onResize`, `orientation` (not `direction`) -- the research doc's v4 API section was mostly correct but missed the `panelRef` prop name and `PanelSize` object type
- WebSocketContext kept as dual-write bridge: events go to both Zustand store and legacy subscribe handlers for backward compatibility
- Created wsStore and workspaceStore in this worktree since Plan 01 output exists on a different worktree (Rule 3 - blocking dependency)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created Zustand stores missing from worktree**
- **Found during:** Task 1
- **Issue:** Plan 01 created wsStore and workspaceStore on a different worktree; this worktree had no stores directory
- **Fix:** Created both stores matching Plan 01 spec before proceeding
- **Files created:** web/src/stores/wsStore.ts, web/src/stores/workspaceStore.ts

**2. [Rule 1 - Bug] Fixed react-resizable-panels v4 API mismatches**
- **Found during:** Task 2 build verification
- **Issue:** Research doc said `ref` on Panel and `onResize(size: number)`, but v4 uses `panelRef` prop and `PanelSize` object type
- **Fix:** Changed `ref` to `panelRef`, updated onResize callback to accept `PanelSize` and use `.asPercentage`
- **Files modified:** web/src/components/layout/IDELayout.tsx

**3. [Rule 1 - Bug] Removed unused instructionRef variable**
- **Found during:** Task 2 build verification
- **Issue:** TypeScript strict mode flagged unused `instructionRef`
- **Fix:** Removed the unused ref declaration
- **Files modified:** web/src/components/layout/IDELayout.tsx

## Issues Encountered
None beyond the auto-fixed items above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
- `web/src/stores/workspaceStore.ts` - Intentional scaffolding. No component consumes this store yet. Phase 10 (tabbed editor) will wire it into TabBar and editor content area.

## Next Phase Readiness
- IDE shell ready for Phase 9 (file tree) to mount real file explorer in left panel
- Center panel ready for Phase 10 (tabbed editor) to replace WorkspaceHome/DiffViewer/RunProgress
- Right panel ready for Phase 11 (agent panel) to evolve AgentPanel with enhanced streaming

---
*Phase: 08-foundation-layout-state-architecture-topbar*
*Completed: 2026-03-27*
