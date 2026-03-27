# Phase 8: Foundation -- Layout, State Architecture, TopBar - Research

**Researched:** 2026-03-27
**Domain:** React IDE shell layout with Zustand state management and react-resizable-panels
**Confidence:** HIGH

## Summary

Phase 8 replaces the existing CSS grid `AppShell` with a VS Code-style three-panel IDE layout using `react-resizable-panels` v4.7.6 and migrates WebSocket event distribution from React Context to Zustand v5 stores with fine-grained selectors. The top bar moves the instruction input out of the center panel into a persistent bar with project selector and run status.

A critical finding: `react-resizable-panels` v4 has breaking API changes from v3. The component names changed (`PanelGroup` to `Group`, `PanelResizeHandle` to `Separator`), `direction` became `orientation`, `autoSaveId` was replaced with `useDefaultLayout` hook, and `onCollapse`/`onExpand` callbacks were removed in favor of `onResize`. The prior research documents (STACK.md, ARCHITECTURE.md) reference the v3 API -- the planner must use the v4 API documented here.

Zustand v5.0.12 is the current version, fully compatible with React 19. The `create<T>()(...)` curried pattern is required for TypeScript type inference.

**Primary recommendation:** Install `react-resizable-panels@^4.7` and `zustand@^5.0` as new dependencies. Build the Zustand `wsStore` first (it has no UI dependencies), then the `IDELayout` shell with `Group`/`Panel`/`Separator`, then the `TopBar`. Mount existing components into new panels without modification.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Keep the existing glassmorphic/frosted look throughout, including code areas. MeshBackground stays.
- **D-02:** Use higher contrast text in code areas to compensate for translucent backgrounds.
- **D-03:** Three resizable panels using react-resizable-panels: file explorer (left), editor area (center), agent stream (right).
- **D-04:** Both header toggle buttons AND double-click on resize handle to collapse/expand panels.
- **D-05:** Panel sizes persist to localStorage via react-resizable-panels `autoSaveId`. [NOTE: v4 replaces `autoSaveId` with `useDefaultLayout` hook -- same outcome, different API]
- **D-06:** Instruction input uses compact+expand pattern: small input that expands into multi-line textarea when clicked. Saves space by default, prominent when typing.
- **D-07:** Top bar also includes project selector and run status. Exact layout is Claude's discretion.
- **D-08:** Migrate WebSocket event distribution to Zustand store with fine-grained selectors. Each panel subscribes to its relevant slice only.
- **D-09:** New WorkspaceProvider state (tabs, selected file, changed files) also in Zustand, NOT React Context.
- **D-10:** ProjectContext stays as React Context (low-frequency state: projects, current project, submit instruction).

### Claude's Discretion
- Panel minimum sizes (reasonable defaults)
- Top bar layout arrangement (input, project selector, status positioning)
- Zustand store shape and slice boundaries
- Exact collapse/expand animations and transitions
- Resize handle visual styling

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LAYOUT-01 | User sees a VS Code-style three-panel resizable layout (file explorer, editor, agent stream) | react-resizable-panels v4.7.6 `Group`/`Panel`/`Separator` with `orientation="horizontal"`. Existing components mounted in panels without modification. |
| LAYOUT-02 | User can drag panel borders to resize, with sizes persisted across sessions | `useDefaultLayout` hook with `groupId` and `storage: localStorage` replaces v3 `autoSaveId`. Persistence is automatic. |
| LAYOUT-03 | User can collapse/expand any panel | `Panel` `collapsible` prop + imperative `collapse()`/`expand()` via `usePanelRef()`. `onResize` callback detects collapse state (replaces removed `onCollapse`/`onExpand`). Double-click on `Separator` toggles via imperative API. |
| LAYOUT-04 | User sees a persistent top bar with instruction input, project selector, and run status | New `TopBar` component above `Group`. `InstructionInput` with compact/expand pattern, `ProjectSelector` extracted from existing `ProjectPicker`, `RunStatusIndicator` reading Zustand wsStore. |
| LAYOUT-05 | High-frequency WebSocket state uses Zustand stores to prevent render storms across panels | Zustand v5.0.12 `wsStore` with selector-based subscriptions. WebSocket hook pushes events into store. Each panel selects only its slice: `useWsStore(s => s.agentEvents)`, `useWsStore(s => s.snapshot)`, etc. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-resizable-panels | 4.7.6 | Three-panel resizable IDE layout | De facto standard (1777 npm dependents), WAI-ARIA compliant, used by shadcn/ui, ~8KB gzipped |
| zustand | 5.0.12 | Fine-grained WebSocket + workspace state | React 19 compatible, selector-based subscriptions prevent render storms, ~2KB gzipped |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| React | 19.2.4 (existing) | UI framework | Already installed |
| Tailwind CSS | 4.2.2 (existing) | Styling | Already installed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-resizable-panels | allotment | Less maintained, fewer dependents, no v4 modern API |
| zustand | jotai | Atom-based model is more granular than needed; Zustand's store model maps better to WebSocket event slices |
| zustand | React Context with useSyncExternalStore | More boilerplate, no middleware ecosystem, harder to test |

