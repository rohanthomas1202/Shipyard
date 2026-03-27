# Phase 11: Agent Activity Stream - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a real-time activity stream in the right panel that shows agent progress step-by-step during a run. Users see live updates as nodes execute (planning, reading, editing, validating). When scrolled up to review past events, auto-scroll stops and a "N new events" badge appears. Each run gets its own section so users can review past runs without losing context.

</domain>

<decisions>
## Implementation Decisions

### Event Rendering
- **D-01:** Claude's Discretion — choose the best rendering approach based on existing components (ActionBlock, ChatBubble, StepTimeline) and the event types now available (status, stream, plan_ready, edit_applied, exec_result, validation_result, git, run_summary).

### Scroll Behavior
- **D-02:** Sticky bottom with smooth transitions. Auto-scroll while user is at bottom (within ~50px threshold). When user scrolls up, show a floating "N new events" badge at the bottom of the panel with a pulse animation. Clicking the badge snaps back to bottom and re-enables auto-scroll.
- **D-03:** New events animate in with a slide-up transition rather than instant append.

### Stream Density
- **D-04:** Claude's Discretion — choose the right level of detail per event type. Balance observability with panel cleanliness. Consider collapsible detail for verbose events like stream tokens.

### Run History
- **D-05:** Each run gets its own section in the agent panel. Users can switch between runs to review past activity. New run appears as a new section, previous runs remain accessible.

### Claude's Discretion
- Event rendering approach (cards, bubbles, accordion, or hybrid)
- Stream density per event type (which events show inline vs collapsed)
- Run section UI (tabs, stacked sections, or sidebar list)
- Exact animation timing and easing for scroll transitions
- Badge positioning, styling, and pulse animation design
- How to handle very long runs (virtualization if needed)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Agent Panel Components
- `web/src/components/agent/AgentPanel.tsx` — Current right panel with idle/working/error states, task display, StreamingText, StepTimeline
- `web/src/components/agent/StreamingText.tsx` — Appends stream event tokens to a span via ref
- `web/src/components/agent/StepTimeline.tsx` — Horizontal step dots with done/active/pending
- `web/src/components/agent/ActionBlock.tsx` — Spinner + label + detail card for action display
- `web/src/components/agent/ChatBubble.tsx` — User/agent chat bubbles
- `web/src/components/agent/TypingIndicator.tsx` — Three bouncing dots animation
- `web/src/components/agent/AutonomyToggle.tsx` — Supervised/autonomous mode toggle

### State Management
- `web/src/stores/wsStore.ts` — Has agentEvents[], activeNode, planSteps[], updateStepStatus(), runError, changedFiles
- `web/src/context/WebSocketContext.tsx` — Bridges WS events to Zustand store, handles status/plan_ready/run lifecycle events
- `web/src/context/ProjectContext.tsx` — currentRun, submitInstruction, setCurrentRun

### Backend Event Types (wired this session)
- `agent/node_events.py` — Helper module emitting events from all graph nodes
- `agent/events.py` — EventBus with P0/P1/P2 priority routing, _P0_TYPES includes run lifecycle
- `server/main.py` lines 355-415 — Run lifecycle events (run_started, run_completed, run_failed, run_cancelled)
- `agent/router.py` — call_streaming() emits stream tokens via event_bus

### Layout Integration
- `web/src/components/layout/IDELayout.tsx` lines 197-228 — Right panel mounts AgentPanel
- `web/src/components/layout/PanelHeader.tsx` — Glassmorphic panel header pattern

### Prior Phase Context
- `.planning/phases/08-foundation-layout-state-architecture-topbar/08-CONTEXT.md` — Glassmorphic design, Zustand architecture, panel layout decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ActionBlock`: Spinner + label card — can render node status events
- `ChatBubble`: User/agent bubbles — potential for instruction display
- `StepTimeline`: Horizontal step dots — already wired to planSteps from wsStore
- `StreamingText`: Token-by-token text display via ref — used for planner streaming
- `AutonomyToggle`: Mode toggle — keep in idle state UI
- `useWsStore` selectors: agentEvents, activeNode, planSteps already available

### Established Patterns
- Zustand stores with fine-grained selectors (useWsStore((s) => s.agentEvents))
- Tailwind CSS 4 + inline style objects for glassmorphic effects
- Material Symbols for icons with fontVariationSettings for filled variants
- `var(--color-*)` CSS custom properties, `var(--font-code)` for monospace
- CSS keyframe animations (bounce-dot, blink) defined in index.css

### Integration Points
- AgentPanel is mounted inside IDELayout right panel — full replacement
- wsStore.agentEvents[] accumulates all non-snapshot WS events — primary data source
- wsStore.activeNode tracks which node is currently executing
- wsStore.planSteps[] tracks plan progress from plan_ready events
- WebSocketContext already routes events to store — no new plumbing needed

</code_context>

<specifics>
## Specific Ideas

- Smooth slide-up animation for new events entering the stream
- Floating badge with pulse animation when user has scrolled up and new events arrive
- Each run as a distinct section so past runs are always reviewable
- The event streaming backend was just wired end-to-end this session — all event types are now flowing through WebSocket

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-agent-activity-stream*
*Context gathered: 2026-03-27*
