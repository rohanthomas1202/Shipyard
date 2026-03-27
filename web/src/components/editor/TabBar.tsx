import { useWorkspaceStore } from '../../stores/workspaceStore'
import { TabItem } from './TabItem'

export function TabBar() {
  const openTabs = useWorkspaceStore((s) => s.openTabs)
  const activeTabId = useWorkspaceStore((s) => s.activeTabId)
  const setActiveTab = useWorkspaceStore((s) => s.setActiveTab)
  const closeTab = useWorkspaceStore((s) => s.closeTab)
  const pinTab = useWorkspaceStore((s) => s.pinTab)

  if (openTabs.length === 0) return null

  return (
    <div
      role="tablist"
      className="flex shrink-0"
      style={{
        height: 36,
        background: 'rgba(30, 33, 43, 0.6)',
        borderBottom: '1px solid var(--color-border)',
        overflowX: 'auto',
        overflowY: 'hidden',
        scrollbarWidth: 'none',
      }}
    >
      {openTabs.map((tab) => (
        <TabItem
          key={tab.id}
          tab={tab}
          isActive={tab.id === activeTabId}
          onClick={() => setActiveTab(tab.id)}
          onClose={() => closeTab(tab.id)}
          onDoubleClick={() => pinTab(tab.id)}
        />
      ))}
      <style>{`
        [role="tablist"]::-webkit-scrollbar { display: none; }
      `}</style>
    </div>
  )
}
