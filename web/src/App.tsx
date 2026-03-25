import { WebSocketProvider } from './context/WebSocketContext'
import { ProjectProvider } from './context/ProjectContext'
import { AppShell } from './components/layout/AppShell'

function App() {
  // TODO: Get projectId from URL or selection. Use null for now.
  const projectId = null

  return (
    <WebSocketProvider projectId={projectId}>
      <ProjectProvider>
        <AppShell />
      </ProjectProvider>
    </WebSocketProvider>
  )
}

export default App
