import { useState, useEffect, useRef } from 'react'
import { useProjectContext } from '../../context/ProjectContext'

export function ProjectSelector() {
  const { projects, currentProject, setCurrentProject, loading } = useProjectContext()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div ref={containerRef} className="relative flex-shrink-0" style={{ maxWidth: '200px' }}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm transition-colors hover:bg-white/5"
        style={{
          color: currentProject ? 'var(--color-text)' : 'var(--color-muted)',
          border: '1px solid var(--color-border)',
          background: 'rgba(30, 33, 43, 0.4)',
        }}
        disabled={loading}
      >
        <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>
          folder
        </span>
        <span className="truncate max-w-[140px]">
          {currentProject ? currentProject.name : 'Select project...'}
        </span>
        <span className="material-symbols-outlined text-[14px]" style={{ color: 'var(--color-muted)' }}>
          expand_more
        </span>
      </button>

      {open && (
        <div
          className="absolute top-full left-0 mt-1 w-full min-w-[180px] z-50 rounded-lg overflow-hidden"
          style={{
            background: 'rgba(20, 22, 30, 0.95)',
            backdropFilter: 'blur(24px)',
            border: '1px solid var(--color-border)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            maxHeight: '300px',
            overflowY: 'auto',
          }}
        >
          {projects.length === 0 ? (
            <div className="px-3 py-4 text-center text-xs" style={{ color: 'var(--color-muted)' }}>
              No projects found
            </div>
          ) : (
            projects.map((project) => (
              <button
                key={project.id}
                onClick={() => {
                  setCurrentProject(project)
                  setOpen(false)
                }}
                className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors"
                style={{
                  color: 'var(--color-text)',
                  background: currentProject?.id === project.id ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (currentProject?.id !== project.id) {
                    e.currentTarget.style.background = 'rgba(99, 102, 241, 0.15)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (currentProject?.id !== project.id) {
                    e.currentTarget.style.background = 'transparent'
                  }
                }}
              >
                <span className="truncate">{project.name}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
