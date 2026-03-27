import { useState, useCallback } from 'react'
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from 'react-resizable-panels'
import type { PanelSize } from 'react-resizable-panels'
import { MeshBackground } from './MeshBackground'
import { TopBar } from './TopBar'
import { PanelHeader } from './PanelHeader'
import { SettingsModal } from '../settings/SettingsModal'
import { ProjectPicker } from '../explorer/ProjectPicker'
import { FileTree } from '../explorer/FileTree'
import { AgentPanel } from '../agent/AgentPanel'
import { WorkspaceHome } from '../home/WorkspaceHome'
import { DiffViewer } from '../editor/DiffViewer'
import { RunProgress } from '../home/RunProgress'
import { useProjectContext } from '../../context/ProjectContext'
import { useHotkeys } from '../../hooks/useHotkeys'

const LEFT_COLLAPSED_SIZE = 3
const RIGHT_COLLAPSED_SIZE = 0

export function IDELayout() {
  const { currentRun } = useProjectContext()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [projectPickerOpen, setProjectPickerOpen] = useState(false)
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)

  const leftPanelRef = usePanelRef()
  const rightPanelRef = usePanelRef()

  const { defaultLayout, onLayoutChange } = useDefaultLayout({
    groupId: 'shipyard-ide-panels',
    storage: localStorage,
  })

  const handleLeftResize = useCallback((panelSize: PanelSize) => {
    setLeftCollapsed(panelSize.asPercentage <= LEFT_COLLAPSED_SIZE)
  }, [])

  const handleRightResize = useCallback((panelSize: PanelSize) => {
    setRightCollapsed(panelSize.asPercentage <= RIGHT_COLLAPSED_SIZE)
  }, [])

  const toggleLeft = useCallback(() => {
    if (leftPanelRef.current?.isCollapsed()) {
      leftPanelRef.current.expand()
    } else {
      leftPanelRef.current?.collapse()
    }
  }, [leftPanelRef])

  const toggleRight = useCallback(() => {
    if (rightPanelRef.current?.isCollapsed()) {
      rightPanelRef.current.expand()
    } else {
      rightPanelRef.current?.collapse()
    }
  }, [rightPanelRef])

  useHotkeys([
    {
      key: 'b',
      modifiers: ['meta'],
      handler: toggleLeft,
    },
    {
      key: 'j',
      modifiers: ['meta'],
      handler: toggleRight,
    },
    {
      key: 'p',
      modifiers: ['ctrl', 'shift'],
      handler: () => {
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
      <div className="h-screen w-screen flex flex-col">
        <div className="p-4 pb-0">
          <TopBar />
        </div>
        <div className="flex-1 px-4 pb-4 overflow-hidden">
          <Group
            orientation="horizontal"
            defaultLayout={defaultLayout}
            onLayoutChange={onLayoutChange}
          >
            {/* Left Panel: Explorer */}
            <Panel
              panelRef={leftPanelRef}
              defaultSize={20}
              minSize={10}
              collapsible
              collapsedSize={LEFT_COLLAPSED_SIZE}
              onResize={handleLeftResize}
            >
              <div
                className="h-full flex flex-col overflow-hidden rounded-bl-[var(--radius-panel)]"
                style={{
                  background: 'rgba(30, 33, 43, 0.6)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  border: '1px solid var(--color-border)',
                  borderTop: 'none',
                  borderTopLeftRadius: 0,
                  borderTopRightRadius: 0,
                }}
              >
                {leftCollapsed ? (
                  <div className="flex flex-col items-center gap-3 p-2 pt-3">
                    <button
                      onClick={() => leftPanelRef.current?.expand()}
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
                  <>
                    <PanelHeader
                      title="EXPLORER"
                      onCollapse={() => leftPanelRef.current?.collapse()}
                      collapseDirection="left"
                      collapseTooltip="Collapse explorer"
                    />
                    <div className="flex-1 overflow-hidden">
                      <FileTree onCollapse={() => leftPanelRef.current?.collapse()} />
                    </div>
                  </>
                )}
              </div>
            </Panel>

            {/* Left Separator */}
            <Separator>
              <div
                className="w-3 h-full flex items-center justify-center cursor-col-resize group"
                onDoubleClick={toggleLeft}
              >
                <div
                  className="w-[2px] h-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ background: 'rgba(99, 102, 241, 0.4)' }}
                />
              </div>
            </Separator>

            {/* Center Panel: Editor */}
            <Panel defaultSize={50} minSize={20}>
              <div
                className="h-full flex flex-col overflow-hidden"
                style={{
                  background: 'rgba(30, 33, 43, 0.4)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  border: '1px solid var(--color-border)',
                  borderTop: 'none',
                  borderRadius: 0,
                }}
              >
                <PanelHeader
                  title="EDITOR"
                  onCollapse={() => {}}
                  collapsed
                />
                <div className="flex-1 overflow-hidden">
                  {!currentRun ? (
                    <WorkspaceHome
                      onOpenSettings={() => setSettingsOpen(true)}
                      onOpenProjectPicker={() => setProjectPickerOpen(true)}
                    />
                  ) : currentRun.status === 'waiting_for_human' ? (
                    <DiffViewer />
                  ) : (
                    <RunProgress />
                  )}
                </div>
              </div>
            </Panel>

            {/* Right Separator */}
            <Separator>
              <div
                className="w-3 h-full flex items-center justify-center cursor-col-resize group"
                onDoubleClick={toggleRight}
              >
                <div
                  className="w-[2px] h-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ background: 'rgba(99, 102, 241, 0.4)' }}
                />
              </div>
            </Separator>

            {/* Right Panel: Agent */}
            <Panel
              panelRef={rightPanelRef}
              defaultSize={30}
              minSize={12}
              collapsible
              collapsedSize={RIGHT_COLLAPSED_SIZE}
              onResize={handleRightResize}
            >
              <div
                className="h-full flex flex-col overflow-hidden rounded-br-[var(--radius-panel)]"
                style={{
                  background: 'rgba(30, 33, 43, 0.6)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  border: '1px solid var(--color-border)',
                  borderTop: 'none',
                  borderTopLeftRadius: 0,
                  borderTopRightRadius: 0,
                }}
              >
                <PanelHeader
                  title="AGENT"
                  onCollapse={() => rightPanelRef.current?.collapse()}
                  collapseDirection="right"
                  collapseTooltip="Collapse agent panel"
                />
                <div className="flex-1 overflow-hidden">
                  <AgentPanel />
                </div>
              </div>
            </Panel>
          </Group>
        </div>
      </div>

      {/* Floating button to restore right panel when collapsed */}
      {rightCollapsed && (
        <button
          onClick={() => rightPanelRef.current?.expand()}
          className="fixed bottom-6 right-6 p-2 rounded-full shadow-lg hover:opacity-80 transition-opacity"
          title="Show agent panel"
          style={{ background: 'var(--color-primary)', color: 'white' }}
        >
          <span className="material-symbols-outlined text-[20px]">smart_toy</span>
        </button>
      )}
    </>
  )
}
