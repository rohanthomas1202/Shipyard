import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'
import { GeneralTab } from './tabs/GeneralTab'
import { AIModelsTab } from './tabs/AIModelsTab'
import { EnvironmentTab } from './tabs/EnvironmentTab'
import { GitHubTab } from './tabs/GitHubTab'
import type { Project } from '../../types'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

const TABS = ['General', 'AI Models', 'Environment', 'GitHub'] as const

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const { currentProject, refreshProjects } = useProjectContext()
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('General')
  const [updates, setUpdates] = useState<Partial<Project>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleChange = useCallback((partial: Partial<Project>) => {
    setUpdates((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleSave = async () => {
    if (!currentProject) return
    setSaving(true)
    setError(null)
    try {
      await api.updateProject(currentProject.id, updates)
      await refreshProjects()
      setUpdates({})
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open || !currentProject) return null

  const merged = { ...currentProject, ...updates }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-[600px] max-h-[80vh] overflow-hidden rounded-2xl"
        style={{
          background: 'rgba(20, 22, 30, 0.85)',
          backdropFilter: 'blur(32px)',
          border: '1px solid var(--color-border)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <h2 className="text-lg font-bold" style={{ color: 'var(--color-text)' }}>Project Settings</h2>
          <button onClick={onClose} className="p-1 rounded-lg transition-colors" style={{ color: 'var(--color-muted)' }}>
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex px-6" style={{ borderBottom: '1px solid var(--color-border)' }}>
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="px-4 py-3 text-sm font-medium transition-colors"
              style={{
                color: activeTab === tab ? 'var(--color-text)' : 'var(--color-muted)',
                borderBottom: activeTab === tab ? '2px solid var(--color-primary)' : '2px solid transparent',
                fontWeight: activeTab === tab ? 600 : 500,
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {activeTab === 'General' && <GeneralTab project={merged} onChange={handleChange} />}
          {activeTab === 'AI Models' && <AIModelsTab project={merged} onChange={handleChange} />}
          {activeTab === 'Environment' && <EnvironmentTab project={merged} onChange={handleChange} />}
          {activeTab === 'GitHub' && <GitHubTab project={merged} onChange={handleChange} />}

          {error && (
            <div className="mt-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.15)', borderLeft: '3px solid var(--color-error)', color: 'var(--color-text)' }}>
              {error}
            </div>
          )}

          <div className="pt-4 mt-4 flex justify-end" style={{ borderTop: '1px solid var(--color-border)' }}>
            <button
              onClick={handleSave}
              disabled={saving || Object.keys(updates).length === 0}
              className="px-6 py-2 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50"
              style={{ background: 'var(--color-primary)', boxShadow: '0 0 15px rgba(99,102,241,0.3)' }}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
