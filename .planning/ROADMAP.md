# Roadmap: Shipyard

## Milestones

- ✅ **v1.0 Agent Core MVP** — Phases 1-7 (shipped 2026-03-27)
- 🚧 **v1.1 IDE UI Rebuild** — Phases 8-11 (in progress)

## Phases

<details>
<summary>✅ v1.0 Agent Core MVP (Phases 1-7) — SHIPPED 2026-03-27</summary>

- [x] Phase 1: Edit Reliability (3/3 plans) — completed 2026-03-26
- [x] Phase 2: Validation & Infrastructure (3/3 plans) — completed 2026-03-27
- [x] Phase 3: Context & Token Management (3/3 plans) — completed 2026-03-26
- [x] Phase 4: Crash Recovery & Run Lifecycle (3/3 plans) — completed 2026-03-26
- [x] Phase 5: Agent Core Features (3/3 plans) — completed 2026-03-27
- [x] Phase 6: Ship Rebuild (3/3 plans) — completed 2026-03-27
- [x] Phase 7: Deliverables & Deployment (3/3 plans) — completed 2026-03-27

</details>

### 🚧 v1.1 IDE UI Rebuild (In Progress)

**Milestone Goal:** Rebuild the frontend as a VS Code-style three-panel IDE with live agent feedback, file explorer, and side-by-side diff views.

- [ ] **Phase 8: Foundation — Layout, State Architecture, TopBar** - Zustand stores, resizable three-panel shell, persistent layout, top bar with instruction input
- [x] **Phase 9: File Explorer & Backend APIs** - Backend file endpoints, lazy-loaded directory tree, live M/A/D change indicators (completed 2026-03-27)
- [ ] **Phase 10: Code & Diff Viewing** - Tabbed editor area with syntax highlighting, side-by-side diff with proper line-level algorithm
- [ ] **Phase 11: Agent Activity Stream** - Real-time step timeline with auto-scroll and new-event badge

## Phase Details

### Phase 8: Foundation — Layout, State Architecture, TopBar
**Goal**: Users see a working IDE shell with resizable panels, persistent layout sizing, and always-visible instruction input — the architectural base that prevents render storms and enables all subsequent panels
**Depends on**: Phase 7 (v1.0 complete)
**Requirements**: LAYOUT-01, LAYOUT-02, LAYOUT-03, LAYOUT-04, LAYOUT-05
**Success Criteria** (what must be TRUE):
  1. User sees three resizable panels (file explorer, editor area, agent stream) arranged in a VS Code-style horizontal layout
  2. User can drag panel borders to resize and the sizes persist after page reload
  3. User can collapse and expand any panel by clicking its header or drag handle
  4. User sees a persistent top bar with instruction input field, project selector dropdown, and run status indicator visible on every screen
  5. WebSocket messages during an agent run do not cause visible lag or jank in panels that are not consuming the message (no render storms)
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md — Zustand stores (wsStore, workspaceStore) and WebSocketContext refactor to Zustand bridge
- [ ] 08-02-PLAN.md — Three-panel IDE shell with TopBar, layout components, App.tsx wiring, E2E test updates

**UI hint**: yes

### Phase 9: File Explorer & Backend APIs
**Goal**: Users can browse project files in a live directory tree and see which files the agent is modifying in real time
**Depends on**: Phase 8
**Requirements**: FILES-01, FILES-02, FILES-03, FILES-04, FILES-05, API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. User sees a lazy-loaded directory tree for the selected project that loads child nodes on expand (not the entire tree upfront)
  2. User can expand and collapse directories and the tree filters out .git, node_modules, __pycache__, and other gitignored paths
  3. During an agent run, files the agent modifies show live M (modified), A (added), or D (deleted) indicators that appear without page refresh
  4. User can click a file in the explorer to open it in the editor area (content loads from the backend)
  5. /browse endpoint cannot be used to read files outside the project directory (path traversal returns an error)
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md — Enhance /browse to return files with filtering, add /files endpoint with path traversal security
- [x] 09-02-PLAN.md — Lazy-loaded FileTree with TreeNode component, M/A/D change indicators, file click to open

**UI hint**: yes

### Phase 10: Code & Diff Viewing
**Goal**: Users can review agent edits with syntax-highlighted code and proper side-by-side diffs in a tabbed editor area
**Depends on**: Phase 9
**Requirements**: DIFF-01, DIFF-02, DIFF-03, DIFF-04
**Success Criteria** (what must be TRUE):
  1. User sees side-by-side diff view with actual line-level diffing (changed, added, and removed lines correctly identified — not "all old lines red, all new lines green")
  2. User sees syntax-highlighted code when viewing any file in a tab (language auto-detected from file extension)
  3. User can open multiple files and diffs in separate tabs and close individual tabs
  4. Diff view shows unchanged context lines around changes so the user can understand the surrounding code
**Plans**: TBD
**UI hint**: yes

### Phase 11: Agent Activity Stream
**Goal**: Users can follow agent progress in real time through a step-by-step timeline that stays out of the way when reviewing past events
**Depends on**: Phase 8
**Requirements**: STREAM-01, STREAM-02
**Success Criteria** (what must be TRUE):
  1. User sees a real-time timeline of agent steps (planning, reading, editing, validating) that updates live during a run without page refresh
  2. When the user is scrolled to the bottom of the stream, new events auto-scroll into view; when the user scrolls up to review past events, auto-scroll stops and a "N new events" badge appears
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 8 -> 9 -> 10 -> 11
Note: Phase 11 depends on Phase 8 (not 10) and can overlap with Phases 9-10 if needed.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Edit Reliability | v1.0 | 3/3 | Complete | 2026-03-26 |
| 2. Validation & Infrastructure | v1.0 | 3/3 | Complete | 2026-03-27 |
| 3. Context & Token Management | v1.0 | 3/3 | Complete | 2026-03-26 |
| 4. Crash Recovery & Run Lifecycle | v1.0 | 3/3 | Complete | 2026-03-26 |
| 5. Agent Core Features | v1.0 | 3/3 | Complete | 2026-03-27 |
| 6. Ship Rebuild | v1.0 | 3/3 | Complete | 2026-03-27 |
| 7. Deliverables & Deployment | v1.0 | 3/3 | Complete | 2026-03-27 |
| 8. Foundation — Layout, State Architecture, TopBar | v1.1 | 0/2 | In progress | - |
| 9. File Explorer & Backend APIs | v1.1 | 2/2 | Complete   | 2026-03-27 |
| 10. Code & Diff Viewing | v1.1 | 1/2 | In Progress|  |
| 11. Agent Activity Stream | v1.1 | 0/0 | Not started | - |

---
*Full v1.0 details archived in `.planning/milestones/v1.0-ROADMAP.md`*
