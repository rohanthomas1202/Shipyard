---
phase: 11-agent-activity-stream
plan: 01
subsystem: ui
tags: [react, zustand, css-animations, event-rendering, glassmorphic]

# Dependency graph
requires:
  - phase: 08-foundation-layout-state-architecture-topbar
    provides: glassmorphic design system, panel layout, CSS custom properties
provides:
  - EventTypeBadge component with 11 event type mappings
  - EventCard component with type-specific rendering and expandable detail
  - StreamingBlock component with ref-based token accumulation
  - RunSection component with stream coalescing
  - NewEventBadge floating pill with pulse animation
  - CSS slide-up and badge-pulse keyframe animations
affects: [11-agent-activity-stream plan 02, agent-panel-rewrite]

# Tech tracking
tech-stack:
  added: [zustand ^5.0.12]
  patterns: [ref-based DOM mutation for streaming, event type config record, stream coalescing]

key-files:
  created:
    - web/src/components/agent/EventTypeBadge.tsx
    - web/src/components/agent/EventCard.tsx
    - web/src/components/agent/StreamingBlock.tsx
    - web/src/components/agent/RunSection.tsx
    - web/src/components/agent/NewEventBadge.tsx
    - web/e2e/activity-stream.spec.ts
    - web/src/stores/wsStore.ts
  modified:
    - web/src/styles/glass.css
    - web/package.json

key-decisions:
  - "Added wsStore.ts and zustand dependency as blocking prerequisite for StreamingBlock"
  - "EVENT_CONFIG exported as module-level constant for cross-component access"
  - "Stream coalescing skips consecutive stream events from same node"

patterns-established:
  - "EVENT_CONFIG record pattern: centralized event type to icon/color/expandable mapping"
  - "Ref-based streaming: useRef + textContent append avoids per-token React re-renders"
  - "Expandable detail: max-height transition with aria-expanded for accessibility"

requirements-completed: [STREAM-01]

# Metrics
duration: 4min
completed: 2026-03-27
---

# Phase 11 Plan 01: Event Rendering Primitives Summary

**Event rendering components (EventTypeBadge, EventCard, StreamingBlock, RunSection, NewEventBadge) with 11-type mapping, ref-based streaming, and CSS animations**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T20:36:44Z
- **Completed:** 2026-03-27T20:41:29Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Built all five event rendering primitives with full TypeScript typing and correct exports
- EventCard handles all 11 event types from UI-SPEC with type-specific body content and expandable detail
- StreamingBlock uses ref-based DOM mutation matching existing StreamingText pattern
- RunSection coalesces consecutive stream events into single StreamingBlock instances
- CSS animations (slide-up, badge-pulse) wrapped in prefers-reduced-motion media query
- E2e test scaffold created for Plan 02 integration

## Task Commits

Each task was committed atomically:

1. **Task 0: Create Wave 0 e2e test scaffold** - `23f2d71` (test)
2. **Task 1: CSS keyframes + EventTypeBadge + EventCard + StreamingBlock** - `e8e0a96` (feat)
3. **Task 2: RunSection and NewEventBadge** - `f399bbe` (feat)

## Files Created/Modified
- `web/e2e/activity-stream.spec.ts` - Skeleton Playwright tests for timeline and scroll badge
- `web/src/styles/glass.css` - Added slide-up and badge-pulse keyframe animations
- `web/src/components/agent/EventTypeBadge.tsx` - Colored pill badge with Material Symbols icon for event types
- `web/src/components/agent/EventCard.tsx` - Single event renderer with type-specific layout and expandable detail
- `web/src/components/agent/StreamingBlock.tsx` - Ref-based streaming token accumulation block
- `web/src/components/agent/RunSection.tsx` - Groups events by run_id with sticky header and stream coalescing
- `web/src/components/agent/NewEventBadge.tsx` - Floating pill badge with pulse animation and accessibility
- `web/src/stores/wsStore.ts` - Zustand store for WebSocket state (blocking dependency)
- `web/package.json` - Added zustand dependency

## Decisions Made
- Added wsStore.ts (Zustand store) and zustand package dependency because StreamingBlock requires useWsStore selector -- the store existed in main working directory from another agent but was not tracked in git
- EVENT_CONFIG exported as a module-level constant so EventCard can check expandable property
- RunSection uses data-run-id attribute on container div for debugging/testing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added wsStore.ts and zustand dependency**
- **Found during:** Task 1 (StreamingBlock implementation)
- **Issue:** StreamingBlock imports useWsStore from stores/wsStore.ts, but neither the store file nor the zustand package existed in this worktree's git-tracked files
- **Fix:** Created web/src/stores/wsStore.ts (matching the main repo version) and added zustand ^5.0.12 to package.json dependencies
- **Files modified:** web/src/stores/wsStore.ts (created), web/package.json, web/package-lock.json
- **Verification:** npm run build passes with zero TypeScript errors
- **Committed in:** e8e0a96 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential dependency for StreamingBlock to compile. No scope creep.

## Issues Encountered
- TypeScript strict mode flagged unused `runId` parameter in RunSection -- resolved by using it as data-run-id attribute on container div

## Known Stubs
None -- all components are fully implemented with real data paths from wsStore.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All event rendering primitives ready for Plan 02 to assemble into full ActivityStream
- Plan 02 will rewrite AgentPanel to use RunSection, wire auto-scroll logic, and mount NewEventBadge
- E2e tests will go green after Plan 02 completes AgentPanel rewrite

---
*Phase: 11-agent-activity-stream*
*Completed: 2026-03-27*