**Installation:**
```bash
cd web
npm install react-resizable-panels zustand
```

**Version verification:** Verified against npm registry on 2026-03-27:
- `react-resizable-panels`: 4.7.6 (latest)
- `zustand`: 5.0.12 (latest)

## Architecture Patterns

### Recommended Project Structure
```
web/src/
  stores/
    wsStore.ts              # WebSocket event state (Zustand)
    workspaceStore.ts       # Tabs, selected file, layout (Zustand)
  components/
    layout/
      IDELayout.tsx         # Replaces AppShell -- Group + Panel + Separator + TopBar
      TopBar.tsx            # Instruction input + project selector + run status
      InstructionInput.tsx  # Compact-to-expanded textarea
      ProjectSelector.tsx   # Dropdown extracted from ProjectPicker
      RunStatusIndicator.tsx # Colored dot + status label
      PanelHeader.tsx       # Reusable panel header with title + collapse toggle
      ResizeHandle.tsx      # Styled Separator wrapper
      MeshBackground.tsx    # Unchanged
      ErrorBoundary.tsx     # Unchanged
```

### Pattern 1: react-resizable-panels v4 Layout

**CRITICAL: v4 API differs from v3.** The prior research documents reference v3 names (`PanelGroup`, `PanelResizeHandle`, `autoSaveId`, `direction`). Use the v4 API below.

**What:** Three-panel horizontal layout with collapsible side panels and persistent sizes.

**v4 Imports:**
```typescript
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from 'react-resizable-panels'
```

**v4 Layout Example:**
```typescript
// Source: react-resizable-panels v4 API (npm 4.7.6)
function IDELayout() {
  const { defaultLayout, onLayoutChange } = useDefaultLayout({
    groupId: 'shipyard-ide-panels',
    storage: localStorage,
  })

  const leftPanelRef = usePanelRef()
  const rightPanelRef = usePanelRef()

  return (
    <div className="h-screen w-screen flex flex-col">
      <TopBar />
      <div className="flex-1 p-4 pt-0">
        <Group
          orientation="horizontal"
          defaultLayout={defaultLayout}
          onLayoutChange={onLayoutChange}
        >
          <Panel
            ref={leftPanelRef}
            defaultSize={20}
            minSize={10}
            collapsible
            collapsedSize={3}
            onResize={(size) => {
              // Detect collapse: size === collapsedSize
            }}
          >
            <LeftPanel />
          </Panel>
          <Separator />
          <Panel defaultSize={50} minSize={20}>
            <CenterPanel />
          </Panel>
          <Separator />
          <Panel
            ref={rightPanelRef}
            defaultSize={30}
            minSize={12}
            collapsible
            collapsedSize={0}
            onResize={(size) => {
              // Detect collapse: size === 0
            }}
          >
            <RightPanel />
          </Panel>
        </Group>
      </div>
    </div>
  )
}
```

**Key v4 Differences from v3:**
| v3 | v4 | Notes |
|----|-----|-------|
| `PanelGroup` | `Group` | Renamed |
| `PanelResizeHandle` | `Separator` | Aligns with ARIA separator role |
| `direction="horizontal"` | `orientation="horizontal"` | Aligns with ARIA orientation |
| `autoSaveId="id"` on Group | `useDefaultLayout({ groupId: "id", storage })` hook | Returns `defaultLayout` + `onLayoutChange` |
| `onCollapse={() => {}}` on Panel | `onResize={(size) => { if (size === collapsedSize) ... }}` | Removed; check size in onResize |
| `onExpand={() => {}}` on Panel | `onResize={(size) => { if (size > collapsedSize) ... }}` | Removed; check size in onResize |
| `useRef` + `ImperativePanelHandle` | `usePanelRef()` hook | New hook for imperative API |

