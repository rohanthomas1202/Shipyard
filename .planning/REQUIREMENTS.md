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
- [x] **LAYOUT-05**: High-frequency WebSocket state uses Zustand stores to prevent render storms across panels

### File Explorer

- [x] **FILES-01**: User sees a lazy-loaded directory tree of the selected project's files
- [x] **FILES-02**: User can expand/collapse directories to browse the file structure
- [x] **FILES-03**: User sees live M/A/D indicators on files the agent modifies during a run
- [x] **FILES-04**: File tree filters out .git, node_modules, __pycache__, and other gitignored paths
- [x] **FILES-05**: User can click a file in the explorer to open it in the editor area

### Code & Diff Viewing

- [x] **DIFF-01**: User sees a side-by-side diff view with proper line-level diff algorithm for agent edits
- [x] **DIFF-02**: User sees syntax-highlighted code when viewing any file in the editor area
- [x] **DIFF-03**: User can open multiple files and diffs in tabs with close functionality
- [x] **DIFF-04**: Diff view shows context lines around changes (not just changed lines)

### Agent Activity Stream

- [ ] **STREAM-01**: User sees a real-time step timeline of agent activity (planning, reading, editing, validating)
- [ ] **STREAM-02**: Stream auto-scrolls when user is at the bottom, shows "N new events" badge when scrolled up

### Backend

- [x] **API-01**: /browse endpoint returns files in addition to directories
- [x] **API-02**: New /files endpoint returns file content with language detection
- [x] **API-03**: /browse validates paths are within the project directory (no path traversal)

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
| LAYOUT-01 | Phase 8 | Pending |
| LAYOUT-02 | Phase 8 | Pending |
| LAYOUT-03 | Phase 8 | Pending |
| LAYOUT-04 | Phase 8 | Pending |
| LAYOUT-05 | Phase 8 | Complete |
| FILES-01 | Phase 9 | Complete |
| FILES-02 | Phase 9 | Complete |
| FILES-03 | Phase 9 | Complete |
| FILES-04 | Phase 9 | Complete |
| FILES-05 | Phase 9 | Complete |
| API-01 | Phase 9 | Complete |
| API-02 | Phase 9 | Complete |
| API-03 | Phase 9 | Complete |
| DIFF-01 | Phase 10 | Complete |
| DIFF-02 | Phase 10 | Complete |
| DIFF-03 | Phase 10 | Complete |
| DIFF-04 | Phase 10 | Complete |
| STREAM-01 | Phase 11 | Pending |
| STREAM-02 | Phase 11 | Pending |

**Coverage:**
- v1.1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 after roadmap creation*
