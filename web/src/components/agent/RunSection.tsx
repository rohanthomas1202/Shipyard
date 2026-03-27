import type { WSEvent } from '../../types'
import { EventCard } from './EventCard'
import { StreamingBlock } from './StreamingBlock'
import { useWsStore } from '../../stores/wsStore'

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

interface RunSectionProps {
  runId: string
  instruction: string
  events: WSEvent[]
  isMultiRun?: boolean
}

export function RunSection({ runId, instruction, events, isMultiRun = false }: RunSectionProps) {
  const globalEvents = useWsStore((s) => s.agentEvents)

  // Build rendered items with stream coalescing
  const items: Array<{ key: string; element: React.ReactNode }> = []
  let lastStreamNode: string | null = null

  for (let i = 0; i < events.length; i++) {
    const event = events[i]
    const isLast = i === events.length - 1

    if (event.type === 'stream') {
      // Coalesce consecutive stream events from the same node
      if (lastStreamNode === (event.node ?? '__default__')) {
        continue // StreamingBlock picks up new tokens via useEffect
      }
      lastStreamNode = event.node ?? '__default__'

      // Find this event's index in the global agentEvents array
      const globalIndex = globalEvents.findIndex(
        (e) => e.run_id === event.run_id && e.seq === event.seq
      )

      items.push({
        key: `stream-${event.seq}`,
        element: <StreamingBlock startIndex={globalIndex >= 0 ? globalIndex : 0} />,
      })
    } else {
      lastStreamNode = null
      items.push({
        key: `event-${event.seq}`,
        element: <EventCard event={event} animate={isLast} />,
      })
    }
  }

  const truncatedInstruction = instruction.length > 60
    ? instruction.slice(0, 60) + '...'
    : instruction

  return (
    <div data-run-id={runId}>
      {/* Run section header (only in multi-run mode) */}
      {isMultiRun && (
        <div
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 5,
            padding: '8px 16px',
            borderBottom: '1px solid var(--color-border)',
            background: 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--color-muted)',
            }}
            title={`Run: ${instruction}`}
          >
            Run: {truncatedInstruction}
          </span>
          {events.length > 0 && (
            <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
              {relativeTime(events[0].timestamp)}
            </span>
          )}
        </div>
      )}

      {/* Event list */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: isMultiRun ? '8px 0' : 0,
        }}
      >
        {items.map(({ key, element }) => (
          <div key={key}>{element}</div>
        ))}
      </div>
    </div>
  )
}
