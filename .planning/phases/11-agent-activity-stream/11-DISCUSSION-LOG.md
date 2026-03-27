# Phase 11: Agent Activity Stream - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 11-agent-activity-stream
**Areas discussed:** Event rendering, Scroll behavior, Stream density, Run history

---

## Event Rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Node cards | Each node gets a card showing status, expanding with details | |
| Chat-style log | Linear feed of chat-bubble-like entries, one per event | |
| Collapsible step accordion | One collapsible section per plan step with sub-events | |
| You decide | Claude picks the best approach based on existing components | ✓ |

**User's choice:** Claude's discretion
**Notes:** User deferred to Claude given the variety of existing components (ActionBlock, ChatBubble, StepTimeline) and the multiple event types now available.

---

## Scroll Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Sticky bottom | Auto-scroll at bottom, floating "N new events" badge, click to snap back | |
| Sticky bottom + smooth | Same + slide-up animation for new events, pulse animation on badge | ✓ |
| Manual only | No auto-scroll, always show badge, user clicks to jump | |

**User's choice:** Sticky bottom + smooth
**Notes:** Matches the success criteria requirement for auto-scroll and "N new events" badge. Smooth transitions add polish.

---

## Stream Density

| Option | Description | Selected |
|--------|-------------|----------|
| Compact by default | One line per plan step, expandable for sub-events | |
| Medium detail | Node transition cards with key details inline | |
| Verbose log | Every event gets a line, terminal-like | |
| You decide | Claude picks the right density balance | ✓ |

**User's choice:** Claude's discretion
**Notes:** User deferred density decisions to Claude.

---

## Run History

| Option | Description | Selected |
|--------|-------------|----------|
| Clear on new run | Stream resets, past runs via REST API only | |
| Collapsible past runs | Previous run collapses to summary line, new run below | |
| Separate sections | Each run gets its own section/tab, switchable | ✓ |

**User's choice:** Separate sections per run
**Notes:** Users can switch between runs to review past activity without losing context.

---

## Claude's Discretion

- Event rendering approach (cards, bubbles, accordion, or hybrid)
- Stream density per event type
- Run section UI implementation (tabs vs stacked vs sidebar)
- Animation timing and easing
- Badge positioning and styling

## Deferred Ideas

None — discussion stayed within phase scope
