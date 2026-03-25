interface ActionBlockProps {
  label: string
  detail?: string
}

export function ActionBlock({ label, detail }: ActionBlockProps) {
  return (
    <div
      className="rounded-lg p-3 flex items-center gap-3 relative overflow-hidden"
      style={{
        background: 'rgba(0,0,0,0.4)',
        border: '1px solid var(--color-border)',
      }}
    >
      <span
        className="material-symbols-outlined text-[18px] animate-spin"
        style={{ color: 'var(--color-primary)' }}
      >
        sync
      </span>
      <div>
        <p className="text-xs" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-code)' }}>
          {label}
        </p>
        {detail && (
          <p className="text-[11px]" style={{ color: 'var(--color-muted)' }}>{detail}</p>
        )}
      </div>
    </div>
  )
}
