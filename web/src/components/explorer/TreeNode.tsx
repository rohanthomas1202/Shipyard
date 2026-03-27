import { useState, useCallback } from 'react'
import type { FileEntry } from '../../types'
import { api } from '../../lib/api'
import { useWsStore } from '../../stores/wsStore'
import { useWorkspaceStore } from '../../stores/workspaceStore'

interface TreeNodeProps {
  entry: FileEntry
  projectId: string
  depth: number
}

const CHANGE_COLORS: Record<string, string> = {
  modified: '#E2B93D',
  added: '#73C991',
  deleted: '#E06C75',
}

const CHANGE_LABELS: Record<string, string> = {
  modified: 'M',
  added: 'A',
  deleted: 'D',
}

export function TreeNode({ entry, projectId, depth }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(false)
  const [children, setChildren] = useState<FileEntry[] | null>(null)
  const [loading, setLoading] = useState(false)

  const changeStatus = useWsStore((s) => s.changedFiles[entry.path])
  const selectedPath = useWorkspaceStore((s) => s.selectedPath)
  const isSelected = entry.path === selectedPath

  const handleToggle = useCallback(async () => {
    if (!entry.is_dir) return

    if (expanded) {
      setExpanded(false)
      return
    }

    if (children === null) {
      setLoading(true)
      try {
        const res = await api.browseProject(projectId, entry.path)
        setChildren(res.entries)
      } catch {
        setChildren([])
      } finally {
        setLoading(false)
      }
    }

    setExpanded(true)
  }, [entry.is_dir, entry.path, expanded, children, projectId])

  const handleFileClick = useCallback(() => {
    if (entry.is_dir) {
      handleToggle()
      return
    }
    useWorkspaceStore.getState().openFile(entry.path)
    useWorkspaceStore.getState().setSelectedPath(entry.path)
  }, [entry.is_dir, entry.path, handleToggle])

  return (
    <>
      <div
        role="treeitem"
        className="flex items-center cursor-pointer select-none transition-colors"
        style={{
          paddingLeft: `${depth * 16 + 8}px`,
          height: 28,
          fontSize: 13,
          background: isSelected ? 'rgba(99, 102, 241, 0.1)' : undefined,
        }}
        onClick={handleFileClick}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = ''
        }}
      >
        {/* Icon */}
        {entry.is_dir ? (
          <span
            className="material-symbols-outlined text-[16px] mr-1.5 shrink-0"
            style={{ color: 'var(--color-primary)' }}
          >
            {expanded ? 'folder_open' : 'folder'}
          </span>
        ) : (
          <span
            className="material-symbols-outlined text-[16px] mr-1.5 shrink-0"
            style={{ color: 'var(--color-muted)' }}
          >
            description
          </span>
        )}

        {/* Name */}
        <span
          className="truncate flex-1"
          style={{ color: 'var(--color-text)' }}
        >
          {entry.name}
        </span>

        {/* Change indicator */}
        {changeStatus && (
          <span
            className="shrink-0 mr-2 font-bold"
            style={{
              color: CHANGE_COLORS[changeStatus],
              fontSize: 10,
              fontFamily: 'var(--font-code)',
            }}
          >
            {CHANGE_LABELS[changeStatus]}
          </span>
        )}

        {/* Loading spinner */}
        {loading && (
          <span
            className="shrink-0 mr-2 animate-pulse text-[10px]"
            style={{ color: 'var(--color-muted)' }}
          >
            ...
          </span>
        )}
      </div>

      {/* Children */}
      {expanded && children && children.map((child) => (
        <TreeNode
          key={child.path}
          entry={child}
          projectId={projectId}
          depth={depth + 1}
        />
      ))}
    </>
  )
}
