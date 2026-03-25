import { RunList } from './RunList'
import { useProjectContext } from '../../context/ProjectContext'

export function FileTree() {
  const { currentProject } = useProjectContext()

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
          <button className="p-1 rounded transition-colors" style={{ color: 'var(--color-muted)' }}>
            <span className="material-symbols-outlined text-[16px]">create_new_folder</span>
          </button>
          <button className="p-1 rounded transition-colors" style={{ color: 'var(--color-muted)' }}>
            <span className="material-symbols-outlined text-[16px]">note_add</span>
          </button>
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
              className="flex items-center justify-center h-8 px-4 rounded-lg text-xs font-semibold w-full transition-colors"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text)',
              }}
            >
              Open Folder
            </button>
            <button
              className="flex items-center justify-center h-8 px-4 rounded-lg text-xs font-semibold w-full mt-2 transition-colors"
              style={{ color: 'var(--color-muted)' }}
            >
              Clone Repository
            </button>
          </div>
        ) : (
          /* Active State — placeholder for now */
          <div className="py-2">
            <div className="px-4 py-1.5 flex items-center gap-2 text-sm cursor-pointer hover:bg-white/5">
              <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>
                folder_open
              </span>
              <span className="font-medium truncate" style={{ color: 'var(--color-text)' }}>
                {currentProject.name}
              </span>
            </div>
          </div>
        )}

        {/* Runs */}
        <RunList />
      </div>
    </>
  )
}
