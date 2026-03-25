import type { Project } from '../../../types'

interface AIModelsTabProps {
  project: Project
  onChange: (updates: Partial<Project>) => void
}

export function AIModelsTab({ project, onChange }: AIModelsTabProps) {
  return (
    <div className="space-y-5">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
          Default Model
        </label>
        <select
          value={project.default_model}
          onChange={(e) => onChange({ default_model: e.target.value })}
          className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none appearance-none"
          style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <option value="o3">o3 (Reasoning)</option>
          <option value="gpt-4o">GPT-4o (General)</option>
          <option value="gpt-4o-mini">GPT-4o-mini (Fast)</option>
        </select>
      </div>
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
          Autonomy Mode
        </label>
        <select
          value={project.autonomy_mode}
          onChange={(e) => onChange({ autonomy_mode: e.target.value })}
          className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none appearance-none"
          style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        >
          <option value="supervised">Supervised (review each edit)</option>
          <option value="autonomous">Autonomous (auto-apply)</option>
        </select>
      </div>
    </div>
  )
}
