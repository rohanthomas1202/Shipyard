import type { Project } from '../../../types'

interface GitHubTabProps {
  project: Project
  onChange: (updates: Partial<Project>) => void
}

export function GitHubTab({ project, onChange }: GitHubTabProps) {
  return (
    <div className="space-y-5">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
          Repository
        </label>
        <input
          type="text"
          value={project.github_repo || ''}
          onChange={(e) => onChange({ github_repo: e.target.value || null })}
          placeholder="owner/repo"
          className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
          style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
      </div>
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
          Personal Access Token
        </label>
        <input
          type="password"
          placeholder="ghp_..."
          onChange={(e) => onChange({ github_pat: e.target.value || null } as Partial<Project>)}
          className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
          style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <p className="text-[11px] mt-1" style={{ color: 'var(--color-muted)' }}>
          Stored locally. Never sent to the frontend after save.
        </p>
      </div>
    </div>
  )
}
