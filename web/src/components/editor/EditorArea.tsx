import { useWorkspaceStore } from '../../stores/workspaceStore'
import { TabBar } from './TabBar'
import { FileViewer } from './FileViewer'
import { WelcomeTab } from './WelcomeTab'

export function EditorArea() {
  const openTabs = useWorkspaceStore((s) => s.openTabs)
  const activeTabId = useWorkspaceStore((s) => s.activeTabId)
  const activeTab = openTabs.find((t) => t.id === activeTabId)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TabBar />
      <div
        role="tabpanel"
        className="flex-1 overflow-hidden"
        style={{ background: 'rgba(15, 17, 26, 0.95)' }}
      >
        {openTabs.length === 0 || !activeTab ? (
          <WelcomeTab />
        ) : activeTab.type === 'file' && activeTab.path ? (
          <FileViewer path={activeTab.path} />
        ) : activeTab.type === 'diff' ? (
          <div
            className="flex items-center justify-center h-full"
            style={{ color: 'var(--color-muted)', fontSize: 14 }}
          >
            Diff viewer loading...
          </div>
        ) : (
          <WelcomeTab />
        )}
      </div>
    </div>
  )
}
