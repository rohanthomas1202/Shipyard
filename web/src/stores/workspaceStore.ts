import { create } from 'zustand'

export interface Tab {
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
  pinTab: (tabId: string) => void
}

export const useWorkspaceStore = create<WorkspaceStore>()((set) => ({
  openTabs: [],
  activeTabId: null,
  selectedPath: null,

  openFile: (path, pin = false) => set((s) => {
    // If the file is already open, activate it (and pin if requested)
    const existing = s.openTabs.find((t) => t.type === 'file' && t.path === path)
    if (existing) {
      if (pin && !existing.isPinned) {
        return {
          openTabs: s.openTabs.map((t) =>
            t.id === existing.id ? { ...t, isPinned: true } : t
          ),
          activeTabId: existing.id,
        }
      }
      return { activeTabId: existing.id }
    }

    const tab: Tab = {
      id: `file-${path}`,
      type: 'file',
      label: path.split('/').pop() || path,
      path,
      isPinned: pin,
    }

    // If opening as preview (not pinned), replace any existing unpinned file tab
    if (!pin) {
      const previewIndex = s.openTabs.findIndex(
        (t) => t.type === 'file' && !t.isPinned
      )
      if (previewIndex !== -1) {
        const newTabs = [...s.openTabs]
        newTabs[previewIndex] = tab
        return { openTabs: newTabs, activeTabId: tab.id }
      }
    }

    return { openTabs: [...s.openTabs, tab], activeTabId: tab.id }
  }),

  openDiff: (editId) => set((s) => {
    const existing = s.openTabs.find((t) => t.type === 'diff' && t.editId === editId)
    if (existing) {
      return { activeTabId: existing.id }
    }
    // Diff tabs are always pinned (per D-05, D-11)
    const tab: Tab = {
      id: `diff-${editId}`,
      type: 'diff',
      label: `Diff ${editId.slice(0, 8)}`,
      editId,
      isPinned: true,
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

  pinTab: (tabId) => set((s) => ({
    openTabs: s.openTabs.map((t) =>
      t.id === tabId ? { ...t, isPinned: true } : t
    ),
  })),
}))
