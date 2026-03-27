# Pitfalls Research

**Domain:** VS Code-style IDE UI in React with WebSocket streaming (v1.1 frontend rebuild for existing Shipyard agent)
**Researched:** 2026-03-27
**Confidence:** HIGH (patterns well-documented across multiple sources, verified against Shipyard codebase)

## Critical Pitfalls

### Pitfall 1: WebSocket Message Floods Causing Render Storms

**What goes wrong:**
During active agent runs, the Shipyard backend emits high-volume WebSocket events -- P1 `stream` events fire continuously during LLM token streaming, `diff` events fire per edit, and P2 `status`/`file` events batch-flush at node boundaries. The existing `WebSocketContext` dispatches each message via `handlersRef.current.forEach(handler => handler(data))`. If consuming components store events in React state via `useState`, each `setState` triggers a render cycle. WebSocket `onmessage` fires once per message on separate event loop ticks, so React 18's automatic batching does NOT collapse them -- each message gets its own render. At 20-50 messages/second during active streaming, every subscribed panel re-renders 20-50 times per second.

**Why it happens:**
Developers build the first panel (agent stream), wire it to `subscribe('stream', handler)`, and it works fine in isolation. Then they add the file explorer subscribing to `file` events and the diff view subscribing to `diff` events. Since the WebSocket context dispatches to all handlers on every message, and React cannot batch across separate `onmessage` callbacks, render frequency scales with message volume times subscriber count.

**How to avoid:**
1. Buffer incoming WebSocket messages in a mutable ref and flush on `requestAnimationFrame` cadence. This collapses N messages/frame into 1 render per 16ms. Implement in the WebSocket hook layer, not individual components.
2. Replace `WebSocketContext` event distribution with a Zustand store. Each panel selects only its relevant slice: `useStore(s => s.agentEvents)` vs `useStore(s => s.fileStatuses)`. Zustand's selector-based subscriptions mean only components reading changed slices re-render.
3. Wrap each panel component in `React.memo` with stable props.

**Warning signs:**
- React DevTools Profiler shows >30 renders/sec on any component during agent runs
- CPU above 50% in browser during streaming with no user interaction
- Typing in the instruction input lags while agent is running

**Phase to address:**
Phase 1 (layout/infrastructure) -- the WebSocket-to-state bridge must be designed correctly from the start. Retrofitting batching onto naive `useState` handlers requires touching every consumer.

---

### Pitfall 2: React Context Propagation Penalty Across All Panels

**What goes wrong:**
The existing `WebSocketContext` bundles `status`, `snapshot`, `subscribe`, `send`, and `lastSeqRef` in one value object. Any component calling `useWebSocketContext()` re-renders when ANY of these change -- even if it only uses `subscribe`. When the IDE adds three panels all consuming this context, a snapshot update (every few seconds during runs) re-renders the file explorer, code view, AND agent stream simultaneously. React Context sets a "propagation bit" on every consumer fiber, bypassing `React.memo` bailout.

**Why it happens:**
React Context has no selector mechanism. You subscribe to the entire value object. The current `WebSocketContext` mixes stable refs (`subscribe`, `send`, `lastSeqRef`) with frequently-changing values (`snapshot`, `status`). Every consumer gets the propagation penalty even if it only needs the stable parts.

**How to avoid:**
1. Migrate high-frequency state (events, file statuses, snapshot) to Zustand stores with fine-grained selectors. Keep React Context only for truly static data (project config, theme).
2. The WebSocket connection itself stays as a hook/ref, but event distribution and derived state must go through Zustand.
3. If keeping any Context, split aggressively: `WSConnectionContext` (send + status, changes rarely) vs nothing else. Put everything dynamic in Zustand.
4. Use `useSyncExternalStore` for external data sources to avoid Context propagation entirely.

**Warning signs:**
- React DevTools "Highlight updates" shows all panels flashing on every WebSocket message
- Adding a new Context consumer in one panel causes performance regression in another
- Panel resize feels sluggish because unrelated components re-render

