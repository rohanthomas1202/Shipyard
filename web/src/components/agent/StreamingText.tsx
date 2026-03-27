import { useRef, useEffect } from 'react'
import { useWsStore } from '../../stores/wsStore'

export function StreamingText() {
  const textRef = useRef<HTMLSpanElement>(null)
  const agentEvents = useWsStore((s) => s.agentEvents)
  const lastIndexRef = useRef(0)

  useEffect(() => {
    if (!textRef.current) return
    // Process only new events since last render
    const newEvents = agentEvents.slice(lastIndexRef.current)
    for (const event of newEvents) {
      if (event.type === 'stream' && event.data.token) {
        textRef.current.textContent += event.data.token as string
      }
    }
    lastIndexRef.current = agentEvents.length
  }, [agentEvents])

  return (
    <div
      className="p-4 rounded-2xl text-sm leading-relaxed"
      style={{
        background: 'rgba(99, 102, 241, 0.1)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
      }}
    >
      <span ref={textRef} style={{ color: 'var(--color-text)' }} />
      <span
        className="inline-block w-[2px] h-[14px] ml-0.5 align-middle"
        style={{
          background: 'var(--color-primary)',
          animation: 'blink 1s infinite',
        }}
      />
    </div>
  )
}
