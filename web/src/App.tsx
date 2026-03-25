import { useState } from 'react'
import { WebSocketProvider } from './context/WebSocketContext'
import { ProjectProvider } from './context/ProjectContext'
import { AppShell } from './components/layout/AppShell'
import { ErrorBoundary } from './components/layout/ErrorBoundary'

function App() {
  const [projectId, setProjectId] = useState<string | null>(null)

  return (
    <ErrorBoundary>
      <WebSocketProvider projectId={projectId}>
        <ProjectProvider onProjectChange={setProjectId}>
          <AppShell />
        </ProjectProvider>
      </WebSocketProvider>
    </ErrorBoundary>
  )
}

export default App
