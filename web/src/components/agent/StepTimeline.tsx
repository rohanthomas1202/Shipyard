interface Step {
  label: string
  status: 'done' | 'active' | 'pending'
}

interface StepTimelineProps {
  steps: Step[]
}

export function StepTimeline({ steps }: StepTimelineProps) {
  return (
    <div className="flex items-center gap-3 mb-6 overflow-x-auto">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-2 shrink-0">
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold"
            style={{
              background: step.status === 'done'
                ? 'rgba(16, 185, 129, 0.2)'
                : step.status === 'active'
                ? 'rgba(99, 102, 241, 0.2)'
                : 'var(--color-surface)',
              border: `1px solid ${
                step.status === 'done'
                  ? 'rgba(16, 185, 129, 0.4)'
                  : step.status === 'active'
                  ? 'rgba(99, 102, 241, 0.4)'
                  : 'var(--color-border)'
              }`,
              color: step.status === 'done'
                ? 'var(--color-success)'
                : step.status === 'active'
                ? 'var(--color-primary)'
                : 'var(--color-muted)',
            }}
          >
            {step.status === 'done' ? (
              <span className="material-symbols-outlined text-[14px]">check</span>
            ) : (
              i + 1
            )}
          </div>
          <span
            className="text-xs"
            style={{
              color: step.status === 'active' ? 'var(--color-primary)' : 'var(--color-muted)',
              fontWeight: step.status === 'active' ? 500 : 400,
            }}
          >
            {step.label}
          </span>
          {i < steps.length - 1 && (
            <div
              className="w-8 h-px"
              style={{
                background: step.status === 'done' ? 'rgba(16, 185, 129, 0.3)' : 'var(--color-border)',
              }}
            />
          )}
        </div>
      ))}
    </div>
  )
}
