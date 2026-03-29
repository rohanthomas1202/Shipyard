import { useRef, useEffect, useMemo, useState } from 'react'
import { useWsStore } from '../../stores/wsStore'
import { useProjectContext } from '../../context/ProjectContext'
import { StepTimeline } from './StepTimeline'
import { AutonomyToggle } from './AutonomyToggle'
import { RunSection } from './RunSection'
import { NewEventBadge } from './NewEventBadge'
import { ProgressHeader } from './ProgressHeader'
import { FailureHeatmap } from './FailureHeatmap'
import type { WSEvent } from '../../types'

export function AgentPanel() {
  const agentEvents = useWsStore((s) => s.agentEvents)
  const wsPlanSteps = useWsStore((s) => s.planSteps)
  const runError = useWsStore((s) => s.runError)
  const status = useWsStore((s) => s.status)
  const { currentRun, currentProject } = useProjectContext()

  // Auto-scroll refs and state (D-02)
  const containerRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const rafRef = useRef(0)
  const [newEventCount, setNewEventCount] = useState(0)

  // Run grouping (D-05): group events by run_id
  const runGroups = useMemo(() => {
    const groups: Map<string, { instruction: string; events: WSEvent[] }> = new Map()
    for (const event of agentEvents) {
      const rid = event.run_id
      if (!rid) continue
      if (!groups.has(rid)) {
        let instruction = rid.slice(0, 8) + '...'
        if (currentRun && currentRun.id === rid) {
          instruction = currentRun.instruction
        } else if (event.type === 'status' && typeof event.data.instruction === 'string') {
          instruction = event.data.instruction
        }
        groups.set(rid, { instruction, events: [] })
      }
      groups.get(rid)!.events.push(event)
    }
    return groups
  }, [agentEvents, currentRun])

  // Scroll handler with RAF guard (Research Pattern 1)
  const handleScroll = () => {
    cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      const el = containerRef.current
      if (!el) return
      isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight <= 50
      if (isAtBottomRef.current) {
        setNewEventCount(0)
      }
    })
  }

  // Auto-scroll effect: fires when events count changes
  useEffect(() => {
    if (isAtBottomRef.current && containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      })
    } else if (!isAtBottomRef.current) {
      setNewEventCount((prev) => prev + 1)
    }
  }, [agentEvents.length])

  // Reset on new run start
  useEffect(() => {
    if (currentRun?.status === 'running') {
      setNewEventCount(0)
      isAtBottomRef.current = true
      if (containerRef.current) {
        containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' })
      }
    }
  }, [currentRun?.id])

  // Badge click handler
  const handleBadgeClick = () => {
    setNewEventCount(0)
    isAtBottomRef.current = true
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }

  // Derived state
  const hasError = runError && currentRun && runError.runId === currentRun.id
  const isWorking = currentRun?.status === 'running' && !hasError
  const hasEvents = agentEvents.length > 0
  const isMultiRun = runGroups.size > 1

  // Timeline steps: prefer live wsStore steps, fallback to run plan
  const timelineSteps = wsPlanSteps.length > 0
    ? wsPlanSteps.map((step, i) => ({
        label: step.label || `Step ${i + 1}`,
        status: step.status,
      }))
    : (Array.isArray(currentRun?.plan) ? currentRun.plan as Array<{ label?: string; status?: string }> : []).map((step, i) => ({
        label: step.label || `Step ${i + 1}`,
        status: (step.status === 'done' ? 'done' : step.status === 'active' ? 'active' : 'pending') as 'done' | 'active' | 'pending',
      }))

  return (
    <>
      {/* StepTimeline -- shown when plan steps exist */}
      {timelineSteps.length > 0 && (
        <div className="px-4 pt-2 pb-0 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <StepTimeline steps={timelineSteps} />
        </div>
      )}

      {/* Progress metrics header */}
      <ProgressHeader />

      {/* Stream body */}
      <div className="flex-1 overflow-hidden relative">
        {!hasEvents ? (
          /* Empty state per UI-SPEC */
          <div className="h-full flex flex-col items-center justify-center gap-3 p-4">
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 48, color: 'var(--color-muted)' }}
            >
              smart_toy
            </span>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              No activity yet
            </h3>
            <p className="text-xs text-center leading-relaxed" style={{ color: 'var(--color-muted)' }}>
              Start a run from the instruction bar above to see agent progress here.
            </p>
            <AutonomyToggle />
          </div>
        ) : (
          /* Activity stream */
          <>
            <div
              ref={containerRef}
              onScroll={handleScroll}
              role="log"
              aria-live="polite"
              className="h-full overflow-y-auto px-4 py-2 flex flex-col gap-2"
            >
              {Array.from(runGroups.entries()).map(([rid, group]) => (
                <RunSection
                  key={rid}
                  runId={rid}
                  instruction={group.instruction}
                  events={group.events}
                  isMultiRun={isMultiRun}
                />
              ))}
            </div>

            {/* Floating badge per D-02 */}
            <NewEventBadge count={newEventCount} onClick={handleBadgeClick} />
          </>
        )}
      </div>

      {/* Failure heatmap -- below activity stream */}
      <div style={{ borderTop: '1px solid var(--color-border)', padding: 12 }}>
        <FailureHeatmap />
      </div>

      {/* Status */}
      <div
        className="px-4 py-3 flex items-center gap-2"
        style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
      >
        <div className="relative flex h-2 w-2">
          <span
            className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
            style={{
              background: !currentProject ? 'var(--color-muted)'
                : status === 'disconnected' ? 'var(--color-warning)'
                : isWorking ? 'var(--color-warning)'
                : 'var(--color-primary)',
            }}
          />
          <span
            className="relative inline-flex rounded-full h-2 w-2"
            style={{
              background: !currentProject ? 'var(--color-muted)'
                : status === 'disconnected' ? 'var(--color-warning)'
                : isWorking ? 'var(--color-warning)'
                : 'var(--color-primary)',
            }}
          />
        </div>
        <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
          {!currentProject
            ? 'No project selected'
            : status === 'disconnected'
            ? 'Disconnected — reconnecting...'
            : status === 'connecting'
            ? 'Connecting...'
            : isWorking
            ? 'Agent Working'
            : 'Agent Idle'}
        </span>
      </div>
    </>
  )
}
