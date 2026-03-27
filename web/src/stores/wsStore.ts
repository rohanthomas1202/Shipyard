import { create } from 'zustand'
import type { WSEvent, RunSnapshot } from '../types'

interface WSStore {
  // Connection
  status: 'connecting' | 'connected' | 'disconnected'
  setStatus: (s: WSStore['status']) => void

  // Run snapshot
  snapshot: RunSnapshot | null
  setSnapshot: (s: RunSnapshot | null) => void

  // Agent events (consumed by ActivityStream panel only)
  agentEvents: WSEvent[]
  appendAgentEvent: (e: WSEvent) => void
  clearAgentEvents: () => void

  // File change tracking (consumed by FileExplorer panel only)
  changedFiles: Record<string, 'modified' | 'added' | 'deleted'>
  setFileChanged: (path: string, status: 'modified' | 'added' | 'deleted') => void
  clearChangedFiles: () => void

  // Run error (set when backend emits error event)
  runError: { runId: string; error: string } | null
  setRunError: (runId: string, error: string) => void
  clearRunError: () => void

  // Last sequence per run
  lastSeq: Record<string, number>
  setLastSeq: (runId: string, seq: number) => void

  // Active node and plan step tracking
  activeNode: string | null
  setActiveNode: (node: string | null) => void
  planSteps: Array<{ kind: string; label: string; status: 'pending' | 'active' | 'done' }>
  setPlanSteps: (steps: Array<{ kind: string; label: string; status: 'pending' | 'active' | 'done' }>) => void
  updateStepStatus: (index: number, status: 'pending' | 'active' | 'done') => void
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

  runError: null,
  setRunError: (runId, error) => set({ runError: { runId, error } }),
  clearRunError: () => set({ runError: null }),

  lastSeq: {},
  setLastSeq: (runId, seq) => set((s) => ({
    lastSeq: { ...s.lastSeq, [runId]: seq },
  })),

  activeNode: null,
  setActiveNode: (node) => set({ activeNode: node }),

  planSteps: [],
  setPlanSteps: (steps) => set({ planSteps: steps }),
  updateStepStatus: (index, status) => set((s) => ({
    planSteps: s.planSteps.map((step, i) => i === index ? { ...step, status } : step),
  })),
}))
