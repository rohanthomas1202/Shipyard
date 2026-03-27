import { useState } from 'react'
import { WebSocketProvider } from './context/WebSocketContext'
import { ProjectProvider } from './context/ProjectContext'
import { IDELayout } from './components/layout/IDELayout'
import { ErrorBoundary } from './components/layout/ErrorBoundary'

function App() {
  const [projectId, setProjectId] = useState<string | null>(null)

  return (
    <ErrorBoundary>
      <WebSocketProvider projectId={projectId}>
        <ProjectProvider onProjectChange={setProjectId}>
          <IDELayout />
        </ProjectProvider>
      </WebSocketProvider>
    </ErrorBoundary>
  )
}

export default App
