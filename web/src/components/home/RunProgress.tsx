import { useState, useEffect } from 'react'
import { useProjectContext } from '../../context/ProjectContext'
import { useWebSocketContext } from '../../context/WebSocketContext'
import { api } from '../../lib/api'
import type { WSEvent, Edit } from '../../types'

export function RunProgress() {
  const { currentRun, setCurrentRun } = useProjectContext()
  const { subscribe } = useWebSocketContext()
  const [statusText, setStatusText] = useState('Starting...')
  const [events, setEvents] = useState<string[]>([])
  const [appliedEdits, setAppliedEdits] = useState<Edit[]>([])
  const [expandedEdit, setExpandedEdit] = useState<string | null>(null)

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

  // Fetch applied edits when run completes
  useEffect(() => {
    if (!currentRun) return
    if (currentRun.status === 'completed' || currentRun.status === 'failed') {
      api.getEdits(currentRun.id).then((edits) => {
        setAppliedEdits(edits.filter(e => e.status === 'applied' || e.status === 'committed'))
      }).catch(() => {})
    }
  }, [currentRun?.status, currentRun?.id])

  if (!currentRun) return null

  const isRunning = currentRun.status === 'running'
  const isDone = currentRun.status === 'completed'
  const isFailed = currentRun.status === 'failed' || currentRun.status === 'error'
  const isWaiting = currentRun.status === 'waiting_for_human'

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <div className="max-w-[600px] w-full flex flex-col items-center">
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

        {/* Applied edits diff summary */}
        {isDone && appliedEdits.length > 0 && (
          <div className="w-full mb-4 space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-success)' }}>
                edit_note
              </span>
              <span className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                {appliedEdits.length} edit{appliedEdits.length !== 1 ? 's' : ''} applied
              </span>
            </div>
            {appliedEdits.map((edit) => {
              const fileName = edit.file_path.split('/').pop() || edit.file_path
              const isExpanded = expandedEdit === edit.id
              return (
                <div
                  key={edit.id}
                  className="rounded-lg overflow-hidden"
                  style={{ border: '1px solid var(--color-border)', background: 'rgba(0,0,0,0.3)' }}
                >
                  <button
                    onClick={() => setExpandedEdit(isExpanded ? null : edit.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
                  >
                    <span className="material-symbols-outlined text-[14px]" style={{ color: 'var(--color-primary)' }}>
                      {isExpanded ? 'expand_more' : 'chevron_right'}
                    </span>
                    <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-code)' }}>
                      {fileName}
                    </span>
                    <span className="text-[10px] ml-auto px-2 py-0.5 rounded-full" style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--color-success)' }}>
                      {edit.status}
                    </span>
                  </button>
                  {isExpanded && (
                    <div
                      className="px-3 pb-3 overflow-x-auto"
                      style={{ fontFamily: 'var(--font-code)', fontSize: '11px', lineHeight: '1.6' }}
                    >
                      {edit.old_content && (
                        <div className="mb-1">
                          {edit.old_content.split('\n').map((line, i) => (
                            <div key={`old-${i}`} className="px-2 rounded" style={{ background: 'rgba(239,68,68,0.1)', color: 'rgba(239,68,68,0.8)' }}>
                              <span style={{ color: 'rgba(239,68,68,0.4)', userSelect: 'none' }}>- </span>{line}
                            </div>
                          ))}
                        </div>
                      )}
                      {edit.new_content && (
                        <div>
                          {edit.new_content.split('\n').map((line, i) => (
                            <div key={`new-${i}`} className="px-2 rounded" style={{ background: 'rgba(34,197,94,0.1)', color: 'rgba(34,197,94,0.8)' }}>
                              <span style={{ color: 'rgba(34,197,94,0.4)', userSelect: 'none' }}>+ </span>{line}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {isDone && appliedEdits.length === 0 && (
          <div className="w-full mb-4 text-center">
            <p className="text-xs" style={{ color: 'var(--color-muted)' }}>No file changes were made.</p>
          </div>
        )}

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
