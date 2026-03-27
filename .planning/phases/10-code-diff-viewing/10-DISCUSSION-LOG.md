# Phase 10: Code & Diff Viewing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 10-code-diff-viewing
**Areas discussed:** Diff layout & rendering, Tab bar behavior, File viewer experience, Editor area routing

---

## Diff Layout & Rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Side-by-side | Two columns: old code left, new code right. VS Code default | ✓ |
| Unified | Single column with +/- markers. GitHub PR style | |
| Both with toggle | Default to side-by-side, button to switch to unified | |

**User's choice:** Side-by-side
**Notes:** None

---

### Context Lines

| Option | Description | Selected |
|--------|-------------|----------|
| 3 lines | VS Code/GitHub default | ✓ |
| 5 lines | More context for complex changes | |
| Collapsible context | 3 lines default, click to expand | |

**User's choice:** 3 lines
**Notes:** None

---

### Syntax Highlighting in Diffs

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, both sides highlighted | Full Shiki syntax highlighting on old and new code | ✓ |
| No highlighting in diffs | Plain monospace with red/green diff colors | |
| You decide | Claude picks based on performance tradeoffs | |

**User's choice:** Yes, both sides highlighted
**Notes:** None

---

### Approval UX

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in diff header | Accept/Reject buttons in DiffHeader | ✓ |
| Agent stream only | Approval in right panel, diff is read-only | |
| Both locations | Buttons in both diff header and agent stream | |

**User's choice:** Inline in diff header
**Notes:** Keeps current DiffHeader pattern

---

### Multi-Edit Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| One tab per edit | Each edit opens as separate diff tab | ✓ |
| Stacked in one view | All edits in single scrollable view | |
| You decide | Claude picks best integration | |

**User's choice:** One tab per edit
**Notes:** None

---

## Tab Bar Behavior

### Tab Model

| Option | Description | Selected |
|--------|-------------|----------|
| Preview + pin | VS Code style: single-click = preview, double-click = pin | ✓ |
| All tabs pinned | Every opened file gets persistent tab | |
| You decide | Claude picks | |

**User's choice:** Preview + pin
**Notes:** None

---

### Tab Style

| Option | Description | Selected |
|--------|-------------|----------|
| VS Code-style horizontal tabs | Tab strip at top, close button on hover, scrollable | ✓ |
| Minimal breadcrumb tabs | Compact path with dropdown | |
| You decide | Claude picks | |

**User's choice:** VS Code-style horizontal tabs
**Notes:** None

---

## File Viewer Experience

### File Display

| Option | Description | Selected |
|--------|-------------|----------|
| Highlighted code + line numbers | Shiki highlighting with gutter. Read-only | ✓ |
| Highlighted + search | Same plus Ctrl+F in-file search | |
| You decide | Claude decides | |

**User's choice:** Highlighted code + line numbers
**Notes:** None

---

### Binary/Empty Files

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder message | Centered icon + descriptive message | ✓ |
| Show file metadata | File size, type, path info in card layout | |
| You decide | Claude picks simplest | |

**User's choice:** Placeholder message
**Notes:** None

---

## Editor Area Routing

### Center Panel Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Tab-driven always | Tabs control center panel. Welcome tab default. RunProgress moves to right panel | ✓ |
| Hybrid: tabs + run overlay | Tabs for files/diffs, RunProgress overlays during runs | |
| You decide | Claude picks | |

**User's choice:** Tab-driven always
**Notes:** RunProgress relocates to agent stream (right panel)

---

### Auto-Open Diffs

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, auto-open diff tab | Edit proposal auto-opens and focuses diff tab | ✓ |
| Notification only | Badge/notification, user opens manually | |
| You decide | Claude picks | |

**User's choice:** Yes, auto-open diff tab
**Notes:** None

---

## Claude's Discretion

- Tab max count and overflow scrolling behavior
- Shiki theme choice (must match glassmorphic dark aesthetic)
- Welcome tab content/layout
- Exact tab strip styling within design system

## Deferred Ideas

- Unified diff toggle (ADIFF-01 -- future phase)
- In-file search (Ctrl+F)
- Inline approval in agent stream (ADIFF-02 -- future phase)
