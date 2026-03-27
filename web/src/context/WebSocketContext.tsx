import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useWsStore } from '../stores/wsStore'
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
