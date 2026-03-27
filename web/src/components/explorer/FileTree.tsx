import { useState, useEffect } from 'react'
import { ProjectPicker } from './ProjectPicker'
import { TreeNode } from './TreeNode'
import { useProjectContext } from '../../context/ProjectContext'
import { useWsStore } from '../../stores/wsStore'
import { api } from '../../lib/api'
import type { FileEntry } from '../../types'

interface FileTreeProps {
  onCollapse?: () => void
}

export function FileTree({ onCollapse }: FileTreeProps) {
  const { currentProject } = useProjectContext()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [rootEntries, setRootEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load root entries when project changes
  useEffect(() => {
    if (!currentProject) return

    // Clear changed files on project change
    useWsStore.getState().clearChangedFiles()

    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await api.browseProject(currentProject.id)
        if (!cancelled) setRootEntries(res.entries)
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load files')
          setRootEntries([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [currentProject])

  // Derive displayed entries — empty when no project selected
  const displayEntries = currentProject ? rootEntries : []

  return (
    <>
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between shrink-0"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <h2
          className="text-xs font-bold tracking-wider uppercase"
          style={{ color: 'var(--color-muted)' }}
        >
          Explorer
        </h2>
        <div className="flex gap-1">
          <button
            onClick={() => setPickerOpen(true)}
            className="p-1 rounded transition-colors hover:bg-white/5"
            style={{ color: 'var(--color-muted)' }}
            title="Open project"
          >
            <span className="material-symbols-outlined text-[16px]">create_new_folder</span>
          </button>
          {onCollapse && (
            <button
              onClick={onCollapse}
              className="p-1 rounded transition-colors hover:bg-white/5"
              style={{ color: 'var(--color-muted)' }}
              title="Collapse"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_left</span>
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {!currentProject ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center h-full p-4">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
              }}
            >
              <span className="material-symbols-outlined text-2xl" style={{ color: 'var(--color-muted)' }}>
                folder_open
              </span>
            </div>
            <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text)' }}>
              No project selected
            </p>
            <p
              className="text-xs leading-relaxed text-center max-w-[180px] mb-4"
              style={{ color: 'var(--color-muted)' }}
            >
              Open a folder or repository to start working.
            </p>
            <button
              onClick={() => setPickerOpen(true)}
              className="flex items-center justify-center h-8 px-4 rounded-lg text-xs font-semibold w-full transition-colors hover:bg-white/5"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text)',
              }}
            >
              Open Project
            </button>
          </div>
        ) : (
          /* Active State - Project header + tree */
          <div className="py-2">
            <button
              onClick={() => setPickerOpen(true)}
              className="w-full px-4 py-1.5 flex items-center gap-2 text-sm cursor-pointer hover:bg-white/5 text-left"
            >
              <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>
                folder_open
              </span>
              <span className="font-medium truncate flex-1" style={{ color: 'var(--color-text)' }}>
                {currentProject.name}
              </span>
              <span className="material-symbols-outlined text-[14px]" style={{ color: 'var(--color-muted)' }}>
                swap_horiz
              </span>
            </button>
            <div className="px-4 mt-1 mb-2">
              <p className="text-[10px] truncate" style={{ color: 'var(--color-muted)', fontFamily: 'var(--font-code)' }}>
                {currentProject.path}
              </p>
            </div>

            {/* Loading state */}
            {loading && (
              <div className="px-4 py-2">
                <p className="text-xs animate-pulse" style={{ color: 'var(--color-muted)' }}>
                  Loading files...
                </p>
              </div>
            )}

            {/* Error state */}
            {error && (
              <div className="px-4 py-2">
                <p className="text-xs" style={{ color: '#E06C75' }}>
                  {error}
                </p>
              </div>
            )}

            {/* Tree */}
            {!loading && !error && (
              <div role="tree">
                {displayEntries.map((entry) => (
                  <TreeNode
                    key={entry.path}
                    entry={entry}
                    projectId={currentProject.id}
                    depth={0}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <ProjectPicker open={pickerOpen} onClose={() => setPickerOpen(false)} />
    </>
  )
}