**Phase to address:**
Phase 1 (layout/infrastructure) -- state management architecture must be decided before building panel components. Migrating from Context to Zustand after panels exist requires changing every consumer file.

---

### Pitfall 3: Diff View Freezing the Main Thread on Large Files

**What goes wrong:**
Side-by-side diff for agent edits renders old and new file content. The existing `DiffViewer.tsx` uses a `buildDiffLines` function that naively marks every old line as removed and every new line as added (confirmed in codebase audit). Beyond producing unreadable output, for files over 500 lines, rendering thousands of DOM nodes with syntax highlighting spans blocks the main thread for 1-3 seconds. During active runs where multiple files are edited in sequence, the diff view re-mounts repeatedly.

**Why it happens:**
Two compounding issues: (a) The current diff algorithm is wrong -- it does not compute actual line-level differences, making every line appear changed. (b) Most React diff libraries render the entire diff without virtualization, producing 5000-10000 DOM nodes for a 1000-line file with highlighting.

**How to avoid:**
1. Replace the naive diff with `diff.diffLines()` from jsdiff. Show context lines (unchanged), additions (green), and removals (red). Include 3 lines of surrounding context per hunk.
2. Use a virtualized diff renderer. Best options: `@git-diff-view/react` (built-in virtualization, GitHub-style UI, split/unified) or CodeMirror 6 merge extension (handles massive files natively).
3. Compute diffs once on arrival, memoize by `edit_id` in the store. Never recompute on re-render.
4. For large files (>2000 lines), compute diffs in a Web Worker.
5. Lazy-load diff view -- show summary line ("Modified 15 lines in file_ops.py") until user clicks to expand.

**Warning signs:**
- Diff view shows entire file as removed then entire file as added (naive diff)
- Clicking an edit takes >500ms before diff appears
- Chrome DevTools shows "Recalculate Style" or "Layout" entries >100ms

**Phase to address:**
Phase 3 (diff view) -- must choose virtualized approach from the start. Non-virtualized diff components cannot be incrementally improved; they require a complete rewrite.

---

### Pitfall 4: File Tree Collapse with Real Project Directories

**What goes wrong:**
The file explorer renders the target project's directory tree. The existing `/browse` endpoint does not filter node_modules, .git, __pycache__, or build artifacts. Real projects have hundreds to thousands of files. Without virtualization, expanding a directory with 200+ children creates 200+ DOM nodes instantly. With real-time status indicators from WebSocket events, each status change can re-render the entire tree.

**Why it happens:**
Naive tree implementations render all nodes in expanded subtrees. The `/browse` endpoint returns all entries without gitignore filtering. Each tree node subscribes to the same status state object, so one file status change propagates to every rendered node.

**How to avoid:**
1. Backend: filter `/browse` results using `git ls-files` or exclude node_modules, .git, __pycache__, dist, build, .next, vendor. Add a `limit` parameter (default 500 per directory).
2. Use a virtualized tree from day one. React Arborist is purpose-built for file explorers (renders only visible ~30 rows). Alternative: headless-tree + TanStack Virtual.
3. File status state: flat Map keyed by path in Zustand. Each tree node selects only its own status: `useStore(s => s.fileStatuses.get(path))`.
4. Lazy-load directory contents on expand, not upfront.
5. Debounce file status updates -- batch WebSocket `file` events within 100ms.

**Warning signs:**
- Expanding any directory causes visible freeze (>100ms)
- Opening a project with node_modules freezes the browser tab
- Tree scroll stutters while agent is running

**Phase to address:**
Phase 2 (file explorer) -- virtualization must be the foundation. React Arborist has a fundamentally different API than recursive `<TreeNode>` rendering.

---

### Pitfall 5: Syntax Highlighting Bloating Bundle and Blocking Renders

**What goes wrong:**
Loading a full editor engine on initial page load blocks time-to-interactive. Monaco: 2MB+ bundle, 50-100MB memory per instance. Even Shiki's `codeToHtml()` is synchronous and takes 50-200ms on large files (1000+ lines), causing visible jank on tab switch. Developers forget to dispose editor instances when closing tabs, leaking memory.

