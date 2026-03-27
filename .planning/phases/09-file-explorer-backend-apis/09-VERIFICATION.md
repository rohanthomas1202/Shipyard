---
phase: 09-file-explorer-backend-apis
verified: 2026-03-27T17:30:00Z
status: gaps_found
score: 8/9 must-haves verified
gaps:
  - truth: "TypeScript and ESLint pass clean (plan 02 acceptance criterion)"
    status: partial
    reason: "FileTree.tsx introduces a new ESLint error: react-hooks/set-state-in-effect at line 23 (setRootEntries([]) called synchronously in useEffect). The plan's acceptance criteria explicitly required ESLint to pass with no errors. The tree is functionally correct but this violates the stated quality bar."
    artifacts:
      - path: "web/src/components/explorer/FileTree.tsx"
        issue: "Line 23: setRootEntries([]) called synchronously inside useEffect body. ESLint rule react-hooks/set-state-in-effect fires. Fix: initialize rootEntries to [] instead of resetting inside the effect, or use a conditional render guard outside the effect."
    missing:
      - "Refactor the early-return branch of the useEffect in FileTree.tsx to avoid synchronous setState. Pattern: move the null-guard to a conditional useMemo or derived state, or initialize rootEntries as [] (already the default) and skip the reset."
human_verification:
  - test: "End-to-end file explorer visual and interaction check"
    expected: "Left panel shows directory tree, expand/collapse works, ignored paths hidden, selected file highlights, M/A/D badges appear during agent runs"
    why_human: "Visual styling, hover behavior, real-time badge appearance during live agent runs, and tree responsiveness cannot be verified without a running browser session"
---

# Phase 09: File Explorer Backend APIs Verification Report

**Phase Goal:** Users can browse project files in a live directory tree and see which files the agent is modifying in real time
**Verified:** 2026-03-27T17:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | /browse returns both files and directories for a project path | VERIFIED | `server/main.py` lines 476-536: endpoint returns `dir_entries + file_entries`, tests `test_browse_returns_files` and `test_browse_file_entry_has_size` pass |
| 2 | /browse filters .git, node_modules, __pycache__, .venv, and other ignored paths | VERIFIED | `_IGNORED_NAMES` set at lines 23-27 of `server/main.py`; `test_browse_filters_ignored` passes |
| 3 | /files endpoint returns file content with detected language | VERIFIED | `server/main.py` lines 539-577: `read_file` returns `{content, language, size, binary, path}`; `test_files_returns_content`, `test_files_markdown_language`, `test_files_css_language` all pass |
| 4 | Path traversal attempts on /browse and /files return 403 | VERIFIED | `is_relative_to(project_root)` check on both endpoints (lines 487, 550); `test_browse_path_traversal` and `test_files_path_traversal` pass |
| 5 | User sees a lazy-loaded directory tree when a project is selected | VERIFIED | `FileTree.tsx` calls `api.browseProject(currentProject.id)` in `useEffect`, stores in `rootEntries`, renders `<TreeNode>` components; wired to `IDELayout.tsx` and `AppShell.tsx` |
| 6 | User can expand and collapse directories to browse files | VERIFIED | `TreeNode.tsx` lines 34-55: `handleToggle` calls `api.browseProject(projectId, entry.path)` on first expand, caches `children`, toggles `expanded` state; children rendered recursively |
| 7 | Files modified by the agent show M/A/D indicators in real time | VERIFIED | `TreeNode.tsx` line 30: `useWsStore((s) => s.changedFiles[entry.path])`; `WebSocketContext.tsx` handles `diff`, `edit_proposed`, `file_created`, `file_deleted` events and calls `setFileChanged` |
| 8 | User can click a file to open it in the editor area | VERIFIED | `TreeNode.tsx` lines 62-63: `useWorkspaceStore.getState().openFile(entry.path)` and `setSelectedPath(entry.path)` called on file click; `openFile` in `workspaceStore.ts` creates a real tab entry |
| 9 | ESLint passes clean on phase-introduced files | FAILED | `FileTree.tsx` line 23 triggers `react-hooks/set-state-in-effect` (ESLint error). Plan 02 acceptance criteria explicitly required "ESLint passes with no errors". TypeScript compilation passes clean. |

