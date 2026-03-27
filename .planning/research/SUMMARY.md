# Project Research Summary

**Project:** Shipyard v1.1 IDE UI Rebuild
**Domain:** VS Code-style IDE UI for an AI coding agent (React SPA with real-time WebSocket streaming)
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

Shipyard v1.1 is a UI rebuild, not a new product. The existing React 19 + Tailwind CSS + FastAPI stack is sound and does not need replacement. The work is surgical: swap the layout engine from CSS grid to `react-resizable-panels`, add three small libraries (`react-resizable-panels`, `diff`, `shiki` — total ~48KB gzipped), introduce a new `WorkspaceProvider` context for IDE UI state, and replace three key components (AppShell, FileTree, DiffViewer) with production-quality equivalents. Two minor backend endpoints are needed — extending `/browse` to include files and adding `GET /files` for content — both using only existing Python dependencies. The architecture research has the highest confidence of any area: the entire existing codebase was audited directly.

The recommended approach is a four-phase build ordered by strict dependency: foundation first (WorkspaceProvider + layout + TopBar), then file explorer (backend + FileExplorer), then editor area (tabs + FileViewer + DiffPanel), then activity stream evolution (ActivityStream absorbing RunProgress). This order is non-negotiable because WorkspaceProvider must exist before any component can open tabs, the backend file endpoints must exist before FileExplorer can render real data, and the tab system must exist before FileViewer/DiffPanel can mount within it.

The dominant risks are all performance-related and all front-loaded: WebSocket render storms, React Context propagation cascade, non-virtualized file tree, and non-virtualized agent stream each require architectural decisions in Phase 1 that are expensive to retrofit later. The research is unambiguous — use Zustand for all high-frequency state (WebSocket events, file statuses), use `react-resizable-panels` for layout, use React Arborist or TanStack Virtual for the file tree, and use Shiki (not Monaco) for syntax highlighting. Taking shortcuts here doubles implementation time when the inevitable rewrite hits.

## Key Findings

### Recommended Stack

The existing stack is kept intact. Three new frontend libraries cover the entire feature surface. `react-resizable-panels` (v4.7, ~8KB) is the industry standard for IDE-style resizable panels — it is what shadcn/ui wraps, handles localStorage persistence natively via `autoSaveId`, and eliminates the panel-resize-jank pitfall at no extra complexity cost. `diff` (jsdiff, v7.0, ~15KB) provides the Myers O(ND) line-diff algorithm needed for a correct side-by-side diff view. `shiki` (v3.0, ~25KB core + grammars on demand) provides VS Code-quality syntax highlighting for the read-only file viewer without the 2MB+ bundle cost of Monaco. No backend Python dependencies are added.

Zustand is not in STACK.md but is strongly implied by PITFALLS.md as a requirement, not an optional optimization. The roadmap should treat it as a Phase 1 dependency.

**Core technologies:**
- `react-resizable-panels` ^4.7: IDE panel layout with drag-resize and collapse — de facto standard, WAI-ARIA compliant, localStorage persistence built-in
- `diff` (jsdiff) ^7.0: Line-level diff computation for side-by-side diff view — Myers O(ND), most widely used JS diff library
- `shiki` ^3.0: Syntax highlighting for read-only file viewer — VS Code TextMate grammars, 200+ languages, on-demand grammar loading
- Zustand (add in Phase 1): State management for high-frequency WebSocket-derived state — required to avoid render storm and Context propagation pitfalls

### Expected Features

**Must have (table stakes):**
- Three-panel resizable layout with collapse — core IDE convention; missing means prototype
- File explorer with real directory tree (lazy-loaded) — cannot review agent work without one
- Syntax-highlighted read-only file viewer in tabs — raw text feels broken in an IDE
- Side-by-side diff view for agent edits with approve/reject — primary agent review workflow
- Top bar with instruction input + project selector — prompt must always be accessible
- Agent activity stream with step timeline — users must see what the agent is doing
- Run status indicator in TopBar — always-visible agent state

**Should have (high-value differentiators to ship in v1.1):**
- Live file change indicators (M/A/D) in file tree — low complexity, high impact for agent observability
- Auto-open diff on approval request — low complexity, dramatically improves edit review UX
- Preview vs pinned tabs (VS Code convention) — prevents tab explosion, expected by power users

**Defer to v1.2:**
- Run history dropdown (requires new backend endpoint, not critical for demo)
- Expandable LLM output in activity stream (agent stream shows step summaries; full output is secondary)
- Keyboard shortcuts beyond existing Ctrl+Shift+P
- Inline approval in activity stream (users can approve in the diff tab)
- In-browser code editing (explicit anti-feature for v1.1 — the agent edits, users review)
- Git graph visualization, terminal panel, file search, minimap

