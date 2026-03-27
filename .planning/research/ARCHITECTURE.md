# Architecture Patterns: IDE UI Rebuild (v1.1)

**Domain:** VS Code-style three-panel IDE UI for an AI coding agent
**Researched:** 2026-03-27
**Confidence:** HIGH (existing codebase fully audited, libraries verified)

## Current Architecture (What Exists)

The existing frontend is a React 19 SPA with this structure:

```
App
  ErrorBoundary
    WebSocketProvider (projectId)
      ProjectProvider (onProjectChange)
        AppShell
          FileTree (left panel - currently shows project name + RunList)
          Center (WorkspaceHome | DiffViewer | RunProgress - conditional)
          AgentPanel (right panel)
```

### Current State Assessment

| Component | Current Role | v1.1 Fate |
|-----------|-------------|-----------|
| `AppShell` | 3-column CSS grid layout with collapse | **Evolve** - replace CSS grid with react-resizable-panels |
| `FileTree` | Shows project name + RunList, no actual file tree | **Replace** - needs real filesystem browsing via `/browse` API |
| `DiffViewer` | Shows only during `waiting_for_human`, naive old-all-red/new-all-green diff | **Replace** - needs proper diff algorithm, side-by-side view, always-accessible |
| `AgentPanel` | Right panel with StepTimeline + StreamingText | **Evolve** - keep core, add expandable LLM output sections |
| `WorkspaceHome` | Center panel when no run active, has prompt textarea | **Evolve** - prompt moves to top bar, home becomes file viewer |
| `RunProgress` | Center panel during active run, shows event log | **Absorb** - merge into ActivityStream, center panel shows files/diffs |
| `WebSocketContext` | Type-based pub/sub with wildcard support | **Keep** - sufficient for new data flows |
| `ProjectContext` | Project/run state, submitInstruction | **Evolve** - add run history fetching |

### Backend APIs Already Available

| Endpoint | Used By | Notes |
|----------|---------|-------|
| `GET /browse?path=` | ProjectPicker (directory only) | Returns `{current, parent, entries[{name, path, is_dir, has_children}]}`. Currently filters to directories only. Needs file support for file explorer. |
| `GET /runs/{id}/edits` | DiffViewer | Returns `Edit[]` with `old_content`, `new_content`, `file_path`, `status` |
| `PATCH /runs/{id}/edits/{id}` | DiffViewer | Approve/reject edits |
| `WS /ws/{project_id}` | WebSocketContext | Event types: approval, error, stop, review (P0), stream, diff, git (P1), status, file, exec (P2) |

### Backend Gaps

| Need | Current State | Required Change |
|------|--------------|-----------------|
| File tree listing (files + dirs) | `/browse` returns dirs only (skips files) | Extend to include files with metadata (size, extension) |
| File content reading | No endpoint exists | Add `GET /files?path=` returning file content with syntax hint |
| Live file change notifications | Events exist for edits but not file-level | Agent already tracks `edit_history` in state; emit `file.changed` events |

## Recommended Architecture

### Component Tree (Target)

```
App
  ErrorBoundary
    WebSocketProvider
      ProjectProvider
        WorkspaceProvider (NEW - file/tab/diff selection state)
          IDELayout (REPLACES AppShell)
            TopBar (NEW - instruction input + run selector + project picker)
            PanelGroup (react-resizable-panels)
              Panel: FileExplorer (NEW - real file tree + change indicators)
              PanelResizeHandle
              Panel: EditorArea (NEW - tabbed file viewer + diff viewer)
              PanelResizeHandle
              Panel: ActivityStream (EVOLVES from AgentPanel)
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `IDELayout` | Top-level layout shell, mounts TopBar + PanelGroup | WorkspaceProvider (layout prefs) |
| `TopBar` | Instruction input, run history dropdown, project selector, status indicator | ProjectContext (submit, select), WebSocketContext (status) |
| `FileExplorer` | Recursive file tree with lazy-loading, change indicators (M/A/D) | WorkspaceProvider (select file), WebSocketContext (file change events) |
| `EditorArea` | Tabbed container for file viewing and diff viewing | WorkspaceProvider (active tabs, selected file) |
| `FileViewer` | Read-only code display with syntax highlighting for a single file | api.getFileContent (new endpoint) |
| `DiffPanel` | Side-by-side or unified diff for an edit | api.getEdits, `diff` library for computation |
| `ActivityStream` | Agent step timeline + streaming LLM output + approval actions | WebSocketContext (all event types), ProjectContext (run state) |
| `WorkspaceProvider` | Manages open tabs, selected file, active diff, layout preferences | Consumed by EditorArea, FileExplorer, TopBar |

### New Context: WorkspaceProvider

The existing contexts (WebSocket, Project) handle connectivity and project/run state. The IDE needs a third context for workspace UI state that does not belong in either existing context.

```typescript
interface WorkspaceContextValue {
  // File explorer state
  selectedPath: string | null
  expandedDirs: Set<string>

  // Tab state
  openTabs: Tab[]
  activeTabId: string | null