**Why it happens:**
Monaco loads the complete VS Code editor engine including TypeScript workers. Shiki's TextMate grammar tokenization is CPU-intensive when run synchronously during React render. For Shipyard v1.1 where users view agent edits read-only, full editor engines are overkill.

**How to avoid:**
1. Use Shiki for read-only display and diffs. It produces pre-rendered HTML with no editor overhead. Vercel's AI Elements switched to Shiki for a "huge initial rendering boost."
2. Lazy-load Shiki with `await createHighlighter()` -- never import at module level. Show plain text first via `useEffect`, then swap in highlighted version.
3. For files >2000 lines, only highlight the visible viewport plus buffer. Use CodeMirror 6 (viewport-aware lazy highlighting) only if full-file highlighting proves too slow.
4. Load language grammars dynamically -- only fetch the grammar for the detected language.
5. Code-split the highlighting engine via `React.lazy()` + `import()`. Keep it out of the initial bundle.
6. Build extension-to-language map with `'text'` fallback for unknown extensions.
7. Never use Monaco unless v1.2 adds in-IDE editing with autocomplete.

**Warning signs:**
- Initial page load >3 seconds (check Network tab)
- Memory grows 50MB+ per opened file tab (Chrome Task Manager)
- Tab switching delay >200ms
- Bundle analyzer shows a single chunk >500KB

**Phase to address:**
Phase 3 (code/diff view) -- highlighting strategy is an architectural decision affecting bundle, memory, and component design.

---

### Pitfall 6: Panel Resize Jank from Layout Thrashing

**What goes wrong:**
Dragging a panel resize handle fires continuous pointer events. Components inside panels using `ResizeObserver` (TanStack Virtual needs container height, CodeMirror measures viewport) fire callbacks on every pixel of drag. Each callback triggers setState, re-render, layout, then ResizeObserver fires again. This cascade produces resize at <15fps.

**Why it happens:**
ResizeObserver is designed to fire on any dimension change. During active resize, dimensions change every 16ms. If each observation triggers a React re-render with layout-dependent content, you get a feedback loop: CSS resize -> observer fires -> setState -> render -> layout -> observer fires again.

**How to avoid:**
1. Use `react-resizable-panels` v4 (by bvaughn). Uses CSS `flex-grow` internally, is the industry standard, and is what shadcn/ui wraps. ~7KB gzipped.
2. Set `autoSaveId` on PanelGroup for localStorage persistence.
3. During active drag, throttle or defer re-measurements. Only recalculate virtual list heights on `onDragEnd`.
4. Apply `contain: layout` CSS on panel containers.
5. Never set React state from ResizeObserver during active drag. Track "resize in progress" via ref.

**Warning signs:**
- Resize handle lags behind cursor
- CPU spikes to 100% during drag
- Virtual lists show blank rows during resize

**Phase to address:**
Phase 1 (layout) -- the panel system is the structural foundation. `react-resizable-panels` prevents this entire class of issue.

---

### Pitfall 7: Agent Stream DOM Growing Without Bound

**What goes wrong:**
The agent stream receives hundreds of events per run (plan steps, file reads, edits, validations, token streams). Appending each as a React component creates an ever-growing DOM. After 500+ events (typical for multi-step runs), scrolling lags. Auto-scroll fights user scroll position.

**Why it happens:**
DOM grows linearly with events. Auto-scroll via `scrollIntoView()` triggers forced reflow. When user scrolls up to read earlier events, the next event's auto-scroll yanks them back to the bottom.

**How to avoid:**
1. Virtualize the event list from day one with TanStack Virtual (dynamic row heights).
2. "Sticky scroll": auto-scroll only when user is at bottom. Show floating "N new events" badge when scrolled up.
3. Collapse event content by default -- show one-line summaries ("Editing file_ops.py: updating parse function"). Expand to full LLM output on click.
4. Cap rendered buffer at ~1000 events. Older events page in on scroll-up.
5. `React.memo` on event row components -- most never change after initial render.