### Architecture Approach

The target architecture adds one new context (WorkspaceProvider), one new layout shell (IDELayout replacing AppShell), four primary components (TopBar, FileExplorer, EditorArea, ActivityStream), and two sub-components (FileViewer, DiffPanel). The existing WebSocketContext and ProjectContext are kept with minor extensions. The key structural principle is single-responsibility: WorkspaceProvider owns client-side UI state only (open tabs, selected path, expanded dirs, changed files map); ProjectContext owns server-side state (projects, runs, instructions); WebSocketContext owns the connection and dispatch. All high-frequency WebSocket-derived state (file statuses, event stream) belongs in Zustand stores outside React reconciliation.

**Major components:**
1. `WorkspaceProvider` — new context managing tab state, selected path, expanded dirs, changed file tracking; consumed by all panels
2. `IDELayout` — replaces AppShell; mounts TopBar + react-resizable-panels PanelGroup
3. `TopBar` — instruction input, project selector, run status indicator (always visible)
4. `FileExplorer` — lazy-loaded recursive file tree from extended `/browse` API; M/A/D indicators from WebSocket diff events; virtualized via React Arborist
5. `EditorArea` — tab container managing FileViewer and DiffPanel; preview/pinned tab semantics
6. `FileViewer` — read-only code display with Shiki syntax highlighting; local state for content (not in Context)
7. `DiffPanel` — side-by-side diff with jsdiff; approve/reject reuses existing `api.patchEdit`; memoized by edit_id
8. `ActivityStream` — evolves from AgentPanel; absorbs RunProgress; virtualized event list via TanStack Virtual

**Backend additions (no new Python dependencies):**
- Extend `GET /browse` to include files (remove `is_dir()` filter, add file metadata)
- Add `GET /files?path=` for file content (pathlib read + mimetypes language detection)
- Add path validation to `/browse` and `/files` to prevent directory traversal (`os.path.commonpath` check)

### Critical Pitfalls

1. **WebSocket render storms** — Each WebSocket message dispatched to `useState` handlers triggers its own render cycle (React 18 batching does not apply across `onmessage` callbacks). At 20-50 messages/second during runs, all panels re-render 20-50 times/second. Prevention: move WebSocket event distribution into a Zustand store; each panel subscribes to its own slice. Must be decided in Phase 1 — retrofitting is a full-codebase rewrite (~2-3 days recovery).

2. **React Context propagation cascade** — The existing `WebSocketContext` bundles stable refs with frequently-changing values (`snapshot`, `status`). Every consumer re-renders on any value change, bypassing `React.memo`. With three IDE panels consuming this context, a snapshot update re-renders every panel simultaneously. Prevention: keep Context only for static data; move all dynamic state to Zustand with fine-grained selectors. Phase 1 architectural decision.

3. **Non-virtualized file tree** — Real project directories include node_modules, __pycache__, dist with thousands of files. Without virtualization, expanding any large directory freezes the browser. The `/browse` endpoint currently has no gitignore filtering (confirmed in codebase audit). Prevention: use React Arborist (virtualized file explorer) from day one; filter node_modules/.git/dist on the backend. Retrofitting virtualization requires a complete component rewrite (~2 days recovery).

4. **Naive diff algorithm** — The existing `DiffViewer.tsx` marks every old line as removed and every new line as added (confirmed: `buildDiffLines` function in codebase). This produces unreadable output and freezes the main thread on files >500 lines. Prevention: use `diff.diffLines()` for actual change computation; memoize computed diffs by `edit_id`; for files >2000 lines, consider Web Worker or fallback summary.

5. **Syntax highlighting bundle bloat and render blocking** — Monaco adds ~2MB to the bundle and 50-100MB per instance; Shiki's `codeToHtml()` is synchronous and blocks 50-200ms on large files if called during render. Prevention: use Shiki only (never Monaco for v1.1); lazy-load via dynamic import; load language grammars on demand; call via `useEffect` so initial render shows plain text; code-split via `React.lazy()`.

## Implications for Roadmap

The architecture research provides an explicit four-phase build order with hard dependencies. This should map directly to roadmap phases.

### Phase 1: Foundation — Layout, State Architecture, TopBar

**Rationale:** WorkspaceProvider and the Zustand state management architecture must exist before any panel component can be built. IDELayout must exist before panels can be placed. This phase also addresses the two highest-recovery-cost pitfalls (render storms, Context cascade) — 2-3 days each to fix retroactively vs. 0 days if designed correctly upfront.

