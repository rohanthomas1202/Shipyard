import { useProjectContext } from '../../context/ProjectContext'
import type { Run } from '../../types'

const STATUS_COLORS: Record<string, string> = {
  completed: 'var(--color-success)',
  running: 'var(--color-primary)',
  waiting_for_human: 'var(--color-warning)',
  failed: 'var(--color-error)',
  error: 'var(--color-error)',
}

export function RunList() {
  const { runs, currentRun, setCurrentRun } = useProjectContext()

  if (runs.length === 0 && !currentRun) return null

  const displayRuns = currentRun ? [currentRun, ...runs.filter(r => r.id !== currentRun.id)] : runs

  return (
    <div className="mt-4 mx-4 pt-4" style={{ borderTop: '1px solid var(--color-border)' }}>
      <h3
        className="text-xs font-bold uppercase tracking-wider mb-3"
        style={{ color: 'var(--color-muted)' }}
      >
        Runs
      </h3>
      <div className="space-y-2">
        {displayRuns.slice(0, 5).map((run: Run) => (
          <button
            key={run.id}
            onClick={() => setCurrentRun(run)}
            className="w-full p-2.5 rounded-lg text-left transition-colors hover:bg-white/5"
            style={{
              background: run.id === currentRun?.id ? 'var(--color-surface)' : 'transparent',
              border: '1px solid var(--color-border)',
            }}
          >
            <div className="flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: STATUS_COLORS[run.status] || 'var(--color-muted)' }}
              />
              <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text)' }}>
                Run #{run.id.slice(0, 6)}
              </span>
              <span className="text-[10px] ml-auto" style={{ color: 'var(--color-muted)' }}>
                {run.status}
              </span>
            </div>
            <p className="text-[10px] mt-1 truncate" style={{ color: 'var(--color-muted)' }}>
              {run.instruction.slice(0, 50)}
            </p>
          </button>
        ))}
      </div>
    </div>
  )
}
