# Phase 8: Foundation — Layout, State Architecture, TopBar - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 08-foundation-layout-state-architecture-topbar
**Areas discussed:** Visual style, Panel behavior, Top bar design, State migration

---

## Visual Style

| Option | Description | Selected |
|--------|-------------|----------|
| Full VS Code dark | Solid dark backgrounds (#1e1e2e), no transparency | |
| Dark with glass accents | Solid dark panels, subtle glass on top bar/headers | |
| Keep glassmorphic | Keep existing frosted glass style, restructure into IDE panels | ✓ |

**User's choice:** Keep glassmorphic
**Notes:** User wants to maintain Shipyard's visual identity

| Option | Description | Selected |
|--------|-------------|----------|
| Solid for code | Code viewer/diff get solid dark background for readability | |
| All glassmorphic | Frosted everywhere including code areas, higher contrast text | ✓ |

**User's choice:** All glassmorphic
**Notes:** Consistent visual treatment throughout

---

## Panel Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Header buttons | Click toggle button in panel header | |
| Double-click divider | Double-click resize handle to toggle collapse | |
| Both | Header buttons AND double-click divider | ✓ |

**User's choice:** Both — more discoverable

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, enforce minimums | File explorer 150px, editor 300px, stream 200px | |
| No minimums | Free resize, collapse if too small | |
| You decide | Claude picks reasonable defaults | ✓ |

**User's choice:** Claude's discretion on minimum sizes

---

## Top Bar Design

| Option | Description | Selected |
|--------|-------------|----------|
| Command palette | VS Code-style single-line, expands on focus | |
| Always-visible bar | Full-width text input always showing | |
| Compact + expand | Small input, expands to multi-line on click | ✓ |

**User's choice:** Compact + expand — saves space by default

| Option | Description | Selected |
|--------|-------------|----------|
| Input + project + status | Instruction (center), project (left), status (right) | |
| Input + project + status + settings | Add settings gear icon | |
| You decide | Claude picks clean layout | ✓ |

**User's choice:** Claude's discretion on top bar layout

---

## State Migration

| Option | Description | Selected |
|--------|-------------|----------|
| WebSocket state only | WS events/snapshot/file statuses to Zustand. ProjectContext stays. | |
| WS + workspace state | Zustand for WS AND workspace state (tabs, files). ProjectContext stays. | ✓ |
| Full migration | Everything to Zustand, no React Context | |

**User's choice:** WS + workspace state to Zustand. ProjectContext remains as React Context.

---

## Claude's Discretion

- Panel minimum sizes
- Top bar layout arrangement
- Zustand store shape and slice boundaries
- Collapse/expand animations
- Resize handle styling

## Deferred Ideas

None — discussion stayed within phase scope