**Delivers:** Working IDE shell with resizable panels, persistent layout sizes, instruction input always visible in TopBar, run status indicator. Panels render as placeholders pending real data.

**Addresses:** Table stakes: resizable three-panel layout, TopBar instruction input, run status indicator, panel collapse/expand

**Avoids:** Pitfall 1 (WebSocket render storms — design Zustand integration here), Pitfall 2 (Context propagation cascade — split state architecture here), Pitfall 6 (panel resize jank — react-resizable-panels)

**Stack:** `react-resizable-panels`, Zustand (install in this phase)

### Phase 2: File Explorer — Backend Extensions + FileExplorer Component

**Rationale:** Depends on Phase 1 (WorkspaceProvider must exist for file selection state and changedFiles map). Backend file endpoints must exist before FileExplorer can show real data. Virtualization must be the foundation — React Arborist has a fundamentally different API from a naive recursive tree and cannot be incrementally added later.

**Delivers:** Real file tree browsing with lazy-loading, M/A/D change indicators during agent runs, files accessible by path, security-hardened backend endpoints.

**Addresses:** Table stakes: file explorer with real directory tree; differentiator: live M/A/D change indicators

**Avoids:** Pitfall 4 (file tree collapse/freeze — React Arborist virtualization from day one), security: Pitfall 10 (/browse path traversal — `os.path.commonpath` validation)

**Stack:** React Arborist (new frontend dependency), backend uses existing Python only

### Phase 3: Editor Area — Tabs, FileViewer, DiffPanel

**Rationale:** Depends on Phase 1 (WorkspaceProvider tab state) and Phase 2 (file content endpoint from `/files`). Tab system must exist before FileViewer/DiffPanel can mount in tabs. Diff algorithm and Shiki loading strategy are architectural decisions that cannot be changed incrementally.

**Delivers:** Full code review workflow — open files in syntax-highlighted tabs, view side-by-side diffs for agent edits, approve/reject from diff view, preview/pinned tab semantics, stale file detection banner.

**Addresses:** Table stakes: syntax-highlighted file viewer, diff view with approve/reject; differentiator: preview vs pinned tabs, auto-open diff on approval request

**Avoids:** Pitfall 3 (diff rendering freeze — jsdiff + memoization), Pitfall 5 (highlighting bloat — Shiki async, not Monaco), Pitfall 8 (tab state loss — local state per component not Context), Pitfall 9 (stale file content — external change banner), Pitfall 11 (glassmorphic diff color conflicts — higher-opacity diff backgrounds, e.g., `rgba(239,68,68,0.25)`)

**Stack:** `shiki`, `diff` (jsdiff) — install in this phase

### Phase 4: Activity Stream — AgentPanel Evolution + RunProgress Absorption

**Rationale:** Depends on Phase 1 (WorkspaceProvider.openDiff for auto-open on approval events). Independent of Phases 2-3 and can overlap them partially. Completing it last ensures the full WorkspaceContext integration is in place. Agent stream virtualization reuses the TanStack Virtual pattern established in Phase 2.

**Delivers:** Unified activity stream replacing both AgentPanel and RunProgress. Virtualized event list for long runs. Auto-opens diff tab when agent requests approval. Step summaries expandable to full agent detail. WebSocket reconnection replays missed events via `lastSeqRef`.

**Addresses:** Table stakes: agent activity stream with step timeline; differentiator: auto-open diff on approval

**Avoids:** Pitfall 7 (agent stream DOM growth — TanStack Virtual with dynamic row heights), UX pitfall: auto-scroll overrides user position (sticky scroll pattern)

### Phase Ordering Rationale

- WorkspaceProvider is a dependency of every panel component — it cannot move out of Phase 1.
- Backend endpoints block FileExplorer from displaying real data — they must precede Phase 2 component work.
- Tab system blocks FileViewer and DiffPanel from mounting — it must precede Phase 3.
- ActivityStream's auto-open-diff behavior requires `WorkspaceProvider.openDiff()` — Phase 1 dependency, but the component itself can be built in Phase 4.
- All performance architecture decisions (Zustand, virtualization) cost 2-3x more to retrofit than to design correctly upfront.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1 (Zustand store architecture):** Zustand was not in STACK.md — it emerged from PITFALLS.md analysis. Store shape for WebSocket event distribution (per-event-type slices vs. unified event log) should be decided before building consumers. Confirm Zustand version and selector patterns for React 19.
- **Phase 2 (React Arborist compatibility):** Not in STACK.md — recommended by PITFALLS.md for virtualized file tree. Confirm React 19 compatibility before starting Phase 2. TanStack Virtual is the fallback if incompatible.
- **Phase 3 (Large-file diff strategy):** PITFALLS.md recommends `@git-diff-view/react` or CodeMirror 6 merge extension for files >2000 lines, but STACK.md recommends jsdiff + custom renderer. Validate the custom renderer approach handles the "Looks Done But Isn't" checklist items (new file with null old_content, deleted file with null new_content, 5000-line file).

