import { useState } from 'react'
import type { Tab } from '../../stores/workspaceStore'

interface TabItemProps {
  tab: Tab
  isActive: boolean
  onClick: () => void
  onClose: () => void
  onDoubleClick: () => void
}

const TAB_ICONS: Record<Tab['type'], string> = {
  file: 'description',
  diff: 'compare_arrows',
  welcome: 'code',
}

export function TabItem({ tab, isActive, onClick, onClose, onDoubleClick }: TabItemProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      role="tab"
      aria-selected={isActive}
      className="flex items-center gap-1.5 shrink-0 cursor-pointer select-none"
      style={{
        height: 36,
        paddingLeft: 12,
        paddingRight: 8,
        fontSize: 13,
        fontFamily: 'var(--font-ui)',
        fontStyle: tab.isPinned ? 'normal' : 'italic',
        color: isActive ? 'var(--color-text)' : 'var(--color-muted)',
        background: isActive
          ? 'rgba(30, 33, 43, 0.8)'
          : hovered
            ? 'rgba(255, 255, 255, 0.03)'
            : 'transparent',
        borderBottom: isActive ? '2px solid var(--color-primary)' : '2px solid transparent',
        lineHeight: 1.2,
      }}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onAuxClick={(e) => {
        if (e.button === 1) {
          e.preventDefault()
          onClose()
        }
      }}
    >
      <span
        className="material-symbols-outlined"
        style={{ fontSize: 16, lineHeight: 1 }}
      >
        {TAB_ICONS[tab.type]}
      </span>
      <span className="truncate max-w-[120px]">{tab.label}</span>
      {(hovered || isActive) && (
        <button
          aria-label={`Close ${tab.label}`}
          className="flex items-center justify-center rounded shrink-0 transition-opacity"
          style={{
            width: 28,
            height: 28,
            color: 'var(--color-muted)',
          }}
          onClick={(e) => {
            e.stopPropagation()
            onClose()
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
            close
          </span>
        </button>
      )}
    </div>
  )
}