**Imperative Panel Control (v4):**
```typescript
const panelRef = usePanelRef()

// Collapse
panelRef.current?.collapse()

// Expand
panelRef.current?.expand()

// Check state
panelRef.current?.isCollapsed()

// Resize to specific percentage
panelRef.current?.resize(25)
```

### Pattern 2: Zustand Store with Fine-Grained Selectors

**What:** Zustand v5 store replaces WebSocket Context for event distribution. Each panel selects only its relevant slice.

```typescript
// Source: Zustand v5 docs (pmndrs/zustand)
import { create } from 'zustand'
import type { WSEvent, RunSnapshot } from '../types'

interface WSStore {
  // Connection
  status: 'connecting' | 'connected' | 'disconnected'
  setStatus: (s: WSStore['status']) => void

  // Run snapshot
  snapshot: RunSnapshot | null
  setSnapshot: (s: RunSnapshot | null) => void

  // Agent events (consumed by ActivityStream only)
  agentEvents: WSEvent[]
  appendAgentEvent: (e: WSEvent) => void
  clearAgentEvents: () => void

  // File change tracking (consumed by FileExplorer only)
  changedFiles: Record<string, 'modified' | 'added' | 'deleted'>
  setFileChanged: (path: string, status: 'modified' | 'added' | 'deleted') => void
  clearChangedFiles: () => void

  // Last sequence per run
  lastSeq: Record<string, number>
  setLastSeq: (runId: string, seq: number) => void
}

export const useWsStore = create<WSStore>()((set) => ({
  status: 'disconnected',
  setStatus: (status) => set({ status }),

  snapshot: null,
  setSnapshot: (snapshot) => set({ snapshot }),

  agentEvents: [],
  appendAgentEvent: (e) => set((s) => ({
    agentEvents: [...s.agentEvents, e],
  })),
  clearAgentEvents: () => set({ agentEvents: [] }),

  changedFiles: {},
  setFileChanged: (path, status) => set((s) => ({
    changedFiles: { ...s.changedFiles, [path]: status },
  })),
  clearChangedFiles: () => set({ changedFiles: {} }),

  lastSeq: {},
  setLastSeq: (runId, seq) => set((s) => ({
    lastSeq: { ...s.lastSeq, [runId]: seq },
  })),
}))
```

**Selector Usage (prevents render storms):**
```typescript
// ActivityStream -- only re-renders when agentEvents changes
const events = useWsStore((s) => s.agentEvents)

// RunStatusIndicator -- only re-renders when snapshot changes
const snapshot = useWsStore((s) => s.snapshot)

// Connection banner -- only re-renders when connection status changes
const wsStatus = useWsStore((s) => s.status)

// FileExplorer -- only re-renders when changedFiles changes
const changedFiles = useWsStore((s) => s.changedFiles)
```

### Pattern 3: WebSocket Hook to Zustand Bridge

**What:** Keep the existing `useWebSocket` hook for connection management. Replace `WebSocketContext` event distribution with Zustand store updates.

```typescript
// In WebSocketProvider (simplified):
const { status, send, onMessage } = useWebSocket(projectId)
const { setStatus, setSnapshot, appendAgentEvent, setFileChanged, setLastSeq } = useWsStore.getState()

useEffect(() => {
  // Push connection status into Zustand
  setStatus(status)
}, [status])

useEffect(() => {
  const unsub = onMessage((event: WSEvent) => {
    // Track seq
    if (event.seq && event.run_id) {
      setLastSeq(event.run_id, event.seq)
    }

    // Route to appropriate store slice
    if (event.type === 'snapshot') {
      setSnapshot(event as unknown as RunSnapshot)
    } else if (event.type === 'diff') {
      setFileChanged(event.data.file_path as string, 'modified')
      appendAgentEvent(event)
    } else {
      appendAgentEvent(event)
    }
  })
  return unsub
}, [onMessage])
```

