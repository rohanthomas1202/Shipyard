import { useState, useEffect } from 'react'
import { MeshBackground } from './MeshBackground'
import { WorkspaceHome } from '../home/WorkspaceHome'
import { AgentPanel } from '../agent/AgentPanel'
import { FileTree } from '../explorer/FileTree'
import { DiffViewer } from '../editor/DiffViewer'
import { SettingsModal } from '../settings/SettingsModal'
import { ProjectPicker } from '../explorer/ProjectPicker'
import { useProjectContext } from '../../context/ProjectContext'
import { useHotkeys } from '../../hooks/useHotkeys'

export function AppShell() {
  const { currentRun } = useProjectContext()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [projectPickerOpen, setProjectPickerOpen] = useState(false)

  const [leftCollapsed, setLeftCollapsed] = useState(() => {
    return localStorage.getItem('shipyard-left-collapsed') === 'true'
  })
  const [rightCollapsed, setRightCollapsed] = useState(() => {
    return localStorage.getItem('shipyard-right-collapsed') === 'true'
  })

  useEffect(() => {
    localStorage.setItem('shipyard-left-collapsed', String(leftCollapsed))
  }, [leftCollapsed])

  useEffect(() => {
    localStorage.setItem('shipyard-right-collapsed', String(rightCollapsed))
  }, [rightCollapsed])

  const gridCols = `${leftCollapsed ? '48px' : '250px'} 1fr ${rightCollapsed ? '0px' : '300px'}`

  useHotkeys([
    {
      key: 'p',
      modifiers: ['ctrl', 'shift'],
      handler: () => {
        // Focus prompt input — WorkspaceHome needs to expose a ref or we use DOM query
        const textarea = document.querySelector('textarea') as HTMLTextAreaElement
        textarea?.focus()
      },
    },
  ])

  return (
    <>
      <MeshBackground />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <ProjectPicker open={projectPickerOpen} onClose={() => setProjectPickerOpen(false)} />
      <div className="h-screen w-screen p-4 box-border">
        <div
          className="grid h-full w-full gap-4"
          style={{
            gridTemplateColumns: gridCols,
            transition: 'grid-template-columns 0.2s ease',
          }}
        >
          {/* Left: File Explorer */}
          <aside className="glass-panel flex flex-col h-full overflow-hidden">
            {leftCollapsed ? (
              /* Icon rail when collapsed */
              <div className="flex flex-col items-center gap-3 p-2 pt-3">
                <button
                  onClick={() => setLeftCollapsed(false)}
                  className="p-1 rounded-lg hover:opacity-80 transition-opacity"
                  title="Expand explorer"
                  style={{ color: 'var(--color-muted)' }}
                >
                  <span className="material-symbols-outlined text-[20px]">folder</span>
                </button>
                <button
                  onClick={() => setSettingsOpen(true)}
                  className="p-1 rounded-lg hover:opacity-80 transition-opacity"
                  title="Settings"
                  style={{ color: 'var(--color-muted)' }}
                >
                  <span className="material-symbols-outlined text-[20px]">settings</span>
                </button>
              </div>
            ) : (
              /* Full explorer */
              <FileTree onCollapse={() => setLeftCollapsed(true)} />
            )}
          </aside>

          {/* Center: Main Canvas */}
          <main className="flex flex-col h-full relative">
            {currentRun ? (
              <DiffViewer />
            ) : (
              <WorkspaceHome
                onOpenSettings={() => setSettingsOpen(true)}
                onOpenProjectPicker={() => setProjectPickerOpen(true)}
              />
            )}
          </main>

          {/* Right: Agent Panel */}
          <aside
            className="glass-panel flex flex-col h-full overflow-hidden"
            style={{
              opacity: rightCollapsed ? 0 : 1,
              transition: 'opacity 0.2s ease',
              pointerEvents: rightCollapsed ? 'none' : 'auto',
            }}
          >
            {!rightCollapsed && (
              <div className="flex flex-col h-full overflow-hidden">
                <div className="flex items-center justify-between px-3 pt-3 pb-1 flex-shrink-0">
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-muted)' }}>
                    Agent
                  </span>
                  <button
                    onClick={() => setRightCollapsed(true)}
                    className="p-0.5 rounded hover:opacity-80 transition-opacity"
                    title="Collapse agent panel"
                    style={{ color: 'var(--color-muted)' }}
                  >
                    <span className="material-symbols-outlined text-[16px]">chevron_right</span>
                  </button>
                </div>
                <div className="flex-1 overflow-hidden">
                  <AgentPanel />
                </div>
              </div>
            )}
          </aside>
        </div>

        {/* Floating button to re-open right panel when collapsed */}
        {rightCollapsed && (
          <button
            onClick={() => setRightCollapsed(false)}
            className="fixed bottom-6 right-6 p-2 rounded-full shadow-lg hover:opacity-80 transition-opacity"
            title="Show agent panel"
            style={{ background: 'var(--color-primary)', color: 'white' }}
          >
            <span className="material-symbols-outlined text-[20px]">smart_toy</span>
          </button>
        )}
      </div>
    </>
  )
}
