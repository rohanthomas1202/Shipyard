import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex items-center justify-center" style={{ background: 'var(--color-background)' }}>
          <div className="glass-panel p-8 max-w-md text-center">
            <span
              className="material-symbols-outlined text-4xl mb-4 block"
              style={{ color: 'var(--color-error)' }}
            >
              error
            </span>
            <h2 className="text-lg font-bold mb-2" style={{ color: 'var(--color-text)' }}>
              Something went wrong
            </h2>
            <p className="text-sm mb-4" style={{ color: 'var(--color-muted)' }}>
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 rounded-lg text-sm font-semibold text-white"
              style={{ background: 'var(--color-primary)' }}
            >
              Reload
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
