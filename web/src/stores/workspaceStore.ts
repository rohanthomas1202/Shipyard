import { create } from 'zustand'

interface Tab {
  id: string
  type: 'file' | 'diff' | 'welcome'
  label: string
  path?: string
  editId?: string
  isPinned: boolean
}

interface WorkspaceStore {
  openTabs: Tab[]
  activeTabId: string | null
  selectedPath: string | null
  openFile: (path: string, pin?: boolean) => void
  openDiff: (editId: string) => void
  closeTab: (tabId: string) => void
  setActiveTab: (tabId: string) => void
  setSelectedPath: (path: string | null) => void
}

export const useWorkspaceStore = create<WorkspaceStore>()((set) => ({
  openTabs: [],
  activeTabId: null,
  selectedPath: null,
  openFile: (path, pin = false) => set((s) => {
    const existing = s.openTabs.find((t) => t.type === 'file' && t.path === path)
    if (existing) {
      return { activeTabId: existing.id }
    }
    const tab: Tab = {
      id: `file-${path}`,
      type: 'file',
      label: path.split('/').pop() || path,
      path,
      isPinned: pin,
    }
    return { openTabs: [...s.openTabs, tab], activeTabId: tab.id }
  }),
  openDiff: (editId) => set((s) => {
    const existing = s.openTabs.find((t) => t.type === 'diff' && t.editId === editId)
    if (existing) {
      return { activeTabId: existing.id }
    }
    const tab: Tab = {
      id: `diff-${editId}`,
      type: 'diff',
      label: `Diff: ${editId}`,
      editId,
      isPinned: false,
    }
    return { openTabs: [...s.openTabs, tab], activeTabId: tab.id }
  }),
  closeTab: (tabId) => set((s) => {
    const tabs = s.openTabs.filter((t) => t.id !== tabId)
    const activeTabId = s.activeTabId === tabId
      ? (tabs[tabs.length - 1]?.id ?? null)
      : s.activeTabId
    return { openTabs: tabs, activeTabId }
  }),
  setActiveTab: (tabId) => set({ activeTabId: tabId }),
  setSelectedPath: (path) => set({ selectedPath: path }),
}))
