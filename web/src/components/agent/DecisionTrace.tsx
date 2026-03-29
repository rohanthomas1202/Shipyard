import { useState } from 'react'
import type { DecisionTraceData } from '../../types'

const CATEGORY_STYLES: Record<string, { bg: string; color: string }> = {
  syntax: { bg: 'rgba(239, 68, 68, 0.15)', color: 'var(--color-error)' },
  test: { bg: 'rgba(245, 158, 11, 0.15)', color: 'var(--color-warning)' },
  contract: { bg: 'rgba(99, 102, 241, 0.15)', color: 'var(--color-primary)' },
  structural: { bg: 'rgba(148, 163, 184, 0.15)', color: 'var(--color-muted)' },
}

export function DecisionTrace({ trace }: { trace: DecisionTraceData }) {
  const [expanded, setExpanded] = useState(false)
  const style = CATEGORY_STYLES[trace.errorCategory] ?? CATEGORY_STYLES.structural

  return (
    <div
      className="cursor-pointer"
      onClick={() => setExpanded(!expanded)}
      aria-expanded={expanded}
    >
      {/* Collapsed: badge + truncated error */}
      <div className="flex items-center gap-2">
        <span
          className="material-symbols-outlined shrink-0 transition-transform duration-200"
          style={{
            fontSize: 14,
            color: 'var(--color-muted)',
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}
        >
          chevron_right
        </span>
        <span
          className="px-2 py-0.5 rounded-full text-xs font-semibold"
          style={{ background: style.bg, color: style.color }}
        >
          {trace.errorCategory}
        </span>
        <span className="text-xs truncate" style={{ color: 'var(--color-text)' }}>
          {trace.errorMessage.length > 80
            ? trace.errorMessage.slice(0, 80) + '...'
            : trace.errorMessage}
        </span>
      </div>

      {/* Expanded details */}
      <div
        className="overflow-hidden transition-all duration-200 ease-in-out"
        style={{ maxHeight: expanded ? 500 : 0 }}
      >
        <div className="mt-2 ml-5 flex flex-col gap-2">
          {/* Full error message */}
          <div className="text-xs" style={{ color: 'var(--color-text)' }}>
            {trace.errorMessage}
          </div>

          {/* Files read */}
          {trace.filesRead.length > 0 && (
            <div>
              <div className="text-xs uppercase mb-1" style={{ color: 'var(--color-muted)' }}>
                Files Read
              </div>
              <ul className="text-xs list-disc ml-4" style={{ color: 'var(--color-text)', fontFamily: 'var(--font-code, "JetBrains Mono", monospace)' }}>
                {trace.filesRead.slice(0, 5).map((f) => (
                  <li key={f}>{f}</li>
                ))}
                {trace.filesRead.length > 5 && (
                  <li style={{ color: 'var(--color-muted)' }}>
                    +{trace.filesRead.length - 5} more
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* LLM context */}
          {trace.llmPrompt && (
            <div>
              <div className="text-xs uppercase mb-1" style={{ color: 'var(--color-muted)' }}>
                LLM Prompt
              </div>
              <div
                className="text-xs p-2 rounded"
                style={{
                  background: 'rgba(15, 17, 26, 0.5)',
                  borderLeft: '2px solid var(--color-border)',
                  color: 'var(--color-muted)',
                  fontFamily: 'var(--font-code, "JetBrains Mono", monospace)',
                  fontSize: 12,
                }}
              >
                {trace.llmPrompt.slice(0, 200)}
                {trace.llmPrompt.length > 200 && '...'}
              </div>
            </div>
          )}
          {trace.llmResponse && (
            <div>
              <div className="text-xs uppercase mb-1" style={{ color: 'var(--color-muted)' }}>
                LLM Response
              </div>
              <div
                className="text-xs p-2 rounded"
                style={{
                  background: 'rgba(15, 17, 26, 0.5)',
                  borderLeft: '2px solid var(--color-border)',
                  color: 'var(--color-muted)',
                  fontFamily: 'var(--font-code, "JetBrains Mono", monospace)',
                  fontSize: 12,
                }}
              >
                {trace.llmResponse.slice(0, 200)}
                {trace.llmResponse.length > 200 && '...'}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
