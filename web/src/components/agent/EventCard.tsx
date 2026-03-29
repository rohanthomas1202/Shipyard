import { useState, useId } from 'react'
import type { WSEvent, DecisionTraceData } from '../../types'
import { EventTypeBadge, EVENT_CONFIG, DEFAULT_EVENT_CONFIG } from './EventTypeBadge'
import { DecisionTrace } from './DecisionTrace'

const NODE_LABELS: Record<string, string> = {
  planning: 'Planning',
  receive: 'Receiving',
  reader: 'Reading files',
  editor: 'Editing',
  validator: 'Validating',
  executor: 'Running command',
  git_ops: 'Git operations',
  merger: 'Merging changes',
  reporter: 'Generating report',
  coordinator: 'Coordinating',
}

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

interface EventCardProps {
  event: WSEvent
  animate?: boolean
}

export function EventCard({ event, animate }: EventCardProps) {
  const [expanded, setExpanded] = useState(false)
  const detailId = useId()
  const config = EVENT_CONFIG[event.type] ?? DEFAULT_EVENT_CONFIG

  // Determine card surface colors
  const isError = event.type === 'error' || event.type === 'run_failed'
  const isValidationPass = event.type === 'validation_result' && event.data.passed === true

  let cardBg = 'rgba(30, 33, 43, 0.4)'
  let cardBorder = '1px solid var(--color-border)'
  if (isError) {
    cardBg = 'rgba(239, 68, 68, 0.08)'
    cardBorder = '1px solid rgba(239, 68, 68, 0.2)'
  } else if (isValidationPass) {
    cardBg = 'rgba(16, 185, 129, 0.08)'
    cardBorder = '1px solid rgba(16, 185, 129, 0.2)'
  }

  // Dynamic badge colors for validation_result
  let badgeBgOverride: string | undefined
  let badgeColorOverride: string | undefined
  if (event.type === 'validation_result') {
    if (event.data.passed === true) {
      badgeBgOverride = 'rgba(16, 185, 129, 0.15)'
      badgeColorOverride = '#10B981'
    } else {
      badgeBgOverride = 'rgba(239, 68, 68, 0.15)'
      badgeColorOverride = '#EF4444'
    }
  }

  const nodeLabel = event.node ? (NODE_LABELS[event.node] ?? event.node) : ''

  return (
    <div
      role="article"
      aria-label={`${event.type} event`}
      style={{
        padding: 12,
        borderRadius: 'var(--radius-element)',
        border: cardBorder,
        background: cardBg,
        ...(animate ? { animation: 'slide-up 200ms ease-out' } : {}),
      }}
    >
      {/* Row 1: Badge + node label + timestamp */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <EventTypeBadge
          type={event.type}
          badgeBg={badgeBgOverride}
          badgeColor={badgeColorOverride}
        />
        {nodeLabel && (
          <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>
            {nodeLabel}
          </span>
        )}
        <span style={{ fontSize: 11, color: 'var(--color-muted)', marginLeft: 'auto' }}>
          {relativeTime(event.timestamp)}
        </span>
      </div>

      {/* Row 2: Body content */}
      <div style={{ marginTop: 8 }}>
        <EventBody event={event} />
      </div>

      {/* Expandable detail */}
      {config.expandable && (
        <div style={{ marginTop: 4 }}>
          <button
            aria-expanded={expanded}
            aria-controls={detailId}
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: 'var(--color-muted)',
              fontSize: 11,
            }}
          >
            {expanded ? 'Hide details' : 'Show details'}
          </button>
          <div
            id={detailId}
            style={{
              maxHeight: expanded ? 300 : 0,
              overflow: 'hidden',
              transition: expanded
                ? 'max-height 200ms ease-out'
                : 'max-height 150ms ease-in',
            }}
          >
            <div
              style={{
                marginTop: 8,
                padding: 8,
                borderRadius: 4,
                background: 'rgba(0, 0, 0, 0.2)',
                fontFamily: 'var(--font-code)',
                fontSize: 13,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              <ExpandedDetail event={event} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function EventBody({ event }: { event: WSEvent }) {
  switch (event.type) {
    case 'status': {
      const stepPrefix = typeof event.data.step_index === 'number'
        ? `Step ${(event.data.step_index as number) + 1}: `
        : ''
      const label = event.node
        ? (NODE_LABELS[event.node] ?? event.node)
        : String(event.data.status ?? '')
      return <span style={{ fontSize: 14 }}>{stepPrefix}{label}</span>
    }

    case 'stream':
      return null

    case 'plan_ready': {
      const steps = Array.isArray(event.data.steps) ? event.data.steps : []
      return <span style={{ fontSize: 14 }}>{steps.length} steps planned</span>
    }

    case 'edit_applied':
      return (
        <span style={{ fontFamily: 'var(--font-code)', fontSize: 13 }}>
          {String(event.data.file_path ?? '')}
        </span>
      )

    case 'exec_result':
      return (
        <span style={{ fontSize: 14 }}>
          <span style={{ fontFamily: 'var(--font-code)', fontSize: 13 }}>
            {String(event.data.command ?? '')}
          </span>
          {event.data.exit_code !== undefined && (
            <span style={{ color: 'var(--color-muted)', marginLeft: 8, fontSize: 11 }}>
              exit {String(event.data.exit_code)}
            </span>
          )}
        </span>
      )

    case 'validation_result':
      if (event.data.passed === true) {
        return <span style={{ fontSize: 14, color: '#10B981' }}>Passed</span>
      } else {
        const issues = Array.isArray(event.data.issues) ? event.data.issues : []
        return (
          <span style={{ fontSize: 14, color: '#EF4444' }}>
            {issues.length} issue{issues.length === 1 ? '' : 's'} found
          </span>
        )
      }

    case 'git':
      return (
        <span style={{ fontSize: 14 }}>
          {String(event.data.branch ?? event.data.message ?? '')}
        </span>
      )

    case 'run_completed':
      return <span style={{ fontSize: 14, color: '#10B981' }}>Run completed</span>

    case 'run_failed':
      return (
        <span style={{ fontFamily: 'var(--font-code)', fontSize: 13, color: '#EF4444' }}>
          {String(event.data.error ?? 'Run failed')}
        </span>
      )

    case 'run_cancelled':
      return <span style={{ fontSize: 14, color: 'var(--color-muted)' }}>Run cancelled</span>

    case 'error':
      return (
        <span style={{ fontFamily: 'var(--font-code)', fontSize: 13, color: '#EF4444' }}>
          {String(event.data.error ?? 'Unknown error')}
        </span>
      )

    case 'decision_trace': {
      const traceData = event.data as unknown as DecisionTraceData
      return <DecisionTrace trace={traceData} />
    }

    default:
      return null
  }
}

function ExpandedDetail({ event }: { event: WSEvent }) {
  switch (event.type) {
    case 'plan_ready': {
      const steps = Array.isArray(event.data.steps) ? event.data.steps as Array<{ kind?: string; label?: string }> : []
      return (
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          {steps.map((step, i) => (
            <li key={i}>
              {step.label ?? step.kind ?? `Step ${i + 1}`}
            </li>
          ))}
        </ol>
      )
    }

    case 'exec_result':
      return (
        <>
          {event.data.stdout && <div>{String(event.data.stdout)}</div>}
          {event.data.stderr && (
            <div style={{ color: '#EF4444' }}>{String(event.data.stderr)}</div>
          )}
        </>
      )

    case 'validation_result': {
      const issues = Array.isArray(event.data.issues) ? event.data.issues : []
      return (
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {issues.map((issue, i) => (
            <li key={i}>{String(issue)}</li>
          ))}
        </ul>
      )
    }

    case 'edit_applied':
      return <>{String(event.data.anchor ?? event.data.detail ?? JSON.stringify(event.data, null, 2))}</>

    case 'run_failed':
    case 'error':
      return <>{String(event.data.error ?? JSON.stringify(event.data, null, 2))}</>

    case 'decision_trace':
      return <>{JSON.stringify(event.data, null, 2)}</>

    default:
      return <>{JSON.stringify(event.data, null, 2)}</>
  }
}
