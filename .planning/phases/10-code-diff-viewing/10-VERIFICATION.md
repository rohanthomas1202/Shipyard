---
phase: 10-code-diff-viewing
verified: 2026-03-27T18:15:00Z
status: gaps_found
score: 3/4 must-haves verified
gaps:
  - truth: "User sees side-by-side diff view with actual line-level diffing"
    status: partial
    reason: "Implementation is correct and substantive, but shiki and diff packages are installed in node_modules yet absent from package.json and package-lock.json. A fresh `npm install` on a clean checkout will fail to install these dependencies, breaking the build in CI or on new machines."
    artifacts:
      - path: "web/package.json"
        issue: "shiki, diff, hast-util-to-jsx-runtime, @types/diff are not listed in dependencies or devDependencies. They are installed in the local node_modules only."
    missing:
      - "Add shiki to package.json dependencies"
      - "Add diff to package.json dependencies"
      - "Add hast-util-to-jsx-runtime to package.json dependencies"
      - "Add @types/diff to package.json devDependencies"
      - "Run `npm install` to regenerate package-lock.json with these entries"
human_verification:
  - test: "Open a project, run the agent so it proposes an edit. Verify the diff tab opens automatically."
    expected: "A tab with compare_arrows icon appears and is focused. Left side shows old code, right side shows new code with red/green line highlights. Changed lines correctly identified — not all-old-red all-new-green."
    why_human: "Requires a live agent run to trigger the edit_proposed WebSocket event."
  - test: "Click a .py or .tsx file in the explorer. Verify syntax highlighting."
    expected: "Code displays with Shiki vitesse-dark token colors. Line numbers visible in gutter. Language auto-detected from extension."
    why_human: "Visual syntax-highlight quality cannot be confirmed programmatically."
---

# Phase 10: Code Diff Viewing Verification Report

**Phase Goal:** Users can review agent edits with syntax-highlighted code and proper side-by-side diffs in a tabbed editor area
**Verified:** 2026-03-27T18:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User sees side-by-side diff with actual line-level diffing | ⚠ PARTIAL | SideBySideDiff.tsx is fully implemented with `structuredPatch({context:3})`, correct red/green classification, hunk separators, and synchronized scroll. However `diff` and `shiki` are missing from package.json — a fresh install breaks. |
| 2 | User sees syntax-highlighted code in any file tab | ✓ VERIFIED | FileViewer.tsx calls `highlightCode()` via useEffect, renders Shiki HTML output. Language auto-detected from file extension via `mapLanguage()` in shiki.ts. Fallback to plain text while loading. |
| 3 | User can open multiple files/diffs in tabs and close them | ✓ VERIFIED | TabBar.tsx + TabItem.tsx render `openTabs` from workspaceStore. Close button calls `closeTab`. Middle-click also closes. `openFile`/`openDiff`/`closeTab`/`setActiveTab` all wired in workspaceStore.ts. |
| 4 | Diff view shows unchanged context lines around changes | ✓ VERIFIED | `structuredPatch(path, path, old, new, '', '', { context: 3 })` at SideBySideDiff.tsx:78. Context lines rendered with `type: 'context'`, transparent background. Hunk separator `@@` rows inserted between hunks. |

