interface EventConfigEntry {
  icon: string
  badgeBg: string
  badgeColor: string
  expandable: boolean
}

export const EVENT_CONFIG: Record<string, EventConfigEntry> = {
  status: { icon: 'sync', badgeBg: 'rgba(99, 102, 241, 0.15)', badgeColor: '#6366F1', expandable: false },
  stream: { icon: 'auto_awesome', badgeBg: 'rgba(99, 102, 241, 0.15)', badgeColor: '#6366F1', expandable: false },
  plan_ready: { icon: 'checklist', badgeBg: 'rgba(99, 102, 241, 0.15)', badgeColor: '#6366F1', expandable: true },
  edit_applied: { icon: 'edit_document', badgeBg: 'rgba(16, 185, 129, 0.15)', badgeColor: '#10B981', expandable: true },
  exec_result: { icon: 'terminal', badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: true },
  validation_result: { icon: 'verified', badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: true },
  git: { icon: 'commit', badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: false },
  run_completed: { icon: 'check_circle', badgeBg: 'rgba(16, 185, 129, 0.15)', badgeColor: '#10B981', expandable: false },
  run_failed: { icon: 'error', badgeBg: 'rgba(239, 68, 68, 0.15)', badgeColor: '#EF4444', expandable: true },
  run_cancelled: { icon: 'cancel', badgeBg: 'rgba(148, 163, 184, 0.15)', badgeColor: '#94A3B8', expandable: false },
  error: { icon: 'warning', badgeBg: 'rgba(239, 68, 68, 0.15)', badgeColor: '#EF4444', expandable: true },
}

export const DEFAULT_EVENT_CONFIG: EventConfigEntry = {
  icon: 'info',
  badgeBg: 'rgba(148, 163, 184, 0.15)',
  badgeColor: '#94A3B8',
  expandable: true,
}

interface EventTypeBadgeProps {
  type: string
  badgeBg?: string
  badgeColor?: string
}

export function EventTypeBadge({ type, badgeBg, badgeColor }: EventTypeBadgeProps) {
  const config = EVENT_CONFIG[type] ?? DEFAULT_EVENT_CONFIG
  const bg = badgeBg ?? config.badgeBg
  const color = badgeColor ?? config.badgeColor
  const label = type.replace(/_/g, ' ')

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 8px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 1.2,
        background: bg,
        color,
      }}
    >
      <span
        className="material-symbols-outlined"
        style={{
          fontSize: 14,
          fontVariationSettings: "'FILL' 1",
        }}
      >
        {config.icon}
      </span>
      <span>{label}</span>
    </span>
  )
}
