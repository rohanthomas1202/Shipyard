# Requirements: Shipyard

**Defined:** 2026-03-27
**Core Value:** The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

## v1.1 Requirements

Requirements for IDE UI Rebuild milestone. Each maps to roadmap phases.

### Layout & Infrastructure

- [ ] **LAYOUT-01**: User sees a VS Code-style three-panel resizable layout (file explorer | editor | agent stream)
- [ ] **LAYOUT-02**: User can drag panel borders to resize, with sizes persisted across sessions
- [ ] **LAYOUT-03**: User can collapse/expand any panel
- [ ] **LAYOUT-04**: User sees a persistent top bar with instruction input, project selector, and run status
- [ ] **LAYOUT-05**: High-frequency WebSocket state uses Zustand stores to prevent render storms across panels

### File Explorer

- [ ] **FILES-01**: User sees a lazy-loaded directory tree of the selected project's files
- [ ] **FILES-02**: User can expand/collapse directories to browse the file structure
- [ ] **FILES-03**: User sees live M/A/D indicators on files the agent modifies during a run
- [ ] **FILES-04**: File tree filters out .git, node_modules, __pycache__, and other gitignored paths
- [ ] **FILES-05**: User can click a file in the explorer to open it in the editor area

### Code & Diff Viewing

- [ ] **DIFF-01**: User sees a side-by-side diff view with proper line-level diff algorithm for agent edits
- [ ] **DIFF-02**: User sees syntax-highlighted code when viewing any file in the editor area
- [ ] **DIFF-03**: User can open multiple files and diffs in tabs with close functionality
- [ ] **DIFF-04**: Diff view shows context lines around changes (not just changed lines)

### Agent Activity Stream

- [ ] **STREAM-01**: User sees a real-time step timeline of agent activity (planning, reading, editing, validating)
- [ ] **STREAM-02**: Stream auto-scrolls when user is at the bottom, shows "N new events" badge when scrolled up

### Backend

- [ ] **API-01**: /browse endpoint returns files in addition to directories
- [ ] **API-02**: New /files endpoint returns file content with language detection
- [ ] **API-03**: /browse validates paths are within the project directory (no path traversal)

## Future Requirements

Deferred beyond v1.1. Tracked but not in current roadmap.

### Enhanced Navigation

- **NAV-01**: User can search files by name with fuzzy matching (Ctrl+P)
- **NAV-02**: User can use keyboard shortcuts for all panel operations

### Run History

- **HIST-01**: User can browse past runs in a dropdown and review what happened
- **HIST-02**: User can compare diffs across multiple runs

### Advanced Diff

- **ADIFF-01**: User can toggle between side-by-side and unified diff views
- **ADIFF-02**: User can see inline approval actions in the activity stream

### Agent Intelligence

- **AGENT-01**: Expandable LLM output per agent step (click to see full prompt/response)
- **AGENT-02**: Auto-open diff tab when agent requests edit approval

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| In-browser code editing (Monaco/CodeMirror) | Users don't edit code; the agent does. Read-only Shiki viewer sufficient. |
| Git graph/history visualization | Agent handles git operations. Out of scope for UI rebuild. |
| Terminal/console panel | Agent runs commands internally. Security risk, unnecessary. |
| Minimap (code overview) | Requires full editor engine. Not needed for read-only viewing. |
| Multi-tab diff comparison | Comparing diffs across edits is complex and niche. One diff at a time. |
| Breadcrumb navigation | Adds complexity with minimal value for agent review workflows. |
| Mobile/responsive layout | Desktop browser is the only target. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LAYOUT-01 | — | Pending |
| LAYOUT-02 | — | Pending |
| LAYOUT-03 | — | Pending |
| LAYOUT-04 | — | Pending |
| LAYOUT-05 | — | Pending |
| FILES-01 | — | Pending |
| FILES-02 | — | Pending |
| FILES-03 | — | Pending |
| FILES-04 | — | Pending |
| FILES-05 | — | Pending |
| DIFF-01 | — | Pending |
| DIFF-02 | — | Pending |
| DIFF-03 | — | Pending |
| DIFF-04 | — | Pending |
| STREAM-01 | — | Pending |
| STREAM-02 | — | Pending |
| API-01 | — | Pending |
| API-02 | — | Pending |
| API-03 | — | Pending |

**Coverage:**
- v1.1 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 after initial definition*
