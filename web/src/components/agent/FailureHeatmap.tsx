import { useMemo } from 'react'
import { useWsStore } from '../../stores/wsStore'

const ERROR_CATEGORIES = ['syntax', 'test', 'contract', 'structural'] as const

function cellBg(count: number): string {
  if (count === 0) return 'transparent'
  if (count <= 2) return 'rgba(245, 158, 11, 0.15)'
  return 'rgba(239, 68, 68, 0.25)'
}

export function FailureHeatmap() {
  const traces = useWsStore((s) => s.decisionTraces)

  const heatmap = useMemo(() => {
    const map: Record<string, Record<string, number>> = {}
    for (const t of traces) {
      const mod = t.moduleName ?? 'unknown'
      if (!map[mod]) map[mod] = {}
      map[mod][t.errorCategory] = (map[mod][t.errorCategory] ?? 0) + 1
    }
    return map
  }, [traces])

  const modules = Object.keys(heatmap).sort()

  if (modules.length === 0) {
    return (
      <div className="glass-panel p-4 rounded-lg text-center">
        <div className="text-xs" style={{ color: 'var(--color-muted)' }}>
          No failure data
        </div>
        <div className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
          Failure patterns will appear here after tasks execute.
        </div>
      </div>
    )
  }

  return (
    <div className="glass-panel p-4 rounded-lg overflow-x-auto">
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            <th
              className="text-left px-2 py-1"
              style={{ color: 'var(--color-muted)', fontSize: 12, fontWeight: 600, textTransform: 'uppercase' }}
            >
              Module
            </th>
            {ERROR_CATEGORIES.map((cat) => (
              <th
                key={cat}
                className="text-center px-2 py-1"
                scope="col"
                style={{ color: 'var(--color-muted)', fontSize: 12, fontWeight: 600, textTransform: 'uppercase' }}
              >
                {cat}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {modules.map((mod) => (
            <tr key={mod} style={{ borderTop: '1px solid var(--color-border)' }}>
              <th
                scope="row"
                className="text-left px-2 py-1 truncate"
                style={{ color: 'var(--color-text)', fontSize: 14, fontWeight: 400, maxWidth: 200 }}
              >
                {mod}
              </th>
              {ERROR_CATEGORIES.map((cat) => {
                const count = heatmap[mod]?.[cat] ?? 0
                return (
                  <td
                    key={cat}
                    className="text-center px-2 py-1"
                    style={{
                      minWidth: 32,
                      minHeight: 32,
                      fontSize: 12,
                      fontWeight: 400,
                      color: 'var(--color-text)',
                      background: cellBg(count),
                      borderLeft: '1px solid var(--color-border)',
                    }}
                    title={`${mod}: ${count} failures (${cat})`}
                  >
                    {count}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
