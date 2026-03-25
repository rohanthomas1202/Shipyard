import { useState } from 'react'
import { MeshBackground } from './MeshBackground'
import { WorkspaceHome } from '../home/WorkspaceHome'
import { AgentPanel } from '../agent/AgentPanel'
import { FileTree } from '../explorer/FileTree'
import { DiffViewer } from '../editor/DiffViewer'
import { SettingsModal } from '../settings/SettingsModal'
import { useProjectContext } from '../../context/ProjectContext'

export function AppShell() {
  const { currentRun } = useProjectContext()
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <>
      <MeshBackground />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <div className="h-screen w-screen p-4 box-border">
        <div
          className="grid h-full w-full gap-4"
          style={{ gridTemplateColumns: '250px 1fr 300px' }}
        >
          {/* Left: File Explorer */}
          <aside className="glass-panel flex flex-col h-full overflow-hidden">
            <FileTree />
          </aside>

          {/* Center: Main Canvas */}
          <main className="flex flex-col h-full relative">
            {currentRun ? <DiffViewer /> : <WorkspaceHome />}
          </main>

          {/* Right: Agent Panel */}
          <aside className="glass-panel flex flex-col h-full overflow-hidden">
            <AgentPanel />
          </aside>
        </div>
      </div>
    </>
  )
}
