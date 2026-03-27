# Phase 11: Agent Activity Stream - Research

**Researched:** 2026-03-27
**Domain:** React real-time event stream UI, scroll management, CSS animations
**Confidence:** HIGH

## Summary

Phase 11 transforms the AgentPanel from a simple status display into a real-time activity stream. The existing infrastructure is solid: `wsStore.agentEvents[]` already accumulates all WebSocket events, `WebSocketContext` already routes events to the store, and all backend event types (status, stream, plan_ready, edit_applied, exec_result, validation_result, git, run lifecycle) are already flowing through WebSocket. The UI spec (11-UI-SPEC.md) provides a complete rendering contract for every event type.

The core technical challenges are: (1) efficient scroll management with sticky-bottom auto-scroll that disengages on user scroll-up, (2) performant streaming token accumulation via refs (not state), and (3) grouping events by run_id into reviewable sections. All of these are well-understood React patterns using `useRef`, `onScroll` handlers, and `requestAnimationFrame` guards -- no exotic libraries needed.

**Primary recommendation:** Build entirely with existing stack (React 19, Zustand 5, Tailwind CSS 4). No new dependencies. The wsStore already provides all needed data; the work is purely UI component creation and AgentPanel rewrite.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-02: Sticky bottom with smooth transitions. Auto-scroll while user is at bottom (within ~50px threshold). When user scrolls up, show a floating "N new events" badge at the bottom of the panel with a pulse animation. Clicking the badge snaps back to bottom and re-enables auto-scroll.
- D-03: New events animate in with a slide-up transition rather than instant append.
- D-05: Each run gets its own section in the agent panel. Users can switch between runs to review past activity.

### Claude's Discretion
- D-01: Event rendering approach (cards, bubbles, accordion, or hybrid)
- D-04: Stream density per event type (which events show inline vs collapsed)
- Run section UI (tabs, stacked sections, or sidebar list)
- Exact animation timing and easing for scroll transitions
- Badge positioning, styling, and pulse animation design
- How to handle very long runs (virtualization if needed)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STREAM-01 | User sees a real-time step timeline of agent activity (planning, reading, editing, validating) | wsStore.agentEvents[] already accumulates all WS events; EventCard renders each type per UI spec contract; StepTimeline already wired to planSteps |
| STREAM-02 | Stream auto-scrolls when user is at bottom, shows "N new events" badge when scrolled up | useRef-based scroll tracking with onScroll handler, 50px threshold, NewEventBadge floating component |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- React 19.2.4 with custom glassmorphic design system (no component library)
- Tailwind CSS 4.2.2 with `@theme` custom properties in glass.css
- Zustand 5.0.12 for state management with fine-grained selectors
- Material Symbols for icons (Google Fonts CDN, already loaded)
- CSS custom properties: `var(--color-*)`, `var(--font-code)`, `var(--radius-element)` etc.
- 2-space indentation for TypeScript/React
- PascalCase.tsx for component files, camelCase.ts for non-component modules
- Named exports for React components: `export function ComponentName()`
- No new dependencies unless justified -- this phase needs none

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.4 | Component framework | Already in use |
| zustand | 5.0.12 | State management (wsStore) | Already provides agentEvents[], activeNode, planSteps |
| tailwindcss | 4.2.2 | Styling with CSS custom properties | Already in use with glass.css theme |

### Supporting (Already Installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @playwright/test | 1.58.2 | E2E testing | Validation of stream behavior |

### No New Dependencies Needed
This phase is purely UI work on top of existing infrastructure. The wsStore already provides all data; WebSocketContext already routes events. No virtualization library needed for v1 (runs are bounded by agent execution time, typically <100 events per run).

## Architecture Patterns

### Recommended Component Structure
```
web/src/components/agent/
  AgentPanel.tsx          # Evolve: panel shell, delegates to ActivityStream
  ActivityStream.tsx      # New: scrollable event list with auto-scroll
  EventCard.tsx           # New: renders single event by type
  EventTypeBadge.tsx      # New: colored pill for event type
  RunSection.tsx          # New: groups events by run_id
  NewEventBadge.tsx       # New: floating unread count pill
  StreamingBlock.tsx      # New: evolves StreamingText for inline streaming
  StepTimeline.tsx        # Keep: horizontal plan step dots
  AutonomyToggle.tsx      # Keep: mode toggle
  ChatBubble.tsx          # Keep file but unused in stream (no deletion)
  ActionBlock.tsx         # Keep file but unused in stream (no deletion)
  StreamingText.tsx       # Keep file but superseded by StreamingBlock
  TypingIndicator.tsx     # Keep file but unused in stream
```