**Score:** 3/4 truths verified (1 partial due to missing package.json entries)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/src/components/editor/SideBySideDiff.tsx` | Two-column diff with jsdiff, Shiki, context lines | ✓ VERIFIED | 374 lines. Contains `structuredPatch`, `highlightCode`, `rgba(239,68,68,0.15)` for removed, `rgba(16,185,129,0.15)` for added. |
| `web/src/components/editor/DiffHeader.tsx` | Accept/Reject buttons with confirmation | ✓ VERIFIED | 82 lines. Contains "Accept Edit", "Reject Edit", "Confirm Reject?" with 3s setTimeout. |
| `web/src/components/editor/EditorArea.tsx` | Tab container routing to FileViewer/SideBySideDiff/WelcomeTab | ✓ VERIFIED | 79 lines. Routes `type='file'` to FileViewer, `type='diff'` to SideBySideDiff (with edit fetch cache), falls back to WelcomeTab. |
| `web/src/components/editor/FileViewer.tsx` | Shiki-highlighted read-only code with line gutter | ✓ VERIFIED | 249 lines. useReducer pattern. `api.readFile()` fetch, `highlightCode()` highlight, loading skeleton, binary/empty/error states. |
| `web/src/components/editor/TabBar.tsx` | Horizontal tab strip with scroll | ✓ VERIFIED | 42 lines. `role="tablist"`, scrollbar hidden, renders TabItems from workspaceStore. |
| `web/src/components/editor/TabItem.tsx` | Tab with icon, italic-preview, close button | ✓ VERIFIED | 82 lines. `role="tab"`, `aria-selected`, italic when `!isPinned`, middle-click close. |
| `web/src/components/editor/WelcomeTab.tsx` | Empty state panel | ✓ VERIFIED | 44 lines. "No files open" heading, guidance text, code icon. |
| `web/src/lib/shiki.ts` | Lazy Shiki singleton with dynamic grammar | ✓ VERIFIED | 48 lines. Exports `highlightCode` and `mapLanguage`. vitesse-dark theme. Dynamic `loadLanguage()` with fallback. |
| `web/src/stores/workspaceStore.ts` | openFile/openDiff/closeTab/pinTab actions | ✓ VERIFIED | 100 lines. All actions present. `openFile` implements preview replacement. `openDiff` always pins. `pinTab` added. |
| `web/package.json` | shiki, diff, hast-util-to-jsx-runtime in dependencies | ✗ MISSING | These packages are installed in node_modules but NOT listed in package.json or package-lock.json. A clean checkout + `npm install` will fail to install them. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `IDELayout.tsx` | `EditorArea.tsx` | `import { EditorArea }` | ✓ WIRED | Line 11: `import { EditorArea } from '../editor/EditorArea'`. Rendered at line 179. |
| `EditorArea.tsx` | `workspaceStore.ts` | `useWorkspaceStore` | ✓ WIRED | Lines 12-15: selects `openTabs`, `activeTabId`, `closeTab`, `setActiveTab`. |
| `FileViewer.tsx` | `shiki.ts` | `highlightCode()` | ✓ WIRED | Line 4: `import { highlightCode }`. Called in useEffect at line 83. |
| `FileViewer.tsx` | `api.ts` | `api.readFile()` | ✓ WIRED | Line 3: `import { api }`. Called at line 63 in fetch effect. |
| `SideBySideDiff.tsx` | `diff` (jsdiff) | `import { structuredPatch }` | ✓ WIRED | Line 1: `import { structuredPatch } from 'diff'`. Called at line 75. |
| `SideBySideDiff.tsx` | `shiki.ts` | `highlightCode()` | ✓ WIRED | Line 3: `import { highlightCode, mapLanguage }`. Called at lines 154-157. |
| `EditorArea.tsx` | `SideBySideDiff.tsx` | render on `type='diff'` | ✓ WIRED | Line 8: import. Rendered at line 65 when `activeTab.type === 'diff' && currentEdit`. |
| `WebSocketContext.tsx` | `workspaceStore.ts` | `openDiff()` on edit_proposed | ✓ WIRED | Lines 52-56: checks `event.type === 'approval' && event.data?.event === 'edit.proposed'`, calls `useWorkspaceStore.getState().openDiff(editId)`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `FileViewer.tsx` | `content`, `language` | `api.readFile(projectId, path)` via `/files` API | Yes — fetches from backend file system | ✓ FLOWING |
| `SideBySideDiff.tsx` | `edit` (Edit object) | Passed as prop from EditorArea, fetched via `api.getEdits(currentRun.id)` | Yes — fetches live edit records from backend | ✓ FLOWING |
| `EditorArea.tsx` | `openTabs`, `activeTabId` | `useWorkspaceStore` Zustand store, populated by WS events and user actions | Yes — driven by real WebSocket events and user interactions | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| TypeScript compiles clean | `cd web && npx tsc --noEmit` | Exit 0, no errors | ✓ PASS |
| shiki exists in node_modules | `ls web/node_modules/shiki` | Directory exists, version 4.0.2 | ✓ PASS |
| diff exists in node_modules | `ls web/node_modules/diff` | Directory exists, version 8.0.4 | ✓ PASS |
| shiki NOT in package.json | `grep "shiki" web/package.json` | No match | ✗ FAIL — dependency undeclared |
| diff NOT in package.json | `grep "diff" web/package.json` | No match | ✗ FAIL — dependency undeclared |
| ESLint errors in phase 10 files | `npm run lint` targeted | No errors in editor/ or lib/shiki.ts files | ✓ PASS (lint errors are all in pre-existing files: useWebSocket.ts, AgentPanel.tsx, RunProgress.tsx) |
| `context: 3` present | `grep "context" SideBySideDiff.tsx` | Line 78: `{ context: 3 }` | ✓ PASS |
| openDiff wired in WebSocketContext | `grep "openDiff" WebSocketContext.tsx` | Line 55: `openDiff(editId)` on approval event | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DIFF-01 | 10-02-PLAN.md | Side-by-side diff with proper line-level diff algorithm | ✓ SATISFIED | SideBySideDiff.tsx uses `structuredPatch` from jsdiff. Lines classified as add/remove/context correctly. |
| DIFF-02 | 10-01-PLAN.md | Syntax-highlighted code in editor area | ✓ SATISFIED | FileViewer.tsx + shiki.ts. Language auto-detected. vitesse-dark theme. |
| DIFF-03 | 10-01-PLAN.md | Multiple files/diffs in tabs with close | ✓ SATISFIED | TabBar + TabItem + workspaceStore. Multiple tabs open. Close button functional. |
| DIFF-04 | 10-02-PLAN.md | Context lines around changes | ✓ SATISFIED | `{ context: 3 }` in structuredPatch call. Hunk separators between hunks. |

All 4 requirements are satisfied at implementation level. The partial gap on Truth 1 is a packaging concern, not a missing feature.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `web/package.json` | — | `shiki`, `diff`, `hast-util-to-jsx-runtime`, `@types/diff` absent from declared dependencies | ✗ Blocker | Fresh `npm install` on a clean clone will not install these packages. Build breaks in CI and on new developer machines. |

No stub anti-patterns found in phase 10 files. No TODO/FIXME/placeholder comments in new files. No empty `return null` or `return {}` patterns in the rendering path.

### Human Verification Required

#### 1. Side-by-Side Diff Rendering Quality

**Test:** Start the backend and frontend. Run an agent task that modifies an existing file. When the agent proposes an edit, observe the diff tab.
**Expected:** Diff tab auto-opens. Left column shows old code, right shows new. Changed lines have red/green backgrounds. Lines that didn't change appear as context rows without color. Both columns have Shiki syntax token colors.
**Why human:** The line-level diff algorithm correctness requires visual inspection — automated grep cannot verify that the `extractLineHtml` line-splitting approach correctly aligns Shiki-highlighted content with diff line indices for all real file types.

#### 2. File Syntax Highlighting

**Test:** Open a `.py`, `.tsx`, and `.json` file from the explorer by clicking them.
**Expected:** Each file renders with token-colored syntax (keywords, strings, identifiers in different colors), line numbers in gutter, no raw HTML visible.
**Why human:** Shiki's `codeToHtml` output quality and correct language detection require visual confirmation.

### Gaps Summary

**One gap blocking full readiness: package.json is missing `shiki`, `diff`, `hast-util-to-jsx-runtime`, and `@types/diff`.**

The implementation itself is complete and correct. All four components (SideBySideDiff, FileViewer, TabBar, EditorArea) exist, are substantive, and are wired together end-to-end. TypeScript compiles clean. The diff algorithm uses `structuredPatch` with `{ context: 3 }`, correctly classifies add/remove/context lines, and wires through to Shiki highlighting on both sides. The auto-open diff tab on WebSocket edit proposals is wired.

The gap is purely in packaging: the `npm install` commands ran in the worktree and installed packages locally, but the `package.json` and `package-lock.json` were not updated to declare these dependencies. This means:
- The app currently works on this machine (node_modules has the packages)
- A `git clone + npm install` on any other machine will fail (packages not declared)
- The production build on Heroku/Railway will fail for the same reason

Fix required: add the four packages to package.json and regenerate the lockfile.

---

_Verified: 2026-03-27T18:15:00Z_
_Verifier: Claude (gsd-verifier)_