  // Change tracking (from WebSocket events)
  changedFiles: Map<string, 'modified' | 'added' | 'deleted'>

  // Actions
  openFile: (path: string) => void
  openDiff: (editId: string) => void
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void
  clearChangedFiles: () => void
}

interface Tab {
  id: string
  type: 'file' | 'diff' | 'welcome'
  label: string
  path?: string      // for file tabs
  editId?: string    // for diff tabs
  isPinned: boolean  // false = preview tab (replaced on next single-click)
}
```

**Why a new context instead of extending ProjectContext:** ProjectContext manages server-side state (projects, runs, instructions). Workspace state is purely client-side UI state (which tab is open, which directory is expanded). Mixing them violates single-responsibility and would cause unnecessary re-renders across unrelated components.

### Data Flow

#### 1. File Explorer Data Flow

```
User clicks directory in FileExplorer
  -> api.browse(path) fetches children (files + dirs)
  -> FileExplorer stores in local state (lazy-loaded tree)
  -> expandedDirs updated in WorkspaceContext

User clicks file in FileExplorer
  -> WorkspaceContext.openFile(path)
  -> Creates/activates Tab { type: 'file', path }
  -> EditorArea renders FileViewer
  -> FileViewer calls api.getFileContent(path) (NEW endpoint)
  -> Renders with syntax highlighting via Shiki
```

#### 2. Live File Change Indicators

```
Agent edits a file during run
  -> Backend emits Event(type="diff", data={file_path, status})  [already exists]
  -> WebSocketContext distributes to 'diff' subscribers
  -> WorkspaceProvider subscribes to 'diff' events
  -> Updates changedFiles Map in WorkspaceContext
  -> FileExplorer reads changedFiles, shows M/A/D badge next to filename
```

#### 3. Diff Viewing Data Flow

```
User clicks changed file indicator OR approval event arrives
  -> WorkspaceContext.openDiff(editId)
  -> Creates/activates Tab { type: 'diff', editId }
  -> EditorArea renders DiffPanel
  -> DiffPanel calls api.getEdits(runId) to get Edit record
  -> Uses `diff` library (jsdiff) to compute line-level changes from old_content/new_content
  -> Renders side-by-side diff with syntax highlighting
  -> Approve/Reject buttons call api.patchEdit()
```

#### 4. Agent Stream Data Flow (mostly unchanged)

```
Run starts via TopBar instruction submit
  -> ProjectContext.submitInstruction() (unchanged)
  -> WebSocket events flow through WebSocketContext (unchanged)
  -> ActivityStream subscribes to '*' wildcard (like current RunProgress)
  -> Renders StepTimeline + expandable LLM output sections
  -> Approval events trigger diff tab auto-opening via WorkspaceContext
