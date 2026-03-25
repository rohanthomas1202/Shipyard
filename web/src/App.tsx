import { WebSocketProvider } from './context/WebSocketContext'
import { ProjectProvider } from './context/ProjectContext'
import { AppShell } from './components/layout/AppShell'
import { ErrorBoundary } from './components/layout/ErrorBoundary'

function App() {
  // TODO: Get projectId from URL or selection. Use null for now.
  const projectId = null

  return (
    <ErrorBoundary>
      <WebSocketProvider projectId={projectId}>
        <ProjectProvider>
          <AppShell />
        </ProjectProvider>
      </WebSocketProvider>
    </ErrorBoundary>
  )
}

export default App
