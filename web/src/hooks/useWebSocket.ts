import { useEffect, useRef, useCallback, useState } from 'react'
import type { WSEvent } from '../types'

type WSStatus = 'connecting' | 'connected' | 'disconnected'

const HEARTBEAT_TIMEOUT = 45_000 // 3 missed heartbeats at 15s each
const RECONNECT_DELAYS = [1000, 2000, 4000, 10000]

export function useWebSocket(projectId: string | null) {
  const [status, setStatus] = useState<WSStatus>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Set<(event: WSEvent) => void>>(new Set())
  const heartbeatTimerRef = useRef<number | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<number | null>(null)

  const connect = useCallback(() => {
    if (!projectId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/ws/${projectId}`)

    ws.onopen = () => {
      setStatus('connected')
      reconnectAttemptRef.current = 0
      resetHeartbeat()
    }

    ws.onmessage = (event) => {
      resetHeartbeat()
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'heartbeat') return
        handlersRef.current.forEach((handler) => handler(data as WSEvent))
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      clearHeartbeat()
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
    setStatus('connecting')
  }, [projectId])

  const resetHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current)
    heartbeatTimerRef.current = window.setTimeout(() => {
      // Heartbeat timeout — force reconnect
      wsRef.current?.close()
    }, HEARTBEAT_TIMEOUT)
  }, [])

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearTimeout(heartbeatTimerRef.current)
      heartbeatTimerRef.current = null
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current
    const delay = RECONNECT_DELAYS[Math.min(attempt, RECONNECT_DELAYS.length - 1)]
    reconnectAttemptRef.current = attempt + 1
    reconnectTimerRef.current = window.setTimeout(connect, delay)
  }, [connect])

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const onMessage = useCallback((handler: (event: WSEvent) => void) => {
    handlersRef.current.add(handler)
    return () => { handlersRef.current.delete(handler) }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearHeartbeat()
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect, clearHeartbeat])

  return { status, send, onMessage }
}