**Warning signs:**
- Stream scroll choppy after 10+ edited files
- Memory grows continuously during long runs
- DOM node count past 5000

**Phase to address:**
Phase 4 (agent stream) -- establish virtualization pattern in Phase 2 (file tree) and reuse.

---

## Moderate Pitfalls

### Pitfall 8: Tab State Loss on Context Re-Render

**What goes wrong:**
If the workspace/tab provider re-renders due to a parent context update (WebSocket reconnection, project switch), all open tab state (scroll positions, expanded sections, unsaved selections) resets.

**How to avoid:**
Store tab state in `useRef` and sync to `useState` only on tab open/close. Keep workspace state independent of WebSocket state. Or use Zustand for tab state (not affected by Context re-renders).

**Phase to address:** Phase 3 (editor area/tabs).

---

### Pitfall 9: Stale File Content After Agent Edit

**What goes wrong:**
User opens a file in the code viewer. Agent edits that file. The viewer still shows old content.

**How to avoid:**
When a `diff` event arrives for an open file's path, show a "file changed externally" banner with a reload button. Don't auto-reload (user might be reading). Auto-reload only if the tab is not focused.

**Phase to address:** Phase 3 (editor area integration).

---

### Pitfall 10: `/browse` Endpoint Path Traversal

**What goes wrong:**
The `/browse` endpoint accepts arbitrary paths. A request could read files outside the project directory.

**How to avoid:**
Backend must validate the requested path is within the project directory: `os.path.commonpath([project_path, requested_path]) == project_path`. Reject requests outside the boundary with 403.

**Phase to address:** Phase 2 (file explorer backend changes).

---

### Pitfall 11: Glassmorphic Styling Conflicts with Diff Colors

**What goes wrong:**
The frosted glassmorphic design system uses translucent backgrounds. Diff line backgrounds (red/green additions/removals) become nearly invisible against translucent panels.

**How to avoid:**
Use higher-opacity backgrounds for diff lines (`rgba(239,68,68,0.25)` not `0.1`). Test diff visibility against actual panel backgrounds. Consider a solid dark background for the code/diff area specifically, even if surrounding chrome is glassmorphic.