**Key insight:** `useWsStore.getState()` accesses the store outside React render cycle. This is safe and avoids the hook needing to be a subscriber itself.

### Pattern 4: Workspace Store (Client-Side UI State)

```typescript
import { create } from 'zustand'

interface Tab {
  id: string
  type: 'file' | 'diff' | 'welcome'
  label: string
  path?: string
  editId?: string
  isPinned: boolean
}

interface WorkspaceStore {
  openTabs: Tab[]
  activeTabId: string | null
  selectedPath: string | null
  openFile: (path: string, pin?: boolean) => void
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void
  setSelectedPath: (path: string | null) => void
}

export const useWorkspaceStore = create<WorkspaceStore>()((set) => ({
  openTabs: [],
  activeTabId: null,
  selectedPath: null,
  openFile: (path, pin = false) => set((s) => {
    const existing = s.openTabs.find((t) => t.type === 'file' && t.path === path)
    if (existing) {
      return { activeTabId: existing.id }
    }
    const tab: Tab = {
      id: `file-${path}`,
      type: 'file',
      label: path.split('/').pop() || path,
      path,
      isPinned: pin,
    }
    return { openTabs: [...s.openTabs, tab], activeTabId: tab.id }
  }),
  closeTab: (tabId) => set((s) => {
    const tabs = s.openTabs.filter((t) => t.id !== tabId)
    const activeTabId = s.activeTabId === tabId
      ? (tabs[tabs.length - 1]?.id ?? null)
      : s.activeTabId
    return { openTabs: tabs, activeTabId }
  }),
  setActiveTab: (tabId) => set({ activeTabId: tabId }),
  setSelectedPath: (path) => set({ selectedPath: path }),
}))
```

### Anti-Patterns to Avoid

- **Using v3 API names:** Do NOT use `PanelGroup`, `PanelResizeHandle`, `direction`, or `autoSaveId`. These are v3 names that will cause import errors with v4.7.6.
- **Putting WebSocket events in React Context:** Causes re-renders on ALL consumers when ANY event arrives. Use Zustand selectors instead.
- **Selecting entire store:** `useWsStore()` without a selector subscribes to the entire store. ALWAYS pass a selector function.
- **Storing panel content in Zustand:** Panel content (file text, diff data) should be local `useState` in the panel component, not in the store. The store only tracks which tabs are open and which is active.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Resizable panel layout | Custom CSS grid with drag handlers | react-resizable-panels v4 `Group`/`Panel`/`Separator` | Drag resize, collapse, keyboard a11y, localStorage persistence -- hundreds of edge cases |
| Panel size persistence | Custom localStorage read/write | `useDefaultLayout` hook from react-resizable-panels | Handles serialization, debouncing, and multi-panel coordination |
| State management with selectors | React Context + useSyncExternalStore | Zustand `create` with selector functions | Built-in selector memoization, no Context propagation penalty, <2KB |
| WebSocket event batching | Custom requestAnimationFrame batching | Zustand store + selectors | Zustand's selector comparison already prevents unnecessary re-renders; rAF batching is only needed if setState itself is too frequent |

## Common Pitfalls

### Pitfall 1: Using v3 API Names with v4 Package
**What goes wrong:** Import errors -- `PanelGroup`, `PanelResizeHandle` are not exported from v4.
**Why it happens:** Prior research documents and many online tutorials reference v3 API.
**How to avoid:** Use v4 names: `Group`, `Panel`, `Separator`. Import `useDefaultLayout` for persistence and `usePanelRef` for imperative control.
**Warning signs:** TypeScript import errors, runtime "is not a function" errors.

### Pitfall 2: WebSocket Context Re-render Storm
**What goes wrong:** All panels re-render on every WebSocket message because `WebSocketContext` bundles `status`, `snapshot`, `subscribe`, `send`, and `lastSeqRef` in one value object.
**Why it happens:** React Context has no selector mechanism. Changing `snapshot` re-renders every `useWebSocketContext()` consumer.
**How to avoid:** Migrate event distribution to Zustand store. Keep `WebSocketContext` minimal (only `send` function which is stable). Or eliminate WebSocketContext entirely -- `send` can be a ref passed through the existing hook.
**Warning signs:** React DevTools shows all panels flashing on every WS message.