**Score:** 8/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `server/main.py` | Enhanced /browse endpoint with project_id, filtering, security | VERIFIED | Lines 476-536: `project_id: str` param, `_IGNORED_NAMES` filter, `is_relative_to` guard, files+dirs returned |
| `server/main.py` | /files endpoint with content and language detection | VERIFIED | Lines 539-577: `read_file` endpoint with `_EXT_TO_LANG`, `_BINARY_EXTS`, 403/404/400 error cases |
| `tests/test_server.py` | Tests for /browse enhancements, /files endpoint, path traversal | VERIFIED | 16 passing tests: `test_browse_returns_files`, `test_browse_filters_ignored`, `test_browse_path_traversal`, `test_files_returns_content`, `test_files_binary_detection`, `test_files_path_traversal` and 10 more |
| `web/src/components/explorer/TreeNode.tsx` | Recursive tree node with expand/collapse and change indicators | VERIFIED | Exists, 146 lines, exports `TreeNode`, wires `api.browseProject`, `useWsStore`, `useWorkspaceStore` |
| `web/src/components/explorer/FileTree.tsx` | File explorer panel with lazy-loading directory tree | VERIFIED (with lint gap) | Exists, loads root on mount, renders `<TreeNode>`, no `RunList` import |
| `web/src/lib/api.ts` | API client functions for /browse and /files | VERIFIED | Lines 38-46: `browseProject` and `readFile` functions present |
| `web/src/types/index.ts` | FileEntry and FileContent types | VERIFIED | `FileEntry`, `BrowseResponse`, `FileContent` interfaces at lines 76-97 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `server/main.py /browse` | `project.path` | `pathlib.Path.is_relative_to()` | VERIFIED | Lines 484-487: `project_root = pathlib.Path(project.path).resolve()`, `target.is_relative_to(project_root)` |
| `server/main.py /files` | `project.path` | `pathlib.Path.is_relative_to()` | VERIFIED | Lines 547-550: same pattern |
| `TreeNode.tsx` | `/browse?project_id=X&path=Y` | `api.browseProject()` on expand | VERIFIED | Line 45: `const res = await api.browseProject(projectId, entry.path)` |
| `TreeNode.tsx` | `wsStore.changedFiles` | `useWsStore` selector | VERIFIED | Line 30: `useWsStore((s) => s.changedFiles[entry.path])` |
| `TreeNode.tsx` | `workspaceStore.openFile` | file click handler | VERIFIED | Lines 62-63: `useWorkspaceStore.getState().openFile(entry.path)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `FileTree.tsx` | `rootEntries` | `api.browseProject(currentProject.id)` in `useEffect` | Yes — calls `/browse` with real `project_id`, response written to state | FLOWING |
| `TreeNode.tsx` | `children` | `api.browseProject(projectId, entry.path)` on expand | Yes — calls `/browse` with real path, response.entries written to state | FLOWING |
| `TreeNode.tsx` | `changeStatus` | `useWsStore((s) => s.changedFiles[entry.path])` | Yes — populated by `setFileChanged` from live WS events | FLOWING |
| `server/main.py /browse` | `entries` | `target.iterdir()` with `pathlib` | Yes — real filesystem listing from resolved project path | FLOWING |
| `server/main.py /files` | `content` | `target.read_text(encoding="utf-8")` | Yes — real file read | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 29 server tests pass | `python3 -m pytest tests/test_server.py -x -v` | 29 passed, 1 warning | PASS |
| 16 browse+files tests pass | `python3 -m pytest tests/test_server.py -k "browse or files" -v` | 16 passed | PASS |
| TypeScript compiles clean | `cd web && npx tsc --noEmit` | No output (exit 0) | PASS |
| ESLint passes clean on phase 09 files | `cd web && npx eslint src/components/explorer/FileTree.tsx src/components/explorer/TreeNode.tsx src/context/WebSocketContext.tsx` | 3 errors in FileTree.tsx (1 new from phase 09) and WebSocketContext.tsx (2 pre-existing from phase 08) | PARTIAL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FILES-01 | Plan 02 | User sees lazy-loaded directory tree of selected project's files | SATISFIED | `FileTree.tsx` loads via `api.browseProject` on mount, renders `<TreeNode>` components |
| FILES-02 | Plan 02 | User can expand/collapse directories | SATISFIED | `TreeNode.tsx` `handleToggle` with cached `children` state |
| FILES-03 | Plan 02 | User sees live M/A/D indicators on files the agent modifies | SATISFIED | `useWsStore(s => s.changedFiles[entry.path])` in `TreeNode.tsx`; WS events tracked in `WebSocketContext.tsx` |
| FILES-04 | Plan 01 | File tree filters .git, node_modules, __pycache__, etc. | SATISFIED | `_IGNORED_NAMES` constant used in `/browse` endpoint; test passes |
| FILES-05 | Plan 02 | User can click file to open in editor | SATISFIED | `useWorkspaceStore.getState().openFile(entry.path)` called on file click |
| API-01 | Plan 01 | /browse returns files in addition to directories | SATISFIED | `file_entries` list constructed alongside `dir_entries`; test `test_browse_returns_files` passes |
| API-02 | Plan 01 | New /files endpoint returns file content with language detection | SATISFIED | `@app.get("/files")` endpoint with `_EXT_TO_LANG`, handles binary, 30+ extensions |
| API-03 | Plan 01 | /browse validates paths within project directory (no traversal) | SATISFIED | `target.is_relative_to(project_root)` raises 403; `test_browse_path_traversal` passes |

All 8 requirements accounted for. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `web/src/components/explorer/FileTree.tsx` | 23 | `setRootEntries([])` synchronous setState inside useEffect body | Warning (ESLint error) | Cascading render risk when project deselected; functionally the tree clears correctly but violates React best practice and the plan's ESLint clean requirement |
| `web/src/context/WebSocketContext.tsx` | 64, 71 | Exports non-component functions from same file as component (react-refresh/only-export-components) | Warning (pre-existing from Phase 08) | Hot reload may be less reliable in dev; not a Phase 09 regression |

### Human Verification Required

#### 1. End-to-End File Explorer Visual Check

**Test:** Start backend (`python3 -m uvicorn server.main:app --reload`) and frontend (`cd web && npm run dev`). Open http://localhost:5173, select or create a project pointing to the Shipyard repo.
**Expected:** Left panel shows a directory tree with folders (agent/, server/, web/, store/, tests/) and files (pyproject.toml, CLAUDE.md, etc.). .git and node_modules are absent. Clicking a directory expands to show children. Clicking the same directory collapses it. Clicking a file highlights it in the tree and opens a tab.
**Why human:** Visual rendering, hover states, scroll behavior, and actual expansion/collapse responsiveness require a running browser.

#### 2. Real-Time M/A/D Indicator Appearance

**Test:** With both backend and frontend running and a project selected, submit an instruction that causes the agent to modify a file. Watch the file tree during execution.
**Expected:** The file being modified shows an amber "M" badge in the tree as the agent runs. If the agent creates a new file, it shows a green "A" badge.
**Why human:** Requires live WebSocket events from a running agent, which cannot be simulated with grep/static analysis.

### Gaps Summary

One gap blocks the "passed" status: `FileTree.tsx` introduces a new ESLint error (`react-hooks/set-state-in-effect`) that the plan's own acceptance criteria required to be absent. The functional behavior is correct — the tree clears when no project is selected and loads when a project is selected. The data flows correctly from backend through Zustand to render. The issue is code quality: a synchronous `setRootEntries([])` call inside the `useEffect` body at line 23. The fix is a one-line change: remove the `setRootEntries([])` call (the default value is already `[]`) and initialize state guards differently, or restructure the effect to avoid the synchronous path.

The two pre-existing `WebSocketContext.tsx` errors are not phase 09 regressions — they were introduced in phase 08 when the file exported two hooks alongside the provider component.

---

_Verified: 2026-03-27T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
