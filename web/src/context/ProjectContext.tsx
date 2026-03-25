import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { api } from '../lib/api'
import { useWebSocketContext } from './WebSocketContext'
import type { Project, Run } from '../types'

interface ProjectContextValue {
  projects: Project[]
  currentProject: Project | null
  runs: Run[]
  currentRun: Run | null
  setCurrentProject: (project: Project | null) => void
  setCurrentRun: (run: Run | null) => void
  submitInstruction: (instruction: string, workingDir: string, context?: object) => Promise<string>
  refreshProjects: () => Promise<void>
  loading: boolean
}

const ProjectContext = createContext<ProjectContextValue | null>(null)

interface ProjectProviderProps {
  children: ReactNode
  onProjectChange?: (projectId: string | null) => void
}

export function ProjectProvider({ children, onProjectChange }: ProjectProviderProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, _setCurrentProject] = useState<Project | null>(null)

  const setCurrentProject = useCallback((project: Project | null) => {
    _setCurrentProject(project)
    onProjectChange?.(project?.id ?? null)
  }, [onProjectChange])
  const [runs] = useState<Run[]>([])
  const [currentRun, setCurrentRun] = useState<Run | null>(null)
  const [loading, setLoading] = useState(true)
  const { send } = useWebSocketContext()

  const refreshProjects = useCallback(async () => {
    try {
      const projects = await api.getProjects()
      setProjects(projects)
    } catch {
      // silently fail on initial load
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshProjects()
  }, [refreshProjects])

  const submitInstruction = useCallback(async (
    instruction: string,
    workingDir: string,
    context?: object,
  ): Promise<string> => {
    const result = await api.submitInstruction(
      instruction,
      workingDir,
      context,
      currentProject?.id,
    )
    const runId = result.run_id

    // Subscribe to run events via WebSocket
    send({ action: 'subscribe', run_id: runId })

    // Set current run
    setCurrentRun({
      id: runId,
      project_id: currentProject?.id || '',
      instruction,
      status: 'running',
      plan: [],
      branch: null,
      created_at: new Date().toISOString(),
      completed_at: null,
    })

    return runId
  }, [currentProject, send])

  return (
    <ProjectContext.Provider value={{
      projects,
      currentProject,
      runs,
      currentRun,
      setCurrentProject,
      setCurrentRun,
      submitInstruction,
      refreshProjects,
      loading,
    }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProjectContext() {
  const context = useContext(ProjectContext)
  if (!context) throw new Error('useProjectContext must be used within ProjectProvider')
  return context
}