```

## Patterns to Follow

### Pattern 1: Lazy-Loading File Tree

**What:** Only fetch directory contents when a user expands a directory node. Cache results but invalidate on file change events.

**When:** Always, for the file explorer.

**Example:**
```typescript
function useDirectoryContents(path: string | null) {
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!path) return
    setLoading(true)
    api.browse(path).then(result => {
      setEntries(result.entries)
      setLoading(false)
    })
  }, [path])

  return { entries, loading }
}
```

**Why:** Project directories can have thousands of files. Eagerly loading the entire tree would be slow and wasteful. VS Code uses lazy loading -- match that pattern.

### Pattern 2: Tab-Based Navigation (Preview vs Pinned)

**What:** Files and diffs open in tabs in the center panel. Single-click opens a preview tab (italic title, replaced by next single-click). Double-click pins it (normal title, persists).

**When:** Any time a file or diff is opened.

**Why:** This is the VS Code convention users expect. It prevents tab explosion while allowing multi-file work.

```typescript
function openFile(path: string, pin = false) {
  const existingTab = openTabs.find(t => t.type === 'file' && t.path === path)
  if (existingTab) {
    setActiveTab(existingTab.id)
    if (pin) pinTab(existingTab.id)
    return
  }

  // Replace existing preview tab, or add new
  const previewTab = openTabs.find(t => !t.isPinned)
  if (previewTab && !pin) {
    replaceTab(previewTab.id, { type: 'file', path, isPinned: false })
  } else {
    addTab({ type: 'file', path, isPinned: pin })
  }
}
```

### Pattern 3: Event-Driven Change Tracking

**What:** Subscribe to WebSocket diff/file events to maintain a `changedFiles` map. Use this to show M/A/D indicators in the file tree without polling.

**When:** During active runs.

**Why:** The existing P0/P1/P2 event priority system already delivers diff events. Subscribe and track -- no new infrastructure needed.

### Pattern 4: Resizable Panel Persistence

**What:** Use `react-resizable-panels` with `autoSaveId` to persist panel sizes to localStorage automatically.

**When:** Always. The library handles this natively.

**Why:** Users expect their layout to persist across sessions. The existing codebase already uses localStorage for panel collapse state (`shipyard-left-collapsed`, `shipyard-right-collapsed`) -- this replaces that with better library support.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monaco Editor for Read-Only Viewing

**What:** Embedding Monaco Editor (or CodeMirror) for file viewing.

**Why bad:** Monaco adds ~2MB to the bundle. Shipyard is a read-only viewer -- users do not edit code in the browser. The agent edits; users review. Loading a full editor for read-only display is massive overkill.

**Instead:** Use Shiki for syntax highlighting in a `<pre>` block. ~25KB core + grammars loaded on demand. Save Monaco for if/when in-browser editing is added (out of scope for v1.1).

### Anti-Pattern 2: Global File Content Cache in Context

**What:** Storing all fetched file contents in WorkspaceContext.

**Why bad:** File contents can be large. Storing them in context causes re-renders across all consumers when any file loads. Memory pressure grows with open tabs.

**Instead:** Each FileViewer/DiffPanel manages its own content via local `useState`. The context only tracks which tabs are open and which is active, not their content.

### Anti-Pattern 3: Replacing WebSocket Architecture

**What:** Adding React Query or SWR alongside the existing WebSocket pub/sub.

**Why bad:** The WebSocket infrastructure already handles real-time updates with priority routing, reconnection, and replay. Adding another data layer creates confusion about source of truth.

**Instead:** Use existing WebSocket subscribe pattern for real-time data. Use plain `fetch` (via existing `api` module) for one-shot data loads (file contents, edit records). No new data layer needed.

### Anti-Pattern 4: Putting Prompt Input in Center Panel

**What:** Keeping the WorkspaceHome prompt as the center panel default view.

**Why bad:** In an IDE layout, the center panel should always show code/diffs. A centered prompt box wastes the most valuable screen real estate and breaks the IDE mental model.

**Instead:** Move the instruction input to the TopBar (always accessible). The center panel shows a welcome tab or open files/diffs.

## Integration Points with Existing Architecture

### WebSocketContext (NO CHANGES NEEDED)

The existing `subscribe(eventType, handler)` pattern is sufficient. New components subscribe to relevant event types:

| New Component | Subscribes To | Purpose |
|--------------|---------------|---------|
| WorkspaceProvider | `'diff'` | Track which files changed (M/A/D indicators) |
| ActivityStream | `'*'` (wildcard) | All events for stream display |
| DiffPanel | `'approval'` | React to approval status changes |
| TopBar | `'status'` | Show current agent node/step |

### ProjectContext (MINOR ADDITIONS)

The `runs` state is currently stubbed as an empty array. It needs to fetch runs for the current project to populate the run history dropdown in TopBar:

```typescript
// Current (stubbed):
const [runs] = useState<Run[]>([])

// Needed:
const [runs, setRuns] = useState<Run[]>([])
// Fetch on project change + after run completes
```

### API Module (ADDITIONS)

Two new endpoints needed, plus extending `/browse`:

```typescript
// Extend existing:
browse: (path?: string, includeFiles?: boolean) => ...

// New:
getFileContent: (path: string) =>
  request<{ content: string; language: string; size: number }>(`/files?path=${encodeURIComponent(path)}`)

getRuns: (projectId: string) =>
  request<Run[]>(`/projects/${projectId}/runs`)
```

## Build Order (Dependency-Aware)

Components must be built bottom-up based on dependencies:

```
Phase 1: Foundation (no component dependencies)
  1. WorkspaceProvider context
  2. Install react-resizable-panels, diff, shiki
  3. IDELayout shell (replaces AppShell with PanelGroup)
  4. TopBar (instruction input + project selector + run dropdown)

Phase 2: File Explorer (depends on Phase 1 + backend extension)
  5. Backend: extend /browse to include files
  6. Backend: add GET /files endpoint for content
  7. FileExplorer component with lazy-loading recursive tree
  8. File change indicator integration (WebSocket 'diff' events -> changedFiles)

Phase 3: Editor Area (depends on Phase 1 + Phase 2 partially)
  9. Tab bar and tab management in EditorArea
  10. FileViewer with Shiki syntax highlighting
  11. DiffPanel with jsdiff algorithm + side-by-side rendering
  12. Approval actions in DiffPanel (reuse existing api.patchEdit)

Phase 4: Activity Stream (depends on Phase 1, parallel with Phases 2-3)
  13. ActivityStream (evolve from AgentPanel + absorb RunProgress)
  14. Expandable LLM output sections (click step -> see full prompt/response)
  15. Inline approval actions + auto-open diff tab on approval events
```

**Why this order:**
- WorkspaceProvider must exist before any component that opens tabs or tracks files
- IDELayout must exist before panels can be placed
- Backend file endpoints must exist before FileExplorer can show real files
- Tab system must exist before FileViewer/DiffPanel can be mounted in tabs
- ActivityStream is independent of file/diff viewing and can be built in parallel

## Sources

- Existing codebase audit: `web/src/` -- all components, contexts, hooks, types, api module read directly
- [react-resizable-panels](https://github.com/bvaughn/react-resizable-panels) - v4.7.6, actively maintained, 1777 npm dependents
- [jsdiff](https://github.com/kpdecker/jsdiff) - text differencing library, Myers O(ND) algorithm
- [Shiki](https://shiki.style/) - VS Code-compatible syntax highlighter using TextMate grammars
