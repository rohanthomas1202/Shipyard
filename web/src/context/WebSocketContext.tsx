import { createContext, useContext, useCallback, useRef, useEffect, useState, type ReactNode } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useWsStore } from '../stores/wsStore'
import type { WSEvent, RunSnapshot } from '../types'

interface WebSocketContextValue {
  status: 'connecting' | 'connected' | 'disconnected'
  subscribe: (eventType: string, handler: (event: WSEvent) => void) => () => void
  send: (data: object) => void
  snapshot: RunSnapshot | null
  lastSeqRef: React.MutableRefObject<Map<string, number>>
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

export function WebSocketProvider({ projectId, children }: { projectId: string | null; children: ReactNode }) {
  const { status, send, onMessage } = useWebSocket(projectId)
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null)
  const lastSeqRef = useRef<Map<string, number>>(new Map())
  const subscribersRef = useRef<Map<string, Set<(event: WSEvent) => void>>>(new Map())

  // Bridge connection status to Zustand
  useEffect(() => {
    useWsStore.getState().setStatus(status)
  }, [status])

  useEffect(() => {
    const unsub = onMessage((event: WSEvent) => {
      const store = useWsStore.getState()

      // Track seq per run
      if (event.seq && event.run_id) {
        lastSeqRef.current.set(event.run_id, event.seq)
        store.setLastSeq(event.run_id, event.seq)
      }

      // Handle snapshot
      if (event.type === 'snapshot') {
        setSnapshot(event as unknown as RunSnapshot)
        store.setSnapshot(event as unknown as RunSnapshot)
        return
      }

      // Push to Zustand store
      store.appendAgentEvent(event)
      if (event.type === 'diff' && event.data.file_path) {
        store.setFileChanged(event.data.file_path as string, 'modified')
      }

      // Distribute to type-based subscribers (legacy)
      const handlers = subscribersRef.current.get(event.type)
      if (handlers) {
        handlers.forEach((handler) => handler(event))
      }

      // Also notify wildcard subscribers (legacy)
      const wildcardHandlers = subscribersRef.current.get('*')
      if (wildcardHandlers) {
        wildcardHandlers.forEach((handler) => handler(event))
      }
    })
    return unsub
  }, [onMessage])

  const subscribe = useCallback((eventType: string, handler: (event: WSEvent) => void) => {
    if (!subscribersRef.current.has(eventType)) {
      subscribersRef.current.set(eventType, new Set())
    }
    subscribersRef.current.get(eventType)!.add(handler)
    return () => {
      subscribersRef.current.get(eventType)?.delete(handler)
    }
  }, [])

  return (
    <WebSocketContext.Provider value={{ status, subscribe, send, snapshot, lastSeqRef }}>
      {children}
    </WebSocketContext.Provider>
  )
}

/** @deprecated Use useWsStore selectors for state. Use useWebSocketSend() for send. */
export function useWebSocketContext() {
  const context = useContext(WebSocketContext)
  if (!context) throw new Error('useWebSocketContext must be used within WebSocketProvider')
  return context
}

export function useWebSocketSend(): (data: object) => void {
  const context = useContext(WebSocketContext)
  if (!context) throw new Error('useWebSocketSend must be used within WebSocketProvider')
  return context.send
}
