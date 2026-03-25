import { useRef, useEffect } from 'react'
import { useWebSocketContext } from '../../context/WebSocketContext'

export function StreamingText() {
  const textRef = useRef<HTMLSpanElement>(null)
  const { subscribe } = useWebSocketContext()

  useEffect(() => {
    const unsub = subscribe('stream', (event) => {
      if (textRef.current && event.data.token) {
        textRef.current.textContent += event.data.token
      }
    })
    return unsub
  }, [subscribe])

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