### Pitfall 3: Separator Must Be Direct Child of Group
**What goes wrong:** Wrapping `Separator` in a custom component or `<div>` breaks the layout.
**Why it happens:** react-resizable-panels v4 requires `Separator` elements to be direct DOM children of the `Group` element.
**How to avoid:** The `ResizeHandle` wrapper component must render `Separator` directly, not wrap it in additional DOM. Use `Separator` props for styling, or use `data-*` attributes and CSS.
**Warning signs:** Panels don't resize, or layout breaks on drag.

### Pitfall 4: Zustand Store Selector Returning New Object Reference
**What goes wrong:** Selector that creates a new object on every call causes infinite re-renders.
**Why it happens:** `useStore((s) => ({ a: s.a, b: s.b }))` creates a new object reference every time, failing shallow equality check.
**How to avoid:** Select primitive values: `useStore((s) => s.status)`. If multiple values are needed, use `useShallow` from `zustand/react/shallow`: `useStore(useShallow((s) => ({ a: s.a, b: s.b })))`.
**Warning signs:** Components re-rendering continuously even when no state changed.

### Pitfall 5: Panel Collapse Detection in v4
**What goes wrong:** Code listens for `onCollapse`/`onExpand` callbacks that no longer exist in v4.
**Why it happens:** v3 had these callbacks; v4 removed them.
**How to avoid:** Use `onResize` callback and check if size equals `collapsedSize`. Or use imperative `panelRef.current?.isCollapsed()`.
**Warning signs:** Collapse state not tracked, icon rail not shown when collapsed.

### Pitfall 6: Existing E2E Tests Will Break
**What goes wrong:** The existing Playwright tests in `web/e2e/app.spec.ts` assert on v1.0 UI elements that Phase 8 replaces (e.g., "Explorer" text, textarea location, "AI Agent" text, sidebar structure).
**Why it happens:** Phase 8 restructures the entire layout. Text labels, element hierarchy, and DOM structure all change.
**How to avoid:** Update E2E tests as part of Phase 8. The new assertions should match the UI-SPEC copy (e.g., "EXPLORER" uppercase label, instruction input in top bar, "AGENT" panel header).
**Warning signs:** CI fails on Playwright tests after layout changes.

## Code Examples

### InstructionInput Component (Compact-to-Expand Pattern)

```typescript
// Source: UI-SPEC Phase 8 contract
import { useState, useRef, useCallback } from 'react'

interface InstructionInputProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

export function InstructionInput({ onSubmit, disabled }: InstructionInputProps) {
  const [text, setText] = useState('')
  const [expanded, setExpanded] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = useCallback(() => {
    if (!text.trim() || disabled) return
    onSubmit(text.trim())
    setText('')
    setExpanded(false)
    textareaRef.current?.blur()
  }, [text, disabled, onSubmit])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    }
  }, [handleSubmit])

  return (
    <div className="flex-1 flex items-center gap-2">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={() => setExpanded(true)}
        onBlur={() => { if (!text) setExpanded(false) }}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={expanded
          ? 'Describe what you want the agent to do. Be specific about files, functions, and the expected outcome.'
          : 'Describe the code change you want...'
        }
        rows={expanded ? 3 : 1}
        className="flex-1 resize-none rounded-lg px-3 py-2 text-sm"
        style={{
          background: 'rgba(30, 33, 43, 0.4)',
          border: `1px solid ${expanded ? 'var(--color-primary)' : 'var(--color-border)'}`,
          color: 'var(--color-text)',
          height: expanded ? 'auto' : '36px',
          maxHeight: '120px',
          opacity: disabled ? 0.5 : 1,
          fontFamily: 'var(--font-ui)',
        }}
      />
      {expanded && (
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || disabled}
          className="px-3 py-2 rounded-lg text-sm font-semibold text-white"
          style={{
            background: !text.trim() || disabled ? 'rgba(99, 102, 241, 0.3)' : 'var(--color-primary)',
          }}
        >
          Run instruction
        </button>
      )}
    </div>
  )
}
```

### Provider Restructuring (App.tsx)

