import { create } from 'zustand'
import type { WSEvent, RunSnapshot } from '../types'

interface WSStore {
  // Connection
  status: 'connecting' | 'connected' | 'disconnected'
  setStatus: (s: WSStore['status']) => void

  // Run snapshot
  snapshot: RunSnapshot | null
  setSnapshot: (s: RunSnapshot | null) => void

  // Agent events (consumed by ActivityStream only)
  agentEvents: WSEvent[]
  appendAgentEvent: (e: WSEvent) => void
  clearAgentEvents: () => void

  // File change tracking (consumed by FileExplorer only)
  changedFiles: Record<string, 'modified' | 'added' | 'deleted'>
  setFileChanged: (path: string, status: 'modified' | 'added' | 'deleted') => void
  clearChangedFiles: () => void

  // Last sequence per run
  lastSeq: Record<string, number>
  setLastSeq: (runId: string, seq: number) => void
}

export const useWsStore = create<WSStore>()((set) => ({
  status: 'disconnected',
  setStatus: (status) => set({ status }),

  snapshot: null,
  setSnapshot: (snapshot) => set({ snapshot }),

  agentEvents: [],
  appendAgentEvent: (e) => set((s) => ({
    agentEvents: [...s.agentEvents, e],
  })),
  clearAgentEvents: () => set({ agentEvents: [] }),

  changedFiles: {},
  setFileChanged: (path, status) => set((s) => ({
    changedFiles: { ...s.changedFiles, [path]: status },
  })),
  clearChangedFiles: () => set({ changedFiles: {} }),

  lastSeq: {},
  setLastSeq: (runId, seq) => set((s) => ({
    lastSeq: { ...s.lastSeq, [runId]: seq },
  })),
}))
