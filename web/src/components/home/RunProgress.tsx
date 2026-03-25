import { useState, useEffect } from 'react'
import { useProjectContext } from '../../context/ProjectContext'
import { useWebSocketContext } from '../../context/WebSocketContext'
import { api } from '../../lib/api'
import type { WSEvent } from '../../types'

export function RunProgress() {
  const { currentRun, setCurrentRun } = useProjectContext()
  const { subscribe } = useWebSocketContext()
  const [statusText, setStatusText] = useState('Starting...')
  const [events, setEvents] = useState<string[]>([])

  // Poll for run completion
  useEffect(() => {
    if (!currentRun || currentRun.status !== 'running') return

    const interval = setInterval(async () => {
      try {
        const status = await api.getStatus(currentRun.id)
        if (status.status !== 'running') {
          setCurrentRun({
            ...currentRun,
            status: status.status as typeof currentRun.status,
          })
        }
      } catch {
        // ignore polling errors
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [currentRun, setCurrentRun])

  // Listen for WebSocket events
  useEffect(() => {
    const unsub = subscribe('*', (event: WSEvent) => {
      if (event.type === 'status') {
        setStatusText(`Step: ${event.node || 'processing'}`)
      }
      setEvents((prev) => [
        ...prev.slice(-20),
        `[${event.type}] ${event.node || ''} ${JSON.stringify(event.data).slice(0, 80)}`,
      ])
    })
    return unsub
  }, [subscribe])

  if (!currentRun) return null

  const isRunning = currentRun.status === 'running'
  const isDone = currentRun.status === 'completed'
  const isFailed = currentRun.status === 'failed' || currentRun.status === 'error'
  const isWaiting = currentRun.status === 'waiting_for_human'

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <div className="max-w-[500px] w-full flex flex-col items-center">
        {/* Status Icon */}
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}
        >
          <span
            className={`material-symbols-outlined text-3xl ${isRunning ? 'animate-spin' : ''}`}
            style={{
              color: isDone ? 'var(--color-success)'
                : isFailed ? 'var(--color-error)'
                : isWaiting ? 'var(--color-warning)'
                : 'var(--color-primary)',
              fontVariationSettings: "'FILL' 1",
            }}
          >
            {isDone ? 'check_circle' : isFailed ? 'error' : isWaiting ? 'pause_circle' : 'sync'}
          </span>
        </div>

        {/* Title */}
        <h2
          className="text-xl font-bold mb-2 tracking-tight text-center"
          style={{ color: 'var(--color-text)' }}
        >
          {isDone ? 'Run Complete' : isFailed ? 'Run Failed' : isWaiting ? 'Waiting for Approval' : 'Agent Working'}
        </h2>

        {/* Instruction */}
        <p className="text-sm mb-4 text-center" style={{ color: 'var(--color-muted)' }}>
          {currentRun.instruction.slice(0, 100)}
          {currentRun.instruction.length > 100 ? '...' : ''}
        </p>

        {/* Status */}
        <div
          className="w-full glass-panel p-4 mb-4"
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="relative flex h-2 w-2">
              <span
                className={`${isRunning ? 'animate-ping' : ''} absolute inline-flex h-full w-full rounded-full opacity-75`}
                style={{
                  background: isDone ? 'var(--color-success)'
                    : isFailed ? 'var(--color-error)'
                    : 'var(--color-primary)',
                }}
              />
              <span
                className="relative inline-flex rounded-full h-2 w-2"
                style={{
                  background: isDone ? 'var(--color-success)'
                    : isFailed ? 'var(--color-error)'
                    : 'var(--color-primary)',
                }}
              />
            </div>
            <span className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
              {statusText}
            </span>
            <span className="text-xs ml-auto" style={{ color: 'var(--color-muted)' }}>
              {currentRun.status}
            </span>
          </div>

          {/* Event log */}
          <div
            className="max-h-[200px] overflow-y-auto rounded-lg p-3 text-[11px] leading-relaxed"
            style={{
              background: 'rgba(0,0,0,0.3)',
              fontFamily: 'var(--font-code)',
              color: 'var(--color-muted)',
            }}
          >
            {events.length === 0 ? (
              <p>Waiting for events...</p>
            ) : (
              events.map((e, i) => <div key={i}>{e}</div>)
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          {(isDone || isFailed) && (
            <button
              onClick={() => setCurrentRun(null)}
              className="px-4 py-2 rounded-lg text-xs font-semibold text-white"
              style={{ background: 'var(--color-primary)' }}
            >
              Back to Home
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