**Phase to address:** Phase 3 (diff view styling).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| React Context for all shared state | Fast to implement, no new dependency | Re-render cascade across all panels; must refactor to Zustand later | Never for high-frequency state. OK for project config, theme |
| Non-virtualized lists | Simpler code, no TanStack Virtual dependency | UI freezes at >200 items; complete rewrite to add virtualization | Never -- Shipyard targets real codebases with 500+ files |
| Monaco for read-only display | "Looks like VS Code" immediately | 2MB bundle, 100MB per instance | Never for v1.1. Only if v1.2 adds in-IDE editing with autocomplete |
| Inline `useState` per WebSocket event | Obvious data flow, easy to debug | Each setState = separate render, no batching | OK for Phase 1 prototype only; migrate to Zustand store by Phase 2 |
| Single shared WebSocket subscriber for all panels | Simple architecture | Every message triggers every panel | Never -- each panel must subscribe to its own event types |
| Naive diff algorithm (mark all old as removed, all new as added) | Trivial implementation | Diffs are unreadable, defeats the purpose of the view | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Existing WebSocketContext + new panels | Adding more `useWebSocketContext()` calls, each re-rendering on snapshot/status change | Zustand store ingests WebSocket events. Panels subscribe to specific slices. WebSocket hook pushes into store, not Context |
| Existing ProjectContext + file explorer | Putting file tree expanded/selected state inside ProjectContext | File tree state in its own Zustand store. ProjectContext only provides project path/id |
| P0/P1/P2 event priorities + UI | Treating all events identically | P0 (approval, error): modal/overlay interruption. P1 (stream, diff): panel-specific immediate update. P2 (status, file): batch on rAF |
| Backend absolute paths + display | Showing `/Users/rohanthomas/Shipyard/agent/graph.py` in UI | Strip project root. Display `agent/graph.py`. Either server sends relative paths or frontend computes from known root |
| Edit old_content/new_content + diff | Recomputing diff from full strings on every render | Compute once on arrival, memoize by edit_id in store |
| useHotkeys + new keyboard shortcuts | Hotkey conflicts between panels (arrow keys for tree vs diff scroll) | Scope hotkeys to focused panel. Track panel focus. Hotkey handler checks focus before firing |
| react-resizable-panels + ResizeObserver | Observer fires every pixel of drag causing cascading re-renders | Debounce observer during active drag. Use `onLayout` (drag end) for expensive recalculations |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Every WS message triggers setState | CPU during streaming, input lag | rAF batching + Zustand selectors | >10 msg/sec (normal during runs) |
| Rendering all file tree nodes | Expand directory freezes UI | React Arborist / TanStack Virtual | >100 children in directory |
| Synchronous Shiki highlighting | Tab switch jank | Async highlight via useEffect, viewport-only for large files | Files >500 lines |
| Full file content in React state | GC pressure, memory growth | Zustand store outside reconciliation; pass only visible ranges | >5 tabs, any file >500 lines |
| Unthrottled ResizeObserver | Layout thrashing during resize | Throttle to 1 per rAF; defer during drag | Any panel with virtualized list |
| Agent stream unbounded DOM | Scroll lag, memory growth | TanStack Virtual with dynamic heights | >300 events per run |
| CSS-in-JS runtime for panel styling | Recalculation on resize | Tailwind (already in stack), zero runtime | During any high-frequency update |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `dangerouslySetInnerHTML` for syntax highlighting | XSS if file contains malicious HTML | Use Shiki's `codeToHast()` + `hast-util-to-jsx-runtime` for React elements, not raw HTML |
| Full server paths in browser | Exposes filesystem structure | Strip to project-relative paths |
| `/browse` without path validation | Directory traversal reads arbitrary files | Validate path is within project root (`os.path.commonpath` check) |
| Raw LLM output rendered as HTML | XSS from model output | Render in `<pre>` or markdown renderer with HTML disabled |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Auto-scroll overrides user position | Cannot read earlier events during active run | Sticky scroll: auto only at bottom. "N new events" badge when scrolled up |
| File tree shows node_modules, .git | Overwhelming, slow, signal buried | Respect .gitignore. Use `git ls-files`. Toggle for ignored files |
| No loading state during diff computation | Click, nothing for 500ms, then sudden appearance | Skeleton/spinner immediately. Async diff computation |
| Panel sizes not persisted | Resize, refresh, reset to defaults | `autoSaveId` on PanelGroup stores to localStorage |
| Raw LLM output shown by default | Walls of text, impossible to follow | Summary lines by default. Expand on click |
| Diff without context lines | Cannot orient where change occurred in file | 3 lines of context per hunk (git diff default) |
| No visual connection between agent step and file | "Step 3: edit graph.py" but no way to navigate | Click file path in stream to select in explorer and open diff |
| Missing keyboard navigation in tree | Mouse-only slows power users | Arrow keys, Enter, Escape following VS Code conventions |

## "Looks Done But Isn't" Checklist

