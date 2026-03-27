import { useRef, useEffect } from 'react'
import { useWsStore } from '../../stores/wsStore'
import { EventTypeBadge } from './EventTypeBadge'

interface StreamingBlockProps {
  startIndex: number
}

export function StreamingBlock({ startIndex }: StreamingBlockProps) {
  const textRef = useRef<HTMLSpanElement>(null)
  const lastProcessed = useRef(startIndex)
  const agentEvents = useWsStore((s) => s.agentEvents)

  useEffect(() => {
    if (!textRef.current) return
    for (let i = lastProcessed.current; i < agentEvents.length; i++) {
      const ev = agentEvents[i]
      if (ev.type === 'stream' && ev.data.token) {
        textRef.current.textContent += String(ev.data.token)
      }
    }
    lastProcessed.current = agentEvents.length
  }, [agentEvents])

  return (
    <div
      style={{
        padding: 12,
        borderRadius: 'var(--radius-element)',
        border: '1px solid var(--color-border)',
        background: 'rgba(30, 33, 43, 0.4)',
      }}
    >
      {/* Row 1: Badge + label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <EventTypeBadge type="stream" />
        <span style={{ fontSize: 11, color: 'var(--color-muted)', fontStyle: 'italic' }}>
          Thinking...
        </span>
      </div>

      {/* Row 2: Streaming text */}
      <div style={{ marginTop: 8, fontSize: 14, lineHeight: 1.5 }}>
        <span ref={textRef} style={{ color: 'var(--color-text)' }} />
        <span
          className="inline-block w-[2px] h-[14px] ml-0.5 align-middle"
          style={{
            background: 'var(--color-primary)',
            animation: 'blink 1s infinite',
          }}
        />
      </div>
    </div>
  )
}
