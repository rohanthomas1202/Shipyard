# Feature Landscape: IDE UI Rebuild (v1.1)

**Domain:** VS Code-style IDE UI for AI coding agent
**Researched:** 2026-03-27

## Table Stakes

Features users expect from an IDE-style interface. Missing = product feels like a prototype.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Resizable three-panel layout | Core IDE convention (file tree, editor, panel) | Medium | react-resizable-panels handles the hard parts |
| File explorer with directory tree | Cannot browse code without one | Medium | Lazy-load via existing `/browse` API (needs file extension) |
| Syntax-highlighted code viewing | Raw text feels broken in an IDE context | Medium | Shiki with on-demand grammar loading |
| Side-by-side diff view | Agent makes edits; users must review them clearly | High | Requires proper diff algorithm (jsdiff), custom rendering |
| Tab-based file navigation | IDE convention; multiple files must be viewable | Medium | WorkspaceProvider manages tab state |
| Top-bar instruction input | Primary interaction point must always be accessible | Low | Move from center (WorkspaceHome) to persistent top bar |
| Real-time agent activity stream | Users need to see what the agent is doing | Medium | Evolve existing AgentPanel with better event formatting |
| Run status indicator | Must know if agent is working, idle, or waiting | Low | Already exists in AgentPanel footer; move to TopBar |
| Panel collapse/expand | Screen real estate management | Low | react-resizable-panels supports collapsible panels natively |

## Differentiators

Features that set Shipyard apart from generic code viewers. Not expected but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live file change indicators (M/A/D) | See which files the agent touched in real-time without checking git | Low | Subscribe to WebSocket 'diff' events, badge file tree nodes |
| Auto-open diff on approval request | When agent proposes an edit, diff tab opens automatically | Low | WorkspaceProvider listens for 'approval' events |
| Expandable LLM output in activity stream | Click a step to see the full prompt/response the agent used | Medium | Expand/collapse sections in ActivityStream |
| Run history dropdown | Quickly switch between past runs to review what happened | Medium | Needs `GET /projects/{id}/runs` endpoint + dropdown in TopBar |
| Preview vs pinned tabs | VS Code-style: single-click previews, double-click pins | Low | Tab state management in WorkspaceProvider |
| Keyboard shortcuts | Power users expect Ctrl+P (file), Ctrl+Shift+P (command) | Low | Extend existing useHotkeys hook |
| Inline approval in activity stream | Approve/reject edits from the stream without switching to diff tab | Medium | Reuse api.patchEdit, add approve/reject buttons to stream events |

## Anti-Features

Features to explicitly NOT build in v1.1.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| In-browser code editing | Users do not edit code; the agent does. Building an editor is massive scope creep. | Read-only file viewer with syntax highlighting. Agent is the editor. |
| Git graph/history visualization | Out of scope for v1.1. Agent handles git operations. | Show branch name and last commit in TopBar status area. |
| Terminal/console panel | Agent runs commands internally. Exposing a terminal is unnecessary and a security risk. | Show command output in activity stream as expandable blocks. |
| File search/fuzzy finder | Nice-to-have but not critical for v1.1 watching an agent work. | Defer to v1.2. Users browse via file tree. |
| Multi-tab diff comparison | Comparing diffs across multiple edits is complex and niche. | Show one diff at a time per tab. User scrolls through edit list. |
| Minimap (code overview) | VS Code feature that requires a full editor engine. | Not needed for read-only viewing at v1.1 scale. |
| Breadcrumb navigation | File path breadcrumbs add complexity with minimal value for agent review. | Show full file path in tab title and diff header. |

## Feature Dependencies

```
WorkspaceProvider -> Tab System -> FileViewer
WorkspaceProvider -> Tab System -> DiffPanel
WorkspaceProvider -> File Change Tracking -> File Explorer (M/A/D badges)

TopBar -> ProjectContext (project selector, instruction submit)
TopBar -> WorkspaceProvider (run history dropdown)

FileExplorer -> api.browse (extended with files) -> FileViewer (via tab)
DiffPanel -> api.getEdits (existing) -> diff library (computation)

ActivityStream -> WebSocketContext (existing event subscription)
ActivityStream -> WorkspaceProvider (auto-open diff tab on approval)
```

## MVP Recommendation

**Must ship (table stakes that define the product):**
1. Three-panel resizable layout with collapse
2. File explorer with real file tree (lazy-loaded)
3. Syntax-highlighted read-only file viewer in tabs
4. Side-by-side diff view for agent edits with approve/reject
5. Top bar with instruction input and project selector
6. Agent activity stream with step timeline

**High-value differentiators to include:**
7. Live file change indicators (M/A/D) -- low complexity, high impact
8. Auto-open diff on approval request -- low complexity, great UX

**Defer to later:**
- Run history dropdown: Needs new backend endpoint, not critical for demo
- Expandable LLM output: Nice but not blocking; agent stream shows high-level steps
- Keyboard shortcuts beyond existing: Current Ctrl+Shift+P focus is sufficient
- Inline approval in stream: Users can approve in the diff tab

## Sources

- VS Code UX conventions (de facto standard for IDE UI)
- Existing Shipyard component audit (`web/src/components/`)
- PROJECT.md active requirements list