### Pattern 1: Sticky-Bottom Auto-Scroll
**What:** Track scroll position to auto-scroll on new events, disengage when user scrolls up.
**When to use:** Any container showing a live feed of appended items.
**Example:**
```typescript
// Scroll tracking with useRef + onScroll + RAF guard
function ActivityStream({ events }: { events: WSEvent[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const rafRef = useRef(0)

  const handleScroll = () => {
    cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      const el = containerRef.current
      if (!el) return
      isAtBottomRef.current =
        el.scrollHeight - el.scrollTop - el.clientHeight <= 50
    })
  }

  useEffect(() => {
    if (isAtBottomRef.current && containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [events.length])

  return (
    <div ref={containerRef} onScroll={handleScroll}
      role="log" aria-live="polite"
      className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
      {/* event cards */}
    </div>
  )
}
```

### Pattern 2: Ref-Based Token Streaming
**What:** Append streaming tokens via DOM ref to avoid re-renders per token.
**When to use:** High-frequency text updates from LLM streaming.
**Example:**
```typescript
// StreamingBlock accumulates tokens without triggering React re-renders
function StreamingBlock() {
  const textRef = useRef<HTMLSpanElement>(null)
  const agentEvents = useWsStore((s) => s.agentEvents)
  const lastProcessed = useRef(0)

  useEffect(() => {
    if (!textRef.current) return
    const newEvents = agentEvents.slice(lastProcessed.current)
    for (const event of newEvents) {
      if (event.type === 'stream' && event.data.token) {
        textRef.current.textContent += event.data.token as string
      }
    }
    lastProcessed.current = agentEvents.length
  }, [agentEvents])

  return <span ref={textRef} />
}
```
This is the exact pattern already used in `StreamingText.tsx`.

### Pattern 3: Event Grouping by Run
**What:** Group agentEvents by run_id to create run sections.
**When to use:** Multi-run history display.
**Example:**
```typescript
// Derive run groups from flat event array
const runGroups = useMemo(() => {
  const groups: Map<string, WSEvent[]> = new Map()
  for (const event of events) {
    const runId = event.run_id
    if (!groups.has(runId)) groups.set(runId, [])
    groups.get(runId)!.push(event)
  }
  return groups
}, [events])
```

### Pattern 4: Expandable Detail with max-height Animation
**What:** CSS-only expand/collapse for event details.
**When to use:** Event cards with optional verbose content (plan steps, stdout, error details).
**Example:**
```typescript
const [expanded, setExpanded] = useState(false)
// In JSX:
<div style={{
  maxHeight: expanded ? '300px' : '0px',
  overflow: 'hidden',
  transition: expanded
    ? 'max-height 200ms ease-out'
    : 'max-height 150ms ease-in',
}}>
  {/* detail content */}
</div>
```

### Anti-Patterns to Avoid
- **Re-rendering per stream token:** Never store individual tokens in React state. Use refs to mutate DOM directly, same as existing StreamingText pattern.
- **Spreading all agentEvents into individual selectors:** Use a single `useWsStore((s) => s.agentEvents)` selector. The array reference changes on each append, which is the intended re-render trigger for the stream container.
- **Scroll-to-bottom on every render:** Only scroll when `isAtBottomRef.current` is true AND events.length changed. Otherwise user cannot scroll up to review.
- **Inline style objects created on every render:** Extract static style objects to module-level constants to avoid GC pressure.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative timestamps | Custom date math | Simple helper function with `Date.now() - timestamp` | Only need "just now", "Xm ago", "Xh ago" -- trivial, no library needed |
| List virtualization | Custom windowing | Not needed for v1 | Runs produce <100 events typically; premature optimization |
| Scroll position tracking | Complex intersection observer setup | Simple `onScroll` + `scrollHeight - scrollTop - clientHeight` check | The 50px threshold approach is simpler and proven in this codebase (Phase 10 diff sync) |

**Key insight:** This phase requires no new abstractions or libraries. The existing wsStore + React refs pattern handles all the hard problems (streaming, scroll, state). The work is component creation and styling per the UI spec.

## Common Pitfalls

### Pitfall 1: Auto-Scroll Fighting User Scroll
**What goes wrong:** User tries to scroll up to review past events, but new events keep pushing them to the bottom.
**Why it happens:** Auto-scroll effect fires on every new event without checking user intent.
**How to avoid:** Use `isAtBottomRef` pattern. Check `scrollHeight - scrollTop - clientHeight <= 50` in onScroll handler. Only auto-scroll when ref is true.
**Warning signs:** User reports they "can't scroll up during a run."

