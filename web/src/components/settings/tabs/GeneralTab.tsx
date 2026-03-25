import { useState, useEffect } from 'react'
import type { Project } from '../../../types'

interface GeneralTabProps {
  project: Project
  onChange: (updates: Partial<Project>) => void
}

export function GeneralTab({ project, onChange }: GeneralTabProps) {
  const [name, setName] = useState(project.name)
  const [path, setPath] = useState(project.path)

  useEffect(() => {
    setName(project.name)
    setPath(project.path)
  }, [project])

  return (
    <div className="space-y-5">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
          Project Name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => { setName(e.target.value); onChange({ name: e.target.value }) }}
          className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
          style={{
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
          }}
        />
      </div>
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
          Working Directory
        </label>
        <input
          type="text"
          value={path}
          onChange={(e) => { setPath(e.target.value); onChange({ path: e.target.value }) }}
          className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
          style={{
            background: 'rgba(0,0,0,0.3)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            fontFamily: 'var(--font-code)',
          }}
        />
      </div>
    </div>
  )
}