- [ ] **File explorer:** Keyboard navigation (arrow keys, Enter, Escape) works without mouse
- [ ] **Diff view:** Scroll sync between old/new panels in side-by-side mode
- [ ] **Diff view:** Handles new files (old_content is null) and deleted files (new_content is null) gracefully
- [ ] **Diff view:** Files >5000 lines show graceful fallback, not browser freeze
- [ ] **Panel resize:** Minimum size constraints prevent collapsing to 0px
- [ ] **Panel resize:** Sizes persist across page reload (check localStorage)
- [ ] **Agent stream:** WebSocket reconnection replays missed events via `lastSeqRef`
- [ ] **Agent stream:** Empty state before any run starts (not blank white space)
- [ ] **File status indicators:** Rapid updates (10 in 100ms) don't cause flickering
- [ ] **Tab bar:** 20+ open files show scroll/overflow, not broken layout
- [ ] **Dark theme:** Syntax highlighting colors match IDE chrome (no jarring mismatch)
- [ ] **WebSocket disconnect:** Clear visual indicator when disconnected/reconnecting
- [ ] **Language detection:** Unknown file extensions fall back to plain text, not error

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| WebSocket render storms | MEDIUM | Add rAF batching between WS hook and stores. Modifies distribution path, not panels. ~1 day |
| Context propagation cascade | HIGH | Migrate Context to Zustand. Touches every file using `useWebSocketContext()`. ~2-3 days |
| Non-virtualized diff | HIGH | Complete rewrite -- virtualized components have different API/data flow. ~2 days |
| Non-virtualized tree | HIGH | React Arborist rewrite -- fundamentally different API than recursive nodes. ~2 days |
| Panel resize jank | LOW | Drop-in `react-resizable-panels` if no custom logic built yet. ~0.5 day |
| Highlighting bloat | MEDIUM | Swap Monaco/heavy lib for Shiki. Wrapper can maintain same props. ~1-2 days |
| Agent stream DOM growth | MEDIUM | Add TanStack Virtual. Dynamic row heights are the challenge. ~1 day |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| WebSocket render storms | Phase 1 (layout/infra) | Profiler: <10 renders/sec per panel during streaming |
| Context propagation cascade | Phase 1 (layout/infra) | File selection change does NOT re-render agent stream (DevTools highlight) |
| Diff rendering freeze | Phase 3 (diff view) | 2000-line file diff renders in <200ms |
| File tree collapse | Phase 2 (file explorer) | 500-child directory expands without frame drops (60fps) |
| Syntax highlighting bloat | Phase 3 (code/diff view) | No single bundle chunk >300KB; 10 tabs under 200MB |
| Panel resize jank | Phase 1 (layout) | Resize drag at 60fps (Chrome FPS overlay) |
| Agent stream DOM growth | Phase 4 (agent stream) | 1000 events, stream scroll at 60fps, constant DOM node count |

## Sources

- [React Context Performance Trap: useSyncExternalStore](https://azguards.com/performance-optimization/the-propagation-penalty-bypassing-react-context-re-renders-via-usesyncexternalstore/)
- [Streaming Backends & React: Controlling Re-render Chaos](https://www.sitepoint.com/streaming-backends-react-controlling-re-render-chaos/)
- [React State Management: Context API vs Zustand](https://medium.com/@bloodturtle/react-state-management-why-context-api-might-be-causing-performance-issues-and-how-zustand-can-ec7718103a71)
- [Handle large files - react-diff-viewer Issue #25](https://github.com/praneshr/react-diff-viewer/issues/25)
- [Git Diff View - High-Performance Diff Component](https://mrwangjusttodo.github.io/git-diff-view/)
- [Building High Performance Directory Components in React](https://dev.to/jdetle/memoization-generators-virtualization-oh-my-building-a-high-performance-directory-component-in-react-3efm)
- [Monaco Editor Memory Use - Issue #132](https://github.com/react-monaco-editor/react-monaco-editor/issues/132)
- [Shiki vs react-syntax-highlighter - Vercel AI Elements #14](https://github.com/vercel/ai-elements/issues/14)
- [react-resizable-panels](https://github.com/bvaughn/react-resizable-panels)
- [TanStack Virtual](https://tanstack.com/virtual/latest)
- Codebase audit: `DiffViewer.tsx` buildDiffLines (naive diff confirmed)
- Codebase audit: `/browse` endpoint in `server/main.py` (no path validation)
- Codebase audit: `WebSocketContext.tsx` (bundles stable refs with changing values)
- Codebase audit: `useWebSocket.ts` (per-message dispatch, no batching)

---
*Pitfalls research for: VS Code-style IDE UI in React with WebSocket streaming*
*Researched: 2026-03-27*