### Pitfall 2: Stream Token Performance
**What goes wrong:** UI becomes sluggish during LLM streaming because every token triggers a React re-render.
**Why it happens:** Storing tokens in state causes re-render of entire event list.
**How to avoid:** Use ref-based text mutation (existing StreamingText pattern). StreamingBlock should NOT store token text in state.
**Warning signs:** React DevTools shows 50+ re-renders per second during streaming.

### Pitfall 3: Stale Closure in Scroll Handler
**What goes wrong:** `onScroll` handler captures stale `events.length` from a previous render.
**Why it happens:** Scroll handler is a closure over render-time values.
**How to avoid:** Use refs for mutable values the scroll handler needs (isAtBottom, newEventCount). Don't read React state inside the scroll handler.
**Warning signs:** Badge count is wrong or scroll behavior is inconsistent.

### Pitfall 4: Missing Run Context for Events
**What goes wrong:** Events rendered without knowing which instruction they belong to, making run sections meaningless.
**Why it happens:** `WSEvent` has `run_id` but not the instruction text. Need to look up instruction from currentRun or a run map.
**How to avoid:** Store instruction per run_id when `run_started` or `status` events arrive. Or look up from ProjectContext's run data.
**Warning signs:** Run section headers show "Run: undefined".

### Pitfall 5: Animation Performance on Many Events
**What goes wrong:** Slide-up animation causes jank when many events arrive rapidly.
**Why it happens:** CSS animations on many elements + layout recalculations.
**How to avoid:** Only animate the most recent event card. Skip animation when auto-scroll is disabled (events are off-screen anyway). Use `will-change: transform` sparingly.
**Warning signs:** Frame drops visible during rapid event sequences.

### Pitfall 6: agentEvents Array Growing Unbounded
**What goes wrong:** Memory grows without limit across multiple runs in a single session.
**Why it happens:** `agentEvents` array never gets cleared between runs.
**How to avoid:** Either clear on new run start (losing history) or group by run_id and only keep last N runs. The UI spec says "past runs remain accessible" so clearing is not ideal -- instead, use the run grouping to only render visible runs and consider clearing events for runs older than some threshold.
**Warning signs:** Tab memory usage grows steadily over a long session.

## Code Examples

### Event Type to Rendering Map (from UI Spec)
```typescript
// Source: 11-UI-SPEC.md Event Rendering Contract
interface EventConfig {
  icon: string
  badgeBg: string
  badgeColor: string
  expandable: boolean
}

const EVENT_CONFIG: Record<string, EventConfig> = {
  status:            { icon: 'sync',          badgeBg: 'rgba(99, 102, 241, 0.15)',  badgeColor: '#6366F1', expandable: false },
  stream:            { icon: 'auto_awesome',  badgeBg: 'rgba(99, 102, 241, 0.15)',  badgeColor: '#6366F1', expandable: false },
  plan_ready:        { icon: 'checklist',     badgeBg: 'rgba(99, 102, 241, 0.15)',  badgeColor: '#6366F1', expandable: true },
  edit_applied:      { icon: 'edit_document', badgeBg: 'rgba(16, 185, 129, 0.15)',  badgeColor: '#10B981', expandable: true },
  exec_result:       { icon: 'terminal',      badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: true },
  validation_result: { icon: 'verified',      badgeBg: 'dynamic',                   badgeColor: 'dynamic', expandable: true },
  git:               { icon: 'commit',        badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: false },
  run_completed:     { icon: 'check_circle',  badgeBg: 'rgba(16, 185, 129, 0.15)',  badgeColor: '#10B981', expandable: false },
  run_failed:        { icon: 'error',         badgeBg: 'rgba(239, 68, 68, 0.15)',   badgeColor: '#EF4444', expandable: true },
  run_cancelled:     { icon: 'cancel',        badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: false },
  error:             { icon: 'warning',       badgeBg: 'rgba(239, 68, 68, 0.15)',   badgeColor: '#EF4444', expandable: true },
}
// Fallback for unknown types:
const DEFAULT_CONFIG: EventConfig = {
  icon: 'info', badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: true,
}
```

