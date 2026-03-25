import { useWebSocketContext } from '../../context/WebSocketContext'
import { useProjectContext } from '../../context/ProjectContext'
import { TypingIndicator } from './TypingIndicator'
import { StreamingText } from './StreamingText'
import { StepTimeline } from './StepTimeline'
import { AutonomyToggle } from './AutonomyToggle'

export function AgentPanel() {
  const { status } = useWebSocketContext()
  const { currentRun, currentProject } = useProjectContext()

  const isWorking = currentRun?.status === 'running'

  // Build step timeline from run plan if available
  const planSteps = Array.isArray(currentRun?.plan) ? currentRun.plan as Array<{ label?: string; status?: string }> : []
  const timelineSteps = planSteps.map((step, i) => ({
    label: step.label || `Step ${i + 1}`,
    status: (step.status === 'done' ? 'done' : step.status === 'active' ? 'active' : 'pending') as 'done' | 'active' | 'pending',
  }))

  return (
    <>
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between shrink-0"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[18px]"
            style={{ color: 'var(--color-primary)', fontVariationSettings: "'FILL' 1" }}
          >
            smart_toy
          </span>
          <h2 className="text-sm font-bold" style={{ color: 'var(--color-text)' }}>
            AI Agent
          </h2>
        </div>
        <button className="p-1 rounded transition-colors" style={{ color: 'var(--color-muted)' }}>
          <span className="material-symbols-outlined text-[16px]">tune</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {isWorking ? (
          /* Active run: streaming UI */
          <>
            {timelineSteps.length > 0 && <StepTimeline steps={timelineSteps} />}

            <div
              className="p-3 rounded-lg text-xs"
              style={{ background: 'rgba(30, 33, 43, 0.4)', border: '1px solid var(--color-border)', color: 'var(--color-muted)' }}
            >
              <span className="font-medium" style={{ color: 'var(--color-text)' }}>Task: </span>
              {currentRun.instruction}
            </div>

            <StreamingText />
            <TypingIndicator />
          </>
        ) : (
          /* Idle: welcome UI */
          <>
            {/* Welcome Card */}
            <div
              className="p-4 rounded-xl relative overflow-hidden"
              style={{
                background: 'rgba(30, 33, 43, 0.4)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div
                className="absolute -top-10 -right-10 w-24 h-24 rounded-full"
                style={{ background: 'rgba(99, 102, 241, 0.2)', filter: 'blur(20px)' }}
              />
              <p className="text-sm font-medium mb-2 relative z-10" style={{ color: 'var(--color-text)' }}>
                Welcome to your workspace.
              </p>
              <p className="text-xs leading-relaxed relative z-10 mb-4" style={{ color: 'var(--color-muted)' }}>
                I'm ready to help you write, refactor, and understand your code.
              </p>
              <button
                className="w-full flex items-center justify-center gap-2 h-8 rounded-lg text-xs font-semibold relative z-10"
                style={{
                  background: 'rgba(99, 102, 241, 0.1)',
                  color: 'var(--color-primary)',
                  border: '1px solid rgba(99, 102, 241, 0.2)',
                }}
              >
                <span className="material-symbols-outlined text-[16px]">add</span>
                New Chat
              </button>
            </div>

            {/* Mode Toggle */}
            <AutonomyToggle />

            {/* Recent Contexts */}
            <div className="flex flex-col gap-2">
              <h3
                className="text-xs font-bold uppercase tracking-wider px-1 mb-1"
                style={{ color: 'var(--color-muted)' }}
              >
                Recent Contexts
              </h3>
              {[
                { title: 'Fix layout bug in header', meta: 'Yesterday • 4 messages' },
                { title: 'Optimize database query', meta: '2 days ago • 12 messages' },
                { title: 'Setup initial project structure', meta: 'Last week • 24 messages' },
              ].map(({ title, meta }) => (
                <button
                  key={title}
                  className="w-full flex items-start gap-3 p-2.5 rounded-xl text-left group transition-colors hover:bg-white/5"
                >
                  <span className="material-symbols-outlined text-[16px] mt-0.5" style={{ color: 'var(--color-muted)' }}>
                    chat_bubble
                  </span>
                  <div className="flex-1 overflow-hidden">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text)' }}>
                      {title}
                    </p>
                    <p className="text-xs truncate" style={{ color: 'var(--color-muted)' }}>{meta}</p>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
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
