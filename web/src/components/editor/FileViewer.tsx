import { useEffect, useCallback, useReducer } from 'react'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'
import { highlightCode } from '../../lib/shiki'

interface FileViewerProps {
  path: string
}

interface FileState {
  content: string | null
  language: string
  loading: boolean
  error: string | null
  binary: boolean
  highlighted: string
  fetchKey: number
}

type FileAction =
  | { type: 'fetch_start' }
  | { type: 'fetch_success'; content: string | null; language: string; binary: boolean }
  | { type: 'fetch_error'; error: string }
  | { type: 'highlight'; html: string }
  | { type: 'retry' }

function fileReducer(state: FileState, action: FileAction): FileState {
  switch (action.type) {
    case 'fetch_start':
      return { ...state, loading: true, error: null, content: null, highlighted: '', binary: false }
    case 'fetch_success':
      return { ...state, loading: false, content: action.content, language: action.language, binary: action.binary }
    case 'fetch_error':
      return { ...state, loading: false, error: action.error }
    case 'highlight':
      return { ...state, highlighted: action.html }
    case 'retry':
      return { ...state, loading: true, error: null, fetchKey: state.fetchKey + 1 }
  }
}

export function FileViewer({ path }: FileViewerProps) {
  const { currentProject } = useProjectContext()
  const [state, dispatch] = useReducer(fileReducer, {
    content: null,
    language: 'text',
    loading: true,
    error: null,
    binary: false,
    highlighted: '',
    fetchKey: 0,
  })

  const { content, language, loading, error, binary, highlighted, fetchKey } = state

  // Fetch file content
  useEffect(() => {
    if (!currentProject?.id) return

    let cancelled = false
    dispatch({ type: 'fetch_start' })

    api.readFile(currentProject.id, path)
      .then((res) => {
        if (!cancelled) {
          dispatch({ type: 'fetch_success', content: res.content, language: res.language, binary: res.binary })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          dispatch({ type: 'fetch_error', error: err.message || 'Failed to load file' })
        }
      })

    return () => { cancelled = true }
  }, [path, currentProject?.id, fetchKey])

  // Highlight content with Shiki
  useEffect(() => {
    if (content === null || binary) return

    let cancelled = false
    highlightCode(content, language).then((html) => {
      if (!cancelled) dispatch({ type: 'highlight', html })
    })

    return () => { cancelled = true }
  }, [content, language, binary])

  const handleRetry = useCallback(() => {
    dispatch({ type: 'retry' })
  }, [])

  // Loading skeleton
  if (loading) {
    return <LoadingSkeleton />
  }

  // Error state
  if (error) {
    return <ErrorState message={error} onRetry={handleRetry} />
  }

  // Binary file
  if (binary) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 48, color: 'var(--color-muted)' }}
        >
          description
        </span>
        <p style={{ fontSize: 14, color: 'var(--color-muted)' }}>
          Binary file -- cannot display
        </p>
      </div>
    )
  }

  // Empty file
  if (content !== null && content.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 48, color: 'var(--color-muted)' }}
        >
          draft
        </span>
        <p style={{ fontSize: 14, color: 'var(--color-muted)' }}>
          Empty file
        </p>
      </div>
    )
  }

  // Normal render with line numbers and highlighted code
  const lines = (content || '').split('\n')

  return (
    <div className="flex h-full overflow-auto" style={{ fontFamily: 'var(--font-code)', fontSize: 13, lineHeight: 1.7 }}>
      {/* Line number gutter */}
      <div
        className="shrink-0 text-right select-none"
        style={{
          width: 50,
          color: 'rgba(148, 163, 184, 0.4)',
          borderRight: '1px solid var(--color-border)',
          paddingRight: 8,
          paddingTop: 4,
        }}
      >
        {lines.map((_, i) => (
          <div key={i} style={{ height: `${13 * 1.7}px` }}>
            {i + 1}
          </div>
        ))}
      </div>

      {/* Code content */}
      <div
        className="flex-1 overflow-x-auto"
        style={{ paddingLeft: 16, paddingTop: 4, whiteSpace: 'pre' }}
      >
        {highlighted ? (
          <div
            // Shiki generates safe HTML from parsed tokens, not user input
            dangerouslySetInnerHTML={{ __html: highlighted }}
            style={{ background: 'transparent' }}
          />
        ) : (
          <pre style={{ margin: 0, background: 'transparent' }}>
            <code>{content}</code>
          </pre>
        )}
      </div>
    </div>
  )
}

function LoadingSkeleton() {
  const widths = [72, 88, 60, 90, 45, 78, 55, 82]
  return (
    <div className="flex h-full" style={{ fontFamily: 'var(--font-code)', fontSize: 13, lineHeight: 1.7 }}>
      <div
        className="shrink-0 text-right select-none"
        style={{
          width: 50,
          color: 'rgba(148, 163, 184, 0.4)',
          borderRight: '1px solid var(--color-border)',
          paddingRight: 8,
          paddingTop: 4,
        }}
      >
        {widths.map((_, i) => (
          <div key={i} style={{ height: `${13 * 1.7}px` }}>
            {i + 1}
          </div>
        ))}
      </div>
      <div className="flex-1" style={{ paddingLeft: 16, paddingTop: 4 }}>
        {widths.map((w, i) => (
          <div
            key={i}
            className="animate-pulse rounded"
            style={{
              width: `${w}%`,
              height: 13,
              marginBottom: `${13 * 0.7}px`,
              background: 'rgba(255, 255, 255, 0.05)',
            }}
          />
        ))}
      </div>
    </div>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3">
      <span
        className="material-symbols-outlined"
        style={{ fontSize: 48, color: 'var(--color-error)' }}
      >
        error
      </span>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text)' }}>
        Failed to load file
      </h3>
      <p style={{ fontSize: 14, color: 'var(--color-muted)', textAlign: 'center', maxWidth: 320 }}>
        {message || 'The file may have been moved or deleted. Try refreshing the explorer.'}
      </p>
      <button
        onClick={onRetry}
        className="px-4 py-2 rounded-lg text-sm transition-colors"
        style={{
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
          background: 'transparent',
        }}
      >
        Retry
      </button>
    </div>
  )
}
