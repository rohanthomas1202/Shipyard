import { useState } from 'react'
import { useProjectContext } from '../../context/ProjectContext'

interface WorkspaceHomeProps {
  onOpenSettings?: () => void
  onOpenProjectPicker?: () => void
}

export function WorkspaceHome({ onOpenSettings, onOpenProjectPicker }: WorkspaceHomeProps) {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { submitInstruction, currentProject } = useProjectContext()

  const handleSubmit = async () => {
    if (!prompt.trim() || loading) return
    setError(null)
    setLoading(true)
    try {
      await submitInstruction(prompt.trim(), currentProject?.path || '/tmp')
      setPrompt('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      <div className="max-w-[600px] w-full flex flex-col items-center">
        {/* Header */}
        <div className="mb-8 text-center">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl border mb-6"
            style={{
              background: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
            }}
          >
            <span
              className="material-symbols-outlined text-3xl"
              style={{ color: 'var(--color-primary)', fontVariationSettings: "'FILL' 1" }}
            >
              auto_awesome
            </span>
          </div>
          <h1
            className="text-3xl font-bold mb-3 tracking-tight"
            style={{ color: 'var(--color-text)' }}
          >
            What are we building today?
          </h1>
          <p style={{ color: 'var(--color-muted)', fontSize: '14px' }}>
            Start by describing your task, or open a file to begin editing.
          </p>
        </div>

        {/* Prompt Input */}
        <div
          className="w-full glass-panel p-2 flex flex-col transition-all relative overflow-hidden group"
          style={{ boxShadow: '0 16px 40px rgba(0, 0, 0, 0.5)' }}
        >
          <div
            className="absolute top-0 left-0 w-full h-px opacity-0 group-focus-within:opacity-100 transition-opacity"
            style={{
              background: 'linear-gradient(to right, transparent, rgba(255,255,255,0.2), transparent)',
            }}
          />
          <textarea
            className="w-full min-h-[80px] bg-transparent border-none text-sm resize-none focus:outline-none focus:ring-0 p-3"
            style={{
              color: 'var(--color-text)',
              fontFamily: 'var(--font-ui)',
            }}
            placeholder="Ask the AI agent... e.g., 'Refactor auth flow' or 'Create a new dashboard component'"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <div
            className="flex items-center justify-between px-2 pb-1 pt-2 mt-1"
            style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
          >
            <div className="flex items-center gap-1">
              <button
                className="p-1.5 rounded transition-colors"
                style={{ color: 'var(--color-muted)' }}
              >
                <span className="material-symbols-outlined text-[18px]">attach_file</span>
              </button>
              <button
                className="p-1.5 rounded transition-colors flex items-center gap-1.5 text-xs font-medium"
                style={{ color: 'var(--color-muted)' }}
              >
                <span className="material-symbols-outlined text-[16px]">psychology</span>
                o3
                <span className="material-symbols-outlined text-[14px]">expand_more</span>
              </button>
            </div>
            <button
              onClick={handleSubmit}
              disabled={loading || !prompt.trim()}
              className="h-8 w-8 flex items-center justify-center rounded-lg text-white transition-colors disabled:opacity-50"
              style={{
                background: 'var(--color-primary)',
                boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)',
              }}
            >
              {loading ? (
                <span className="material-symbols-outlined text-[18px] animate-spin">sync</span>
              ) : (
                <span
                  className="material-symbols-outlined text-[18px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  send
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            className="mt-4 w-full p-3 rounded-lg text-sm"
            style={{
              background: 'rgba(239, 68, 68, 0.15)',
              borderLeft: '3px solid var(--color-error)',
              color: 'var(--color-text)',
            }}
          >
            {error}
          </div>
        )}

        {/* Quick Actions */}
        <div className="mt-8 flex gap-3 flex-wrap justify-center">
          <button
            onClick={onOpenProjectPicker}
            className="px-4 py-2 rounded-full glass-panel text-xs font-medium transition-all flex items-center gap-2 hover:opacity-80"
            style={{ color: 'var(--color-muted)' }}
          >
            <span className="material-symbols-outlined text-[14px]">add_box</span>
            Create new project
          </button>
          <button
            onClick={onOpenSettings}
            className="px-4 py-2 rounded-full glass-panel text-xs font-medium transition-all flex items-center gap-2 hover:opacity-80"
            style={{ color: 'var(--color-muted)' }}
          >
            <span className="material-symbols-outlined text-[14px]">settings</span>
            Workspace settings
          </button>
        </div>
      </div>
    </div>
  )
}
