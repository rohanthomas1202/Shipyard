import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useWsStore } from '../stores/wsStore'
import { useWorkspaceStore } from '../stores/workspaceStore'
import type { RunSnapshot } from '../types'

interface WebSocketContextValue {
  send: (data: object) => void
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function WebSocketProvider({ projectId, children }: { projectId: string | null; children: ReactNode }) {
  const { status, send, onMessage } = useWebSocket(projectId)

  // Bridge connection status to Zustand
  useEffect(() => {
    useWsStore.getState().setStatus(status)
  }, [status])

  // Bridge WS events to Zustand store
  useEffect(() => {
    const unsub = onMessage((event) => {
      const store = useWsStore.getState()

      // Track seq per run
      if (event.seq && event.run_id) {
        store.setLastSeq(event.run_id, event.seq)
      }

      // Handle snapshot
      if (event.type === 'snapshot') {
        store.setSnapshot(event as unknown as RunSnapshot)
        return
      }

      // Track file changes from various event types
      if (event.type === 'diff' && typeof event.data.file_path === 'string') {
        store.setFileChanged(event.data.file_path, 'modified')
      }
      if (event.type === 'edit_proposed' && typeof event.data.file_path === 'string') {
        store.setFileChanged(event.data.file_path, 'modified')
      }
      if (event.type === 'file_created' && typeof event.data.file_path === 'string') {
        store.setFileChanged(event.data.file_path, 'added')
      }
      if (event.type === 'file_deleted' && typeof event.data.file_path === 'string') {
        store.setFileChanged(event.data.file_path, 'deleted')
      }

      // Auto-open diff tab when agent proposes an edit
      if (event.type === 'approval' && event.data?.event === 'edit.proposed') {
        const editId = event.data?.edit_id
        if (typeof editId === 'string') {
          useWorkspaceStore.getState().openDiff(editId)
        }
      }

      // Handle run errors from backend
      if (event.type === 'error' && event.run_id && event.data?.error) {
        store.setRunError(event.run_id, String(event.data.error ?? ''))
      }

      // Track active node from status events
      if (event.type === 'status' && event.node) {
        store.setActiveNode(event.node)
      }

      // Track plan steps from planner
      if (event.type === 'plan_ready' && Array.isArray(event.data?.steps)) {
        const steps = (event.data.steps as Array<{ kind: string; label: string }>).map((s, i) => ({
          kind: s.kind,
          label: s.label || `Step ${i + 1}`,
          status: 'pending' as const,
        }))
        store.setPlanSteps(steps)
      }

      // Handle run lifecycle events
      if (event.type === 'run_completed' || event.type === 'run_failed' || event.type === 'run_cancelled') {
        store.setActiveNode(null)

        // Auto-open diff tabs for completed runs with edits
        if (event.type === 'run_completed' && event.run_id) {
          import('../lib/api').then(({ api }) => {
            api.getEdits(event.run_id).then((edits) => {
              const ws = useWorkspaceStore.getState()
              for (const edit of edits) {
                if (edit.status === 'applied' || edit.status === 'committed') {
                  ws.openDiff(edit.id)
                }
              }
            }).catch(() => {})
          })
        }
      }

      // All non-snapshot events go to agentEvents
      store.appendAgentEvent(event)
    })
    return unsub
  }, [onMessage])

  return (
    <WebSocketContext.Provider value={{ send }}>
      {children}
    </WebSocketContext.Provider>
  )
}

/** Preferred hook — returns only the send function */
export function useWebSocketSend() {
  const context = useContext(WebSocketContext)
  if (!context) throw new Error('useWebSocketSend must be used within WebSocketProvider')
  return context.send
}

/** @deprecated Use useWebSocketSend() for send, useWsStore() for state */
export function useWebSocketContext() {
  const context = useContext(WebSocketContext)
  if (!context) throw new Error('useWebSocketContext must be used within WebSocketProvider')
  return context
}