Phases with well-documented standard patterns (skip research-phase):

- **Phase 1 (react-resizable-panels layout):** Library is mature, well-documented, API is clear. Standard integration with `autoSaveId` for persistence.
- **Phase 1 (TopBar instruction input):** Moves existing WorkspaceHome textarea to TopBar. Straightforward refactor.
- **Phase 3 (approve/reject actions):** Reuses existing `api.patchEdit` — no new API surface.
- **Phase 4 (WebSocket event subscription):** Uses existing wildcard subscribe pattern unchanged.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All existing dependencies verified in package.json. New libraries verified on npm with version numbers. No speculative choices. |
| Features | HIGH | Based on VS Code UX conventions (de facto standard) and direct audit of existing Shipyard components. Feature boundaries are clear and well-reasoned. |
| Architecture | HIGH | Entire `web/src/` codebase audited directly. Component boundaries, data flows, and integration points based on actual code. Backend endpoints verified in `server/main.py`. |
| Pitfalls | HIGH | Each critical pitfall confirmed against actual codebase: naive diff in `DiffViewer.tsx` (`buildDiffLines`), no path validation in `/browse`, stable refs mixed with dynamic values in `WebSocketContext.tsx` — all verified directly. |

**Overall confidence:** HIGH

### Gaps to Address

- **Zustand version and store shape:** Zustand is recommended by PITFALLS.md but not specified with a version. Add to STACK.md and confirm install during Phase 1 planning. Store shape for WebSocket event distribution should be decided before building consumers.
- **React Arborist + React 19 compatibility:** Confirm before Phase 2 starts. TanStack Virtual is the fallback.
- **Large file diff strategy:** For files >2000 lines, the jsdiff + custom renderer approach may need a Web Worker. The checklist item "Files >5000 lines show graceful fallback" needs an explicit implementation decision in Phase 3 planning.
- **Path normalization for display:** PITFALLS.md flags that raw server absolute paths should not reach the browser. Decide in Phase 2 whether the backend strips the project root or the frontend computes relative paths from the known project root.
- **File content caching strategy:** Decide during Phase 3 whether to cache file contents across tab switches or re-fetch. Re-fetching is simpler and always current; caching is faster for large files but adds invalidation complexity on agent edits.

## Sources

### Primary (HIGH confidence — direct codebase audit)
- `web/src/` — All components, contexts, hooks, types, api module (full audit)
- `server/main.py` — Backend endpoints, `/browse` implementation, path handling
- `web/src/components/DiffViewer.tsx` — Naive diff algorithm confirmed (`buildDiffLines`)
- `web/src/contexts/WebSocketContext.tsx` — Context value mixing stable refs with changing values confirmed
- `web/package.json` — Existing dependency versions confirmed

### Primary (HIGH confidence — library verification)
- [react-resizable-panels npm](https://www.npmjs.com/package/react-resizable-panels) — v4.7.6, 1777 npm dependents
- [diff (jsdiff) npm](https://www.npmjs.com/package/diff) — v7.0, Myers O(ND) algorithm
- [Shiki](https://shiki.style/) — v3.0, VS Code TextMate grammars, 200+ languages

### Secondary (MEDIUM confidence — community sources)
- [React Context Performance Trap: useSyncExternalStore](https://azguards.com/performance-optimization/the-propagation-penalty-bypassing-react-context-re-renders-via-usesyncexternalstore/)
- [Streaming Backends & React: Controlling Re-render Chaos](https://www.sitepoint.com/streaming-backends-react-controlling-re-render-chaos/)
- [React State Management: Context API vs Zustand](https://medium.com/@bloodturtle/react-state-management-why-context-api-might-be-causing-performance-issues-and-how-zustand-can-ec7718103a71)
- [Git Diff View — High-Performance Diff Component](https://mrwangjusttodo.github.io/git-diff-view/)
- [Building High Performance Directory Components in React](https://dev.to/jdetle/memoization-generators-virtualization-oh-my-building-a-high-performance-directory-component-in-react-3efm)
- [Shiki vs react-syntax-highlighter — Vercel AI Elements #14](https://github.com/vercel/ai-elements/issues/14)
- [TanStack Virtual](https://tanstack.com/virtual/latest)
- [react-resizable-panels GitHub](https://github.com/bvaughn/react-resizable-panels)
- VS Code UX conventions (de facto standard for IDE UI patterns)

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
