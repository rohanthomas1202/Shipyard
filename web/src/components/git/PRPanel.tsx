import { useState } from 'react'
import { api } from '../../lib/api'
import { useProjectContext } from '../../context/ProjectContext'

export function PRPanel() {
  const [loading, setLoading] = useState(false)
  const [pr, setPR] = useState<{ number: number; html_url: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { currentRun } = useProjectContext()

  const createPR = async () => {
    if (!currentRun || loading) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.gitCreatePR(currentRun.id)
      setPR(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create PR')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 rounded-xl" style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)' }}>
      <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>Pull Request</h3>
      {pr ? (
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-success)' }}>check_circle</span>
          <a
            href={pr.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm underline"
            style={{ color: 'var(--color-primary)' }}
          >
            PR #{pr.number}
          </a>
        </div>
      ) : (
        <>
          {error && <p className="text-xs mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>}
          <button
            onClick={createPR}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
          >
            {loading ? 'Creating...' : 'Create PR'}
          </button>
        </>
      )}
    </div>
  )
}
