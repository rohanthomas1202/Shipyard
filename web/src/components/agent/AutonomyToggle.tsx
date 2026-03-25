import { useState } from 'react'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'

export function AutonomyToggle() {
  const { currentProject, refreshProjects } = useProjectContext()
  const [loading, setLoading] = useState(false)

  const isAutonomous = currentProject?.autonomy_mode === 'autonomous'

  const toggle = async () => {
    if (!currentProject || loading) return
    setLoading(true)
    try {
      const newMode = isAutonomous ? 'supervised' : 'autonomous'
      await api.updateProject(currentProject.id, { autonomy_mode: newMode })
      await refreshProjects()
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-between px-1">
      <span className="text-xs font-medium" style={{ color: 'var(--color-muted)' }}>Mode</span>
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
          {isAutonomous ? 'Autonomous' : 'Supervised'}
        </span>
        <button
          onClick={toggle}
          disabled={loading || !currentProject}
          className="relative w-9 h-5 rounded-full transition-colors disabled:opacity-50"
          style={{ background: isAutonomous ? 'var(--color-primary)' : 'rgba(255,255,255,0.1)' }}
        >
          <div
            className="absolute top-[2px] w-4 h-4 rounded-full bg-white transition-[left] duration-200"
            style={{ left: isAutonomous ? '18px' : '2px' }}
          />
        </button>
      </div>
    </div>
  )
}
