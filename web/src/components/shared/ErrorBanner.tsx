import { useEffect } from 'react'

interface ErrorBannerProps {
  message: string
  onDismiss: () => void
  autoDismissMs?: number
}

export function ErrorBanner({ message, onDismiss, autoDismissMs = 8000 }: ErrorBannerProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, autoDismissMs)
    return () => clearTimeout(timer)
  }, [onDismiss, autoDismissMs])

  return (
    <div
      className="p-3 rounded-lg text-sm cursor-pointer transition-opacity hover:opacity-80"
      style={{
        background: 'rgba(239, 68, 68, 0.15)',
        borderLeft: '3px solid var(--color-error)',
        color: 'var(--color-text)',
      }}
      onClick={onDismiss}
    >
      <div className="flex items-center justify-between">
        <span>{message}</span>
        <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-muted)' }}>close</span>
      </div>
    </div>
  )
}
