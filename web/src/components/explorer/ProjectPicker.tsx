import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'
import type { Project } from '../../types'

interface FolderEntry {
  name: string
  path: string
  is_dir: boolean
  has_children: boolean
}

function FolderBrowser({
  onSelect,
  onCancel,
}: {
  onSelect: (path: string) => void
  onCancel: () => void
}) {
  const [currentPath, setCurrentPath] = useState('')
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [entries, setEntries] = useState<FolderEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadDirectory = async (path?: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.browse(path)
      setCurrentPath(result.current)
      setParentPath(result.parent)
      setEntries(result.entries)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to browse')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDirectory()
  }, [])

  return (
    <div className="space-y-3">
      {/* Current path display */}
      <div className="flex items-center gap-2">
        {parentPath && (
          <button
            onClick={() => loadDirectory(parentPath)}
            className="p-1.5 rounded-lg transition-colors hover:bg-white/10"
            style={{ color: 'var(--color-muted)' }}
            title="Go up"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_upward</span>
          </button>
        )}
        <div
          className="flex-1 h-8 px-3 flex items-center rounded-lg text-xs truncate"
          style={{
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            fontFamily: 'var(--font-code)',
          }}
        >
          {currentPath}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-2 rounded-lg text-xs" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--color-error)' }}>
          {error}
        </div>
      )}

      {/* Directory listing */}
      <div
        className="rounded-xl overflow-y-auto"
        style={{
          maxHeight: '240px',
          border: '1px solid var(--color-border)',
          background: 'rgba(0,0,0,0.2)',
        }}
      >
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <span className="material-symbols-outlined animate-spin text-[20px]" style={{ color: 'var(--color-muted)' }}>
              progress_activity
            </span>
          </div>
        ) : entries.length === 0 ? (
          <div className="py-6 text-center text-xs" style={{ color: 'var(--color-muted)' }}>
            No subdirectories
          </div>
        ) : (
          entries.map((entry) => (
            <button
              key={entry.path}
              onClick={() => loadDirectory(entry.path)}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-white/5"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
            >
              <span className="material-symbols-outlined text-[18px]" style={{ color: 'var(--color-primary)' }}>
                {entry.has_children ? 'folder' : 'folder_open'}
              </span>
              <span className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                {entry.name}
              </span>
              {entry.has_children && (
                <span className="material-symbols-outlined text-[14px] ml-auto" style={{ color: 'var(--color-muted)' }}>
                  chevron_right
                </span>
              )}
            </button>
          ))
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={onCancel}
          className="flex-1 h-9 rounded-lg text-sm font-medium transition-colors hover:bg-white/5"
          style={{ border: '1px solid var(--color-border)', color: 'var(--color-muted)' }}
        >
          Cancel
        </button>
        <button
          onClick={() => onSelect(currentPath)}
          className="flex-1 h-9 rounded-lg text-sm font-semibold text-white transition-all"
          style={{ background: 'var(--color-primary)', boxShadow: '0 0 12px rgba(99,102,241,0.25)' }}
        >
          Select This Folder
        </button>
      </div>
    </div>
  )
}

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
  const [browsing, setBrowsing] = useState(false)

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
        className="w-[520px] max-h-[80vh] overflow-hidden rounded-2xl"
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
            {browsing ? 'Select Folder' : tab === 'select' ? 'Select Project' : 'Create Project'}
          </h2>
          <button onClick={onClose} className="p-1 rounded-lg" style={{ color: 'var(--color-muted)' }}>
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Tabs — hidden when browsing */}
        {!browsing && (
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
        )}

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {browsing ? (
            <FolderBrowser
              onSelect={(selectedPath) => {
                setPath(selectedPath)
                setBrowsing(false)
                // Auto-fill name from folder name if empty
                if (!name.trim()) {
                  const folderName = selectedPath.split('/').pop() || ''
                  setName(folderName)
                }
              }}
              onCancel={() => setBrowsing(false)}
            />
          ) : tab === 'select' ? (
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
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={path}
                    onChange={(e) => setPath(e.target.value)}
                    placeholder="/Users/you/code/my-project"
                    className="flex-1 h-10 px-3 rounded-lg text-sm focus:outline-none"
                    style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)', fontFamily: 'var(--font-code)' }}
                  />
                  <button
                    onClick={() => setBrowsing(true)}
                    className="h-10 px-3 rounded-lg text-sm font-medium flex items-center gap-1.5 transition-colors hover:bg-white/10"
                    style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                    title="Browse folders"
                  >
                    <span className="material-symbols-outlined text-[18px]">folder_open</span>
                    Browse
                  </button>
                </div>
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
