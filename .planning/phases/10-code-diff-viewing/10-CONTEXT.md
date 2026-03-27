# Phase 10: Code & Diff Viewing - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a tabbed editor area with syntax-highlighted read-only file viewing and real side-by-side diffs for agent edits. Users can open files from the explorer, review proposed edits with proper line-level diffing, and approve/reject changes inline. This phase makes the center panel functional as an IDE editor area.

</domain>

<decisions>
## Implementation Decisions

### Diff Layout & Rendering
- **D-01:** Side-by-side diff layout (old code left, new code right). No unified view toggle.
- **D-02:** 3 context lines around each change hunk (VS Code/GitHub default).
- **D-03:** Full Shiki syntax highlighting on both old and new sides of diffs.
- **D-04:** Approve/Reject buttons stay inline in the diff header (current DiffHeader pattern).
- **D-05:** Each agent edit opens as a separate diff tab (one tab per edit, not stacked in one view).

### Tab Bar Behavior
- **D-06:** VS Code-style horizontal tab strip at top of editor area with close button on hover, active tab highlighted, scrollable overflow.
- **D-07:** Preview/pin tab model: single-click from explorer opens a preview tab (italic title, replaced by next single-click). Double-click pins the tab.

### File Viewer Experience
- **D-08:** Shiki syntax-highlighted code with line number gutter. Read-only, no editing.
- **D-09:** Binary files show centered placeholder: icon + "Binary file -- cannot display". Empty files show "Empty file" message.

### Editor Area Routing
- **D-10:** Center panel is always tab-driven. Welcome tab shown when no files/diffs are open. RunProgress moves to the agent stream (right panel).
- **D-11:** When agent proposes an edit, diff tab auto-opens and focuses. User immediately sees the change for approval.

### Claude's Discretion
- Tab max count and overflow scrolling behavior
- Shiki theme choice (should match glassmorphic dark aesthetic)
- Welcome tab content/layout
- Exact tab strip styling within the glassmorphic design system

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Editor Components
- `web/src/components/editor/DiffViewer.tsx` -- Current naive diff implementation to replace with jsdiff + side-by-side
- `web/src/components/editor/DiffHeader.tsx` -- Existing glassmorphic diff header with Accept/Reject buttons (keep pattern)
- `web/src/components/editor/DiffLine.tsx` -- Current diff line rendering (replace with side-by-side layout)

### State Management
- `web/src/stores/workspaceStore.ts` -- Already has Tab type (file|diff|welcome), openFile(), openDiff(), closeTab(), setActiveTab(). Extend for preview/pin model
- `web/src/stores/wsStore.ts` -- WebSocket events for detecting edit proposals (auto-open diff tabs)

### Layout Integration
- `web/src/components/layout/IDELayout.tsx` lines 164-195 -- Center panel currently shows WorkspaceHome|DiffViewer|RunProgress. Replace with tab-driven routing
- `web/src/components/home/RunProgress.tsx` -- Moves from center panel to right panel (agent stream)

### API
- `web/src/lib/api.ts` -- Has `readFile()` for /files endpoint (content + language) and `getEdits()` for diff data
- `web/src/types/index.ts` -- Has FileContent, Edit types

### Research
- `.planning/research/ARCHITECTURE.md` -- FileViewer, DiffPanel component designs, Shiki + jsdiff recommendations
- `.planning/research/PITFALLS.md` lines 59-115 -- Naive diff problem, Shiki performance considerations, virtual scrolling guidance

### Prior Phase Context
- `.planning/phases/08-foundation-layout-state-architecture-topbar/08-CONTEXT.md` -- Glassmorphic design decisions, panel layout, Zustand architecture

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DiffHeader.tsx`: Glassmorphic header with file path, step label, Accept/Reject buttons -- keep and extend
- `workspaceStore.ts`: Tab management skeleton already built (openFile, openDiff, closeTab, setActiveTab) -- extend with preview/pin
- `api.readFile()`: Returns `{ content, language, size, binary }` -- ready for file viewer
- `api.getEdits()`: Returns Edit[] with old_content/new_content -- ready for diff computation

### Established Patterns
- Tailwind CSS 4 for styling, inline style objects for glassmorphic effects
- Zustand stores with fine-grained selectors (useWsStore, useWorkspaceStore)
- Material Symbols for icons
- `var(--font-code)` for monospace, `var(--color-*)` CSS custom properties

### Integration Points
- IDELayout center panel: replace conditional rendering with TabBar + tab content area
- FileTree onClick: already calls `workspaceStore.openFile(path)` -- needs to trigger preview tab
- WebSocket `edit_proposed` events: trigger `workspaceStore.openDiff(editId)` for auto-open
- RunProgress: relocate from center panel to right panel (agent stream area)

</code_context>

<specifics>
## Specific Ideas

- Diffs must use a real diff algorithm (jsdiff) -- the current naive "all old = red, all new = green" is the #1 UX issue to fix
- Side-by-side layout should feel like VS Code's diff editor
- Preview tab model prevents tab explosion when browsing the file explorer
- Auto-opening diff tabs on edit proposals creates a seamless review workflow

</specifics>

<deferred>
## Deferred Ideas

- Unified diff toggle (ADIFF-01 in requirements -- future phase)
- In-file search (Ctrl+F) -- could be added later
- Inline approval actions in agent stream (ADIFF-02 -- future phase)

</deferred>

---

*Phase: 10-code-diff-viewing*
*Context gathered: 2026-03-27*
