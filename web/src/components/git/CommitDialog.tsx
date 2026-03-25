import { useState } from 'react'
import { api } from '../../lib/api'
import { useProjectContext } from '../../context/ProjectContext'

interface CommitDialogProps {
  defaultMessage?: string
  onComplete?: () => void
}

export function CommitDialog({ defaultMessage, onComplete }: CommitDialogProps) {
  const [message, setMessage] = useState(defaultMessage || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ sha: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { currentRun } = useProjectContext()

  const handleCommit = async () => {
    if (!currentRun || loading) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.gitCommit(currentRun.id, message || undefined)
      setResult(res)
      // Auto-push
      try {
        await api.gitPush(currentRun.id)
      } catch {
        // push failure is non-fatal
      }
      onComplete?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Commit failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 rounded-xl" style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)' }}>
      <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text)' }}>Commit Changes</h3>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={3}
        className="w-full rounded-lg p-3 text-sm resize-none focus:outline-none mb-3"
        style={{
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
          fontFamily: 'var(--font-code)',
        }}
        placeholder="Commit message..."
      />
      {error && (
        <p className="text-xs mb-2" style={{ color: 'var(--color-error)' }}>{error}</p>
      )}
      {result && (
        <p className="text-xs mb-2" style={{ color: 'var(--color-success)' }}>
          Committed: {result.sha}
        </p>
      )}
      <button
        onClick={handleCommit}
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all disabled:opacity-50"
        style={{ background: 'var(--color-primary)', boxShadow: '0 0 15px rgba(99,102,241,0.3)' }}
      >
        {loading ? (
          <span className="material-symbols-outlined text-[14px] animate-spin">sync</span>
        ) : (
          <span className="material-symbols-outlined text-[14px]">commit</span>
        )}
        {loading ? 'Committing...' : 'Commit & Push'}
      </button>
    </div>
  )
}
