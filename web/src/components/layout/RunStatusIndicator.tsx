import { useWsStore } from '../../stores/wsStore'
import { useProjectContext } from '../../context/ProjectContext'

export function RunStatusIndicator() {
  const snapshot = useWsStore((s) => s.snapshot)
  const { currentRun } = useProjectContext()

  // Determine status from snapshot or currentRun
  const runStatus = snapshot?.status || currentRun?.status || null

  if (!runStatus || runStatus === 'idle') {
    return (
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
          Idle
        </span>
      </div>
    )
  }

  let dotColor: string
  let label: string
  let animate = false

  switch (runStatus) {
    case 'running':
      dotColor = 'var(--color-warning)'
      label = 'Running...'
      animate = true
      break
    case 'completed':
      dotColor = 'var(--color-success)'
      label = 'Completed'
      break
    case 'failed':
    case 'error':
      dotColor = 'var(--color-error)'
      label = 'Failed'
      break
    case 'waiting_for_human':
      dotColor = 'var(--color-primary)'
      label = 'Waiting for review'
      animate = true
      break
    default:
      dotColor = 'var(--color-muted)'
      label = runStatus
  }

  return (
    <div className="flex items-center gap-2 flex-shrink-0">
      <div className="relative flex h-2 w-2">
        {animate && (
          <span
            className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
            style={{ background: dotColor }}
          />
        )}
        <span
          className="relative inline-flex rounded-full h-2 w-2"
          style={{ background: dotColor }}
        />
      </div>
      <span className="text-xs" style={{ color: dotColor }}>
        {label}
      </span>
    </div>
  )
}
