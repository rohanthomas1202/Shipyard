interface PanelHeaderProps {
  title: string
  onCollapse: () => void
  collapsed?: boolean
  collapseDirection?: 'left' | 'right'
  collapseTooltip?: string
}

export function PanelHeader({ title, onCollapse, collapsed, collapseDirection = 'left', collapseTooltip }: PanelHeaderProps) {
  if (collapsed) return null

  const chevronIcon = collapseDirection === 'left' ? 'chevron_left' : 'chevron_right'
  const defaultTooltip = collapseDirection === 'left' ? 'Collapse explorer' : 'Collapse agent panel'

  return (
    <div className="flex items-center justify-between px-3 pt-3 pb-1 flex-shrink-0">
      <span
        className="text-[11px] font-semibold uppercase"
        style={{ color: 'var(--color-muted)', letterSpacing: '0.05em' }}
        role="heading"
        aria-level={2}
      >
        {title}
      </span>
      <button
        onClick={onCollapse}
        className="p-0.5 rounded hover:opacity-80 transition-opacity"
        title={collapseTooltip || defaultTooltip}
        style={{ color: 'var(--color-muted)' }}
      >
        <span className="material-symbols-outlined text-[16px]">{chevronIcon}</span>
      </button>
    </div>
  )
}
