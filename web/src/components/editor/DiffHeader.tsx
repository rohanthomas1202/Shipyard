import { useState, useEffect, useRef } from 'react'

interface DiffHeaderProps {
  filePath: string
  stepLabel?: string
  onAccept?: () => void
  onReject?: () => void
  loading?: boolean
}

export function DiffHeader({ filePath, stepLabel, onAccept, onReject, loading }: DiffHeaderProps) {
  const [confirmingReject, setConfirmingReject] = useState(false)
  const rejectTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const handleRejectClick = () => {
    if (confirmingReject) {
      clearTimeout(rejectTimerRef.current)
      setConfirmingReject(false)
      onReject?.()
    } else {
      setConfirmingReject(true)
      rejectTimerRef.current = setTimeout(() => setConfirmingReject(false), 3000)
    }
  }

  // Cleanup timer on unmount
  useEffect(() => () => clearTimeout(rejectTimerRef.current), [])

  return (
    <header
      className="flex items-center justify-between px-6 h-[56px] shrink-0 sticky top-0 z-20"
      style={{
        background: 'rgba(30, 33, 43, 0.5)',
        backdropFilter: 'var(--blur-heavy)',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center rounded-lg w-8 h-8"
          style={{ background: 'rgba(255,255,255,0.1)', color: 'var(--color-primary)' }}
        >
          <span className="material-symbols-outlined text-[20px]">code_blocks</span>
        </div>
        <div>
          <h2 className="text-[15px] font-semibold leading-tight" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-code)' }}>
            {filePath}
          </h2>
          {stepLabel && (
            <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-muted)' }}>
              {stepLabel}
            </p>
          )}
        </div>
      </div>
      <div className="flex gap-3">
        <button
          onClick={handleRejectClick}
          disabled={loading}
          className="flex items-center justify-center rounded-lg h-8 px-4 text-[13px] font-semibold transition-colors disabled:opacity-50 gap-1.5"
          style={{
            border: confirmingReject ? '1px solid #EF4444' : '1px solid var(--color-border)',
            color: confirmingReject ? '#EF4444' : 'var(--color-text)',
          }}
        >
          <span className="material-symbols-outlined text-[16px]">close</span>
          {confirmingReject ? 'Confirm Reject?' : 'Reject Edit'}
        </button>
        <button
          onClick={onAccept}
          disabled={loading}
          className="flex items-center justify-center rounded-lg h-8 px-4 text-[13px] font-semibold text-white transition-all disabled:opacity-50 gap-1.5"
          style={{ background: 'var(--color-primary)', boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)' }}
        >
          <span className="material-symbols-outlined text-[16px]">check</span>
          Accept Edit
        </button>
      </div>
    </header>
  )
}
