import { useState, useEffect, useCallback } from 'react'
import { useWorkspaceStore } from '../../stores/workspaceStore'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'
import { TabBar } from './TabBar'
import { FileViewer } from './FileViewer'
import { WelcomeTab } from './WelcomeTab'
import { SideBySideDiff } from './SideBySideDiff'
import type { Edit } from '../../types'

export function EditorArea() {
  const openTabs = useWorkspaceStore((s) => s.openTabs)
  const activeTabId = useWorkspaceStore((s) => s.activeTabId)
  const closeTab = useWorkspaceStore((s) => s.closeTab)
  const setActiveTab = useWorkspaceStore((s) => s.setActiveTab)
  const activeTab = openTabs.find((t) => t.id === activeTabId)
  const { currentRun } = useProjectContext()

  const [editCache, setEditCache] = useState<Record<string, Edit>>({})

  // Fetch edit data when a diff tab is active
  useEffect(() => {
    if (!activeTab || activeTab.type !== 'diff' || !activeTab.editId) return
    if (editCache[activeTab.editId]) return
    if (!currentRun) return

    api.getEdits(currentRun.id).then((edits) => {
      const found = edits.find((e) => e.id === activeTab.editId)
      if (found) {
        setEditCache((prev) => ({ ...prev, [found.id]: found }))
      }
    }).catch(() => {})
  }, [activeTab, currentRun, editCache])

  const handleDiffResolved = useCallback(() => {
    if (!activeTab) return
    const currentId = activeTab.id

    // Find next pending diff tab
    const nextDiffTab = openTabs.find(
      (t) => t.type === 'diff' && t.id !== currentId
    )

    closeTab(currentId)
    if (nextDiffTab) {
      setActiveTab(nextDiffTab.id)
    }
  }, [activeTab, openTabs, closeTab, setActiveTab])

  const currentEdit = activeTab?.editId ? editCache[activeTab.editId] : undefined

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
        ) : activeTab.type === 'diff' && currentEdit ? (
          <SideBySideDiff edit={currentEdit} onResolved={handleDiffResolved} />
        ) : activeTab.type === 'diff' ? (
          <div
            className="flex items-center justify-center h-full"
            style={{ color: 'var(--color-muted)', fontSize: 14 }}
          >
            Loading diff...
          </div>
        ) : (
          <WelcomeTab />
        )}
      </div>
    </div>
  )
}
