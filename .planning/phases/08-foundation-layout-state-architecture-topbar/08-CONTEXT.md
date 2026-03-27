# Phase 8: Foundation — Layout, State Architecture, TopBar - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebuild the frontend shell as a VS Code-style three-panel IDE layout with resizable panels, a persistent top bar, and Zustand-based state architecture that prevents render storms. This is the structural foundation — file explorer content, diff viewing, and agent stream improvements are separate phases (9-11).

</domain>

<decisions>
## Implementation Decisions

### Visual Style
- **D-01:** Keep the existing glassmorphic/frosted look throughout, including code areas. MeshBackground stays.
- **D-02:** Use higher contrast text in code areas to compensate for translucent backgrounds.

### Panel Layout & Behavior
- **D-03:** Three resizable panels using react-resizable-panels: file explorer (left), editor area (center), agent stream (right).
- **D-04:** Both header toggle buttons AND double-click on resize handle to collapse/expand panels.
- **D-05:** Panel sizes persist to localStorage via react-resizable-panels `autoSaveId`.

### Top Bar
- **D-06:** Instruction input uses compact+expand pattern: small input that expands into multi-line textarea when clicked. Saves space by default, prominent when typing.
- **D-07:** Top bar also includes project selector and run status. Exact layout is Claude's discretion.

### State Architecture
- **D-08:** Migrate WebSocket event distribution to Zustand store with fine-grained selectors. Each panel subscribes to its relevant slice only.
- **D-09:** New WorkspaceProvider state (tabs, selected file, changed files) also in Zustand, NOT React Context.
- **D-10:** ProjectContext stays as React Context (low-frequency state: projects, current project, submit instruction).

### Claude's Discretion
- Panel minimum sizes (reasonable defaults)
- Top bar layout arrangement (input, project selector, status positioning)
- Zustand store shape and slice boundaries
- Exact collapse/expand animations and transitions
- Resize handle visual styling

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Frontend Architecture
- `web/src/components/layout/AppShell.tsx` — Current 3-column CSS grid layout being replaced
- `web/src/context/WebSocketContext.tsx` — Current WS state bundling (stable + changing values) — the render storm source
- `web/src/context/ProjectContext.tsx` — Stays as React Context, but `runs` array needs to be populated
- `web/src/hooks/useWebSocket.ts` — WS connection hook, per-message dispatch pattern
- `web/src/hooks/useHotkeys.ts` — Existing keyboard shortcut infrastructure
- `web/src/components/layout/MeshBackground.tsx` — Glassmorphic backdrop, stays unchanged

### Research
- `.planning/research/STACK.md` — Library choices: react-resizable-panels, Zustand, Shiki, jsdiff
- `.planning/research/ARCHITECTURE.md` — Component tree, WorkspaceProvider design, data flows
- `.planning/research/PITFALLS.md` — Render storm prevention, Context propagation penalty, panel resize jank

### Design System
- `web/src/styles/` — Existing CSS/Tailwind design tokens

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MeshBackground` component: Glassmorphic animated backdrop — reuse unchanged
- `useHotkeys` hook: Keyboard shortcut infrastructure — extend for panel shortcuts
- `useWebSocket` hook: WS connection management — keep connection layer, replace event distribution
- `ProjectPicker` component: Project selection modal — extract into top bar dropdown
- `SettingsModal` component: Settings UI — trigger from top bar

### Established Patterns
- Tailwind CSS 4 for all styling (no CSS-in-JS)
- React Context for dependency injection (ProjectContext wraps WebSocketProvider)
- localStorage for user preferences (collapse state, theme)
- Type-based event subscription via `subscribe(eventType, handler)`

### Integration Points
- `App.tsx` wraps providers: ErrorBoundary → WebSocketProvider → ProjectProvider → AppShell
- AppShell is the replacement target — IDELayout takes its place
- WebSocketContext.tsx is the refactor target — Zustand store replaces event distribution
- All existing components (FileTree, AgentPanel, WorkspaceHome, DiffViewer, RunProgress) will be mounted inside new panel structure

</code_context>

<specifics>
## Specific Ideas

- User wants the UI to look like VS Code once a project is selected
- Glassmorphic style is part of Shipyard's identity — keep it
- Instruction input should feel like a command palette: compact by default, expands on interaction

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-foundation-layout-state-architecture-topbar*
*Context gathered: 2026-03-27*
