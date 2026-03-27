interface NewEventBadgeProps {
  count: number
  onClick: () => void
}

export function NewEventBadge({ count, onClick }: NewEventBadgeProps) {
  if (count <= 0) return null

  const label = `${count} new event${count === 1 ? '' : 's'}`

  return (
    <button
      role="status"
      aria-live="assertive"
      aria-label={`${label}, click to scroll to latest`}
      onClick={onClick}
      style={{
        position: 'absolute',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        padding: '6px 16px',
        borderRadius: 9999,
        border: 'none',
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: 600,
        color: '#FFFFFF',
        background: 'rgba(99, 102, 241, 0.9)',
        boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
        animation: 'badge-pulse 2s infinite',
      }}
    >
      {label}
    </button>
  )
}
