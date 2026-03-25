import type { Project } from '../../../types'

interface EnvironmentTabProps {
  project: Project
  onChange: (updates: Partial<Project>) => void
}

export function EnvironmentTab({ project, onChange }: EnvironmentTabProps) {
  const fields = [
    { key: 'test_command' as const, label: 'Test Command', placeholder: 'npm test' },
    { key: 'build_command' as const, label: 'Build Command', placeholder: 'npm run build' },
    { key: 'lint_command' as const, label: 'Lint Command', placeholder: 'npm run lint' },
  ]

  return (
    <div className="space-y-5">
      {fields.map(({ key, label, placeholder }) => (
        <div key={key}>
          <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--color-muted)' }}>
            {label}
          </label>
          <input
            type="text"
            value={project[key] || ''}
            onChange={(e) => onChange({ [key]: e.target.value || null })}
            placeholder={placeholder}
            className="w-full h-10 px-3 rounded-lg text-sm focus:outline-none"
            style={{
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
              fontFamily: 'var(--font-code)',
            }}
          />
        </div>
      ))}
    </div>
  )
}