### Node Label Mapping (from UI Spec)
```typescript
// Source: 11-UI-SPEC.md Copywriting Contract
const NODE_LABELS: Record<string, string> = {
  planning: 'Planning',
  receive: 'Receiving',
  reader: 'Reading files',
  editor: 'Editing',
  validator: 'Validating',
  executor: 'Running command',
  git_ops: 'Git operations',
  merger: 'Merging changes',
  reporter: 'Generating report',
  coordinator: 'Coordinating',
}
```

### CSS Keyframes to Add (from UI Spec)
```css
/* Source: 11-UI-SPEC.md Interaction States */
@keyframes slide-up {
  from { transform: translateY(8px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes badge-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(99, 102, 241, 0); }
}
```

### NewEventBadge Component Pattern
```typescript
// Floating pill at bottom of scroll area
function NewEventBadge({ count, onClick }: { count: number; onClick: () => void }) {
  if (count <= 0) return null
  return (
    <button
      onClick={onClick}
      role="status"
      aria-live="assertive"
      aria-label={`${count} new event${count === 1 ? '' : 's'}, click to scroll to latest`}
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 px-4 py-1.5 rounded-full text-xs font-semibold text-white"
      style={{
        background: 'rgba(99, 102, 241, 0.9)',
        boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
        animation: 'badge-pulse 2s infinite',
      }}
    >
      {count} new event{count === 1 ? '' : 's'}
    </button>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AgentPanel with 3-state view (idle/working/error) | AgentPanel with ActivityStream rendering all events | Phase 11 | Full panel rewrite of body content |
| StreamingText as standalone component | StreamingBlock integrated into event stream | Phase 11 | Streaming tokens appear inline in event flow |
| No run history | Events grouped by run_id in sections | Phase 11 | Users can review past runs |

## Open Questions

1. **Run instruction text availability**
   - What we know: `WSEvent` has `run_id` but not instruction text. `currentRun` from ProjectContext has it for the active run.
   - What's unclear: For past runs, do we need to fetch instruction from API or can we capture it from a `run_started` event?
   - Recommendation: Capture instruction text when `run_started` event arrives (it may include instruction in data). If not, derive from `currentRun` for active run, and consider storing a `runId -> instruction` map in wsStore for multi-run support.

2. **Stream event coalescing into StreamingBlock**
   - What we know: Multiple consecutive `stream` events should be shown in a single StreamingBlock, not individual cards.
   - What's unclear: The exact boundary condition -- when does a new StreamingBlock start?
   - Recommendation: Per UI spec, new StreamingBlock starts when a non-stream event arrives or when the `node` field changes. Implement as a grouping pass over events before rendering.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright 1.58.2 |
| Config file | `web/playwright.config.ts` |
| Quick run command | `cd web && npx playwright test --grep "agent panel"` |
| Full suite command | `cd web && npx playwright test` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STREAM-01 | Real-time step timeline updates live during run | e2e | `cd web && npx playwright test e2e/activity-stream.spec.ts --grep "timeline"` | Wave 0 |
| STREAM-02 | Auto-scroll at bottom, badge when scrolled up | e2e | `cd web && npx playwright test e2e/activity-stream.spec.ts --grep "scroll"` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd web && npm run build` (TypeScript type check + Vite build)
- **Per wave merge:** `cd web && npx playwright test`
- **Phase gate:** Full Playwright suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `web/e2e/activity-stream.spec.ts` -- covers STREAM-01 and STREAM-02
- [ ] Existing `web/e2e/app.spec.ts` test "welcome card is visible in agent panel" will need updating since AgentPanel body changes

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `web/src/stores/wsStore.ts` -- agentEvents[], activeNode, planSteps store shape
- Codebase inspection: `web/src/context/WebSocketContext.tsx` -- event routing to store
- Codebase inspection: `web/src/components/agent/AgentPanel.tsx` -- current panel structure
- Codebase inspection: `web/src/components/agent/StreamingText.tsx` -- ref-based token pattern
- Codebase inspection: `agent/events.py` -- EventBus P0/P1/P2 priority routing, event types
- Phase artifact: `11-UI-SPEC.md` -- complete visual and interaction contract
- Phase artifact: `11-CONTEXT.md` -- user decisions and canonical references

### Secondary (MEDIUM confidence)
- React 19 `scrollTo` with `behavior: 'smooth'` -- standard Web API, widely supported
- `requestAnimationFrame` guard for scroll handlers -- same pattern used in Phase 10 diff sync

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, everything already installed and in use
- Architecture: HIGH -- patterns are standard React (refs, effects, scroll handlers) proven in this codebase
- Pitfalls: HIGH -- all identified from direct codebase analysis and common React patterns

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable -- no external dependencies changing)
