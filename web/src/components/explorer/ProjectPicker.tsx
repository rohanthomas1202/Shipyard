import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'
import type { Project } from '../../types'

interface ProjectPickerProps {
  open: boolean
  onClose: () => void
}

export function ProjectPicker({ open, onClose }: ProjectPickerProps) {
  const { projects, setCurrentProject, refreshProjects } = useProjectContext()
  const [tab, setTab] = useState<'select' | 'create'>('select')
  const [name, setName] = useState('')
  const [path, setPath] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSelect = (project: Project) => {
    setCurrentProject(project)
    onClose()
  }

  const handleCreate = async () => {
    if (!name.trim() || !path.trim()) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createProject(name.trim(), path.trim())
      await refreshProjects()
      setCurrentProject(created)
      setName('')
      setPath('')
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create project')
    } finally {
      setCreating(false)
    }
  }

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-[480px] max-h-[70vh] overflow-hidden rounded-2xl"
        style={{
          background: 'rgba(20, 22, 30, 0.9)',
          backdropFilter: 'blur(32px)',
          border: '1px solid var(--color-border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <h2 className="text-lg font-bold" style={{ color: 'var(--color-text)' }}>
            {tab === 'select' ? 'Select Project' : 'Create Project'}
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg" style={{ color: 'var(--color-muted)' }}>
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex px-6" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <button
            onClick={() => setTab('select')}
            className="px-4 py-3 text-sm font-medium"
            style={{
              color: tab === 'select' ? 'var(--color-text)' : 'var(--color-muted)',
              borderBottom: tab === 'select' ? '2px solid var(--color-primary)' : '2px solid transparent',
            }}
          >
            Existing Projects
          </button>
          <button
            onClick={() => setTab('create')}
            className="px-4 py-3 text-sm font-medium"
            style={{
              color: tab === 'create' ? 'var(--color-text)' : 'var(--color-muted)',
              borderBottom: tab === 'create' ? '2px solid var(--color-primary)' : '2px solid transparent',
            }}
          >
            New Project
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[50vh]">
          {tab === 'select' ? (
            projects.length === 0 ? (
              <div className="text-center py-8">
                <span className="material-symbols-outlined text-4xl mb-3 block" style={{ color: 'var(--color-muted)' }}>
                  folder_off
                </span>
                <p className="text-sm mb-1" style={{ color: 'var(--color-text)' }}>No projects yet</p>
                <p className="text-xs mb-4" style={{ color: 'var(--color-muted)' }}>Create one to get started</p>
                <button
                  onClick={() => setTab('create')}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-white"
                  style={{ background: 'var(--color-primary)' }}
                >
                  Create Project
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => handleSelect(project)}
                    className="w-full flex items-center gap-3 p-3 rounded-xl text-left transition-colors hover:bg-white/5"
                    style={{ border: '1px solid var(--color-border)' }}
                  >
                    <span className="material-symbols-outlined text-[20px]" style={{ color: 'var(--color-primary)' }}>
                      folder
                    </span>
                    <div className="flex-1 overflow-hidden">
                      <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>
                        {project.name}
                      </p>
                      <p className="text-xs truncate" style={{ color: 'var(--color-muted)', fontFamily: 'var(--font-code)' }}>
                        {project.path}
                      </p>
                    </div>
                    <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-muted)' }}>
                      chevron_right
                    </span>
                  </button>
                ))}
              </div>
            )
          ) : (
            <div className="space-y-4">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
                  Project Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-project"
                  className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
                  style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
                  Working Directory
                </label>
                <input
                  type="text"
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  placeholder="/Users/you/code/my-project"
                  className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
                  style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)', fontFamily: 'var(--font-code)' }}
                />
              </div>

              {error && (
                <div className="p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.15)', borderLeft: '3px solid var(--color-error)', color: 'var(--color-text)' }}>
                  {error}
                </div>
              )}

              <button
                onClick={handleCreate}
                disabled={creating || !name.trim() || !path.trim()}
                className="w-full h-10 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50"
                style={{ background: 'var(--color-primary)', boxShadow: '0 0 15px rgba(99,102,241,0.3)' }}
              >
                {creating ? 'Creating...' : 'Create Project'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
