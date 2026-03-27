import { useCallback } from 'react'
import { InstructionInput } from './InstructionInput'
import { ProjectSelector } from './ProjectSelector'
import { RunStatusIndicator } from './RunStatusIndicator'
import { useProjectContext } from '../../context/ProjectContext'
import { useWsStore } from '../../stores/wsStore'

export function TopBar() {
  const { currentProject, currentRun, submitInstruction } = useProjectContext()
  const wsStatus = useWsStore((s) => s.status)

  const isRunActive = currentRun?.status === 'running' || currentRun?.status === 'waiting_for_human'
  const inputDisabled = !currentProject || isRunActive

  const handleSubmit = useCallback((text: string) => {
    if (!currentProject) return
    submitInstruction(text, currentProject.path)
  }, [currentProject, submitInstruction])

  return (
    <div className="flex-shrink-0">
      <div
        className="flex items-center gap-4 px-4"
        style={{
          height: '52px',
          background: 'rgba(30, 33, 43, 0.8)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 'var(--radius-panel) var(--radius-panel) 0 0',
        }}
      >
        {/* Left: Project Selector */}
        <ProjectSelector />

        {/* Center: Instruction Input */}
        <InstructionInput onSubmit={handleSubmit} disabled={inputDisabled} />

        {/* Right: Run Status */}
        <RunStatusIndicator />
      </div>

      {/* WS disconnected banner */}
      {wsStatus === 'disconnected' && (
        <div
          className="flex items-center justify-center text-xs font-medium"
          style={{
            height: '24px',
            background: 'var(--color-warning)',
            color: '#0F111A',
          }}
        >
          Connection lost. Reconnecting...
        </div>
      )}
    </div>
  )
}
