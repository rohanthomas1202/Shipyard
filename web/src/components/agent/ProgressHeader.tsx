import { useState } from 'react'
import { useWsStore } from '../../stores/wsStore'

export function ProgressHeader() {
  const metrics = useWsStore((s) => s.progressMetrics)
  const [collapsed, setCollapsed] = useState(false)

  if (!metrics) return null

  const ciColor = metrics.ciPassRate >= 80 ? 'var(--color-success)'
    : metrics.ciPassRate >= 50 ? 'var(--color-warning)'
    : 'var(--color-error)'

  return (
    <div
      role="region"
      aria-label="DAG progress metrics"
      aria-expanded={!collapsed}
      className="px-4 py-2 cursor-pointer select-none"
      style={{ borderBottom: '1px solid var(--color-border)' }}
      onClick={() => setCollapsed(!collapsed)}
    >
      {/* Row 1: Progress bar + completion fraction */}
      <div className="flex items-center gap-3">
        <div
          className="flex-1 h-1.5 rounded-full"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <div
            role="progressbar"
            aria-valuenow={metrics.coveragePct}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-full rounded-full transition-all duration-300 ease-out"
            style={{
              width: `${metrics.coveragePct}%`,
              background: 'var(--color-primary)',
            }}
          />
        </div>
        <span className="text-xs shrink-0" style={{ color: 'var(--color-muted)' }}>
          {metrics.completedTasks}/{metrics.totalTasks}
        </span>
        <span
          className="material-symbols-outlined shrink-0 transition-transform duration-200"
          style={{
            fontSize: 16,
            color: 'var(--color-muted)',
            transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)',
          }}
        >
          expand_more
        </span>
      </div>

      {/* Row 2: Metrics grid (collapsible) */}
      <div
        className="overflow-hidden transition-all duration-200 ease-in-out"
        style={{ maxHeight: collapsed ? 0 : 80 }}
      >
        <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
          <div>
            <div style={{ color: 'var(--color-muted)', fontSize: 12, fontWeight: 400 }}>Coverage</div>
            <div style={{ color: 'var(--color-text)', fontSize: 20, fontWeight: 600 }}>
              {metrics.coveragePct}%
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--color-muted)', fontSize: 12, fontWeight: 400 }}>CI Pass</div>
            <div style={{ color: ciColor, fontSize: 20, fontWeight: 600 }}>
              {metrics.ciPassRate}%
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--color-muted)', fontSize: 12, fontWeight: 400 }}>Failed</div>
            <div style={{
              color: metrics.failedTasks > 0 ? 'var(--color-error)' : 'var(--color-text)',
              fontSize: 20,
              fontWeight: 600,
            }}>
              {metrics.failedTasks}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--color-muted)', fontSize: 12, fontWeight: 400 }}>Running</div>
            <div style={{ color: 'var(--color-text)', fontSize: 20, fontWeight: 600 }}>
              {metrics.runningTasks}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