```typescript
// Phase 8 changes App.tsx:
// - AppShell -> IDELayout
// - WebSocketProvider simplified (Zustand handles event distribution)
import { useState } from 'react'
import { WebSocketProvider } from './context/WebSocketContext'
import { ProjectProvider } from './context/ProjectContext'
import { IDELayout } from './components/layout/IDELayout'
import { ErrorBoundary } from './components/layout/ErrorBoundary'

function App() {
  const [projectId, setProjectId] = useState<string | null>(null)

  return (
    <ErrorBoundary>
      <WebSocketProvider projectId={projectId}>
        <ProjectProvider onProjectChange={setProjectId}>
          <IDELayout />
        </ProjectProvider>
      </WebSocketProvider>
    </ErrorBoundary>
  )
}

export default App
```

### WebSocketContext Simplification

```typescript
// Phase 8: WebSocketContext becomes a thin bridge to Zustand
// It keeps WS connection management but routes events to wsStore
import { createContext, useContext, useEffect, useCallback, type ReactNode } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useWsStore } from '../stores/wsStore'
import type { WSEvent, RunSnapshot } from '../types'

interface WebSocketContextValue {
  send: (data: object) => void
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function WebSocketProvider({ projectId, children }: { projectId: string | null; children: ReactNode }) {
  const { status, send, onMessage } = useWebSocket(projectId)

  // Bridge connection status to Zustand
  useEffect(() => {
    useWsStore.getState().setStatus(status)
  }, [status])

  // Bridge events to Zustand store
  useEffect(() => {
    const unsub = onMessage((event: WSEvent) => {
      const store = useWsStore.getState()

      if (event.seq && event.run_id) {
        store.setLastSeq(event.run_id, event.seq)
      }

      if (event.type === 'snapshot') {
        store.setSnapshot(event as unknown as RunSnapshot)
      } else {
        store.appendAgentEvent(event)
        if (event.type === 'diff' && event.data.file_path) {
          store.setFileChanged(event.data.file_path as string, 'modified')
        }
      }
    })
    return unsub
  }, [onMessage])

  return (
    <WebSocketContext.Provider value={{ send }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocketSend() {
  const context = useContext(WebSocketContext)
  if (!context) throw new Error('useWebSocketSend must be used within WebSocketProvider')
  return context.send
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| react-resizable-panels v3 (`PanelGroup`, `autoSaveId`) | v4 (`Group`, `useDefaultLayout`) | v4.0.0 (2025) | All component names and persistence API changed |
| Zustand v4 (`create(...)`) | Zustand v5 (`create<T>()(...)`) | v5.0.0 (2024) | Curried create for TypeScript, vanilla store by default |
| React Context for all shared state | Zustand for high-frequency, Context for low-frequency | Ecosystem consensus 2024-2025 | Context propagation penalty well-documented |

**Deprecated/outdated:**
- `PanelGroup`, `PanelResizeHandle` component names (v3, replaced in v4)
- `autoSaveId` prop (v3, replaced by `useDefaultLayout` hook in v4)
- `direction` prop (v3, renamed to `orientation` in v4)
- `onCollapse`/`onExpand` callbacks (v3, removed in v4 -- use `onResize`)
- `useWebSocketContext()` for event consumption (Phase 8 replaces with Zustand selectors)

## Open Questions

1. **Separator wrapper component feasibility**
   - What we know: v4 requires `Separator` to be a direct DOM child of `Group`.
   - What's unclear: Whether a React wrapper component (that renders `<Separator {...props} />` with styled children) is acceptable, or if it must literally be `<Separator>` in JSX.
   - Recommendation: Test early. If wrapper breaks layout, use plain `Separator` with `className` directly in `IDELayout`.

2. **useDefaultLayout debounce behavior**
   - What we know: v4 `useDefaultLayout` hook handles localStorage persistence.
   - What's unclear: Whether it debounces saves automatically or fires on every pixel of drag.
   - Recommendation: If jank occurs, add `debounceSaveMs` option (supported by the hook per API docs).

3. **Existing component compatibility in new panels**
   - What we know: `FileTree`, `AgentPanel`, `WorkspaceHome`, `DiffViewer`, `RunProgress` will be mounted in new panel containers.
   - What's unclear: Whether their CSS (height: 100%, overflow assumptions) will work inside `Panel` containers vs CSS grid cells.
   - Recommendation: Panel children should use `h-full overflow-hidden` consistently. May need minor CSS adjustments on existing components.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build/dev | Yes | v25.6.1 | -- |
| npm | Package installation | Yes | (bundled with Node) | -- |
| react-resizable-panels | Panel layout | No (to install) | 4.7.6 target | -- |
| zustand | State management | No (to install) | 5.0.12 target | -- |

**Missing dependencies with no fallback:** None (both packages are installable via npm)

**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright 1.58.2 (E2E only) |
| Config file | `web/playwright.config.ts` |
| Quick run command | `cd web && npx playwright test --grep "TESTNAME"` |
| Full suite command | `cd web && npx playwright test` |

**Note:** No unit test framework (vitest/jest) is configured for the frontend. All validation is E2E via Playwright. Phase 8 does not introduce unit tests (consistent with existing codebase).

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LAYOUT-01 | Three-panel layout visible | E2E | `npx playwright test --grep "three-panel"` | Needs update (existing test checks old labels) |
| LAYOUT-02 | Resize handles work, sizes persist | E2E (manual verification) | Manual: drag handle, reload, verify sizes | N/A |
| LAYOUT-03 | Collapse/expand panels | E2E | `npx playwright test --grep "collapse"` | Wave 0 |
| LAYOUT-04 | Top bar with input, selector, status | E2E | `npx playwright test --grep "top bar"` | Wave 0 |
| LAYOUT-05 | No render storms during WS messages | Manual (React DevTools Profiler) | Manual: verify <10 renders/sec per panel during streaming | N/A |

### Sampling Rate
- **Per task commit:** `cd web && npm run build` (TypeScript + Vite build validates types and imports)
- **Per wave merge:** `cd web && npx playwright test`
- **Phase gate:** Full Playwright suite green + manual render storm verification

### Wave 0 Gaps
- [ ] Update `web/e2e/app.spec.ts` -- existing tests assert on v1.0 UI structure that Phase 8 replaces. Tests for "Explorer" text, textarea location, "AI Agent" label, sidebar structure all need updating to match new layout.
- [ ] No unit test infrastructure exists for stores -- Zustand stores could be unit tested with vitest but that is not in the current testing pattern. Skip for Phase 8.

## Sources

### Primary (HIGH confidence)
- [react-resizable-panels npm](https://www.npmjs.com/package/react-resizable-panels) - v4.7.6 verified
- [react-resizable-panels GitHub](https://github.com/bvaughn/react-resizable-panels) - v4 API changes confirmed
- [react-resizable-panels CHANGELOG](https://github.com/bvaughn/react-resizable-panels/blob/main/CHANGELOG.md) - v4.0.0 breaking changes
- [shadcn-ui/ui Issue #9136](https://github.com/shadcn-ui/ui/issues/9136) - v4 migration confirmed resolved
- [newreleases.io v4.0.0](https://newreleases.io/project/github/bvaughn/react-resizable-panels/release/4.0.0) - Complete v4 breaking changes list
- [DeepWiki react-resizable-panels](https://deepwiki.com/bvaughn/react-resizable-panels/6-examples-and-usage-patterns) - v4 imperative API
- [zustand GitHub](https://github.com/pmndrs/zustand) - v5 API confirmed
- [Zustand Advanced TypeScript Guide](https://zustand.docs.pmnd.rs/learn/guides/advanced-typescript) - `create<T>()(...)` pattern
- Existing codebase: `AppShell.tsx`, `WebSocketContext.tsx`, `ProjectContext.tsx`, `useWebSocket.ts`, `glass.css`, `App.tsx` -- all read directly

### Secondary (MEDIUM confidence)
- [Zustand v5 best practices discussion](https://github.com/pmndrs/zustand/discussions/2867) - Selector patterns
- [TKDodo: Working with Zustand](https://tkdodo.eu/blog/working-with-zustand) - Zustand + React Context complementary pattern
- [React 19 + Zustand compatibility](https://medium.com/@reactjsbd/react-19-state-management-with-zustand-a-developers-guide-to-modern-state-handling-8b6192c1e306) - Confirmed compatible

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Versions verified against npm registry, v4 API changes confirmed via multiple sources
- Architecture: HIGH - Existing codebase fully audited, component tree and data flows documented
- Pitfalls: HIGH - v4 API breaking changes are the primary risk; well-documented across shadcn/ui issues and changelogs

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (30 days -- stable libraries, unlikely to change)
