import { useState, useEffect } from 'react'
import { DiffHeader } from './DiffHeader'
import { DiffLine } from './DiffLine'
import { useWebSocketContext } from '../../context/WebSocketContext'
import { useProjectContext } from '../../context/ProjectContext'
import { api } from '../../lib/api'
import type { Edit } from '../../types'

export function DiffViewer() {
  const [edits, setEdits] = useState<Edit[]>([])
  const [currentEditIndex, setCurrentEditIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const { subscribe } = useWebSocketContext()
  const { currentRun } = useProjectContext()

  // Listen for diff events
  useEffect(() => {
    const unsub = subscribe('approval', (event) => {
      if (event.data.event === 'edit.proposed' && currentRun) {
        // Refresh edits from API
        api.getEdits(currentRun.id, 'proposed').then(setEdits).catch(() => {})
      }
    })
    return unsub
  }, [subscribe, currentRun])

  // Load edits on mount
  useEffect(() => {
    if (currentRun) {
      api.getEdits(currentRun.id).then(setEdits).catch(() => {})
    }
  }, [currentRun])

  const currentEdit = edits[currentEditIndex]
  if (!currentEdit) return null

  const handleAccept = async () => {
    setLoading(true)
    try {
      const opId = `op_${currentEdit.id}_approve`
      await api.patchEdit(currentEdit.run_id, currentEdit.id, 'approve', opId)
      // Move to next edit or refresh
      const updated = await api.getEdits(currentRun!.id, 'proposed')
      setEdits(updated)
      setCurrentEditIndex(0)
    } catch {
      // error handled by caller
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    setLoading(true)
    try {
      const opId = `op_${currentEdit.id}_reject`
      await api.patchEdit(currentEdit.run_id, currentEdit.id, 'reject', opId)
      const updated = await api.getEdits(currentRun!.id, 'proposed')
      setEdits(updated)
      setCurrentEditIndex(0)
    } catch {
      // error handled
    } finally {
      setLoading(false)
    }
  }

  // Build diff lines from edit content
  const diffLines = buildDiffLines(currentEdit)

  return (
    <div className="glass-panel flex flex-col h-full overflow-hidden">
      <DiffHeader
        filePath={currentEdit.file_path}
        stepLabel={`Step ${currentEdit.step + 1} — ${edits.length} edit(s) pending`}
        onAccept={handleAccept}
        onReject={handleReject}
        loading={loading}
      />

      <div className="flex-1 overflow-auto" style={{ fontFamily: 'var(--font-code)', fontSize: '13px', lineHeight: '1.7' }}>
        <table className="w-full text-left border-collapse">
          <colgroup>
            <col className="w-[50px]" />
            <col className="w-[50px]" />
            <col />
          </colgroup>
          <tbody>
            {diffLines.map((line, i) => (
              <DiffLine key={i} {...line} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div
        className="flex items-center gap-3 px-6 py-3"
        style={{
          background: 'rgba(30, 33, 43, 0.5)',
          backdropFilter: 'var(--blur-heavy)',
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <button
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all"
          style={{ background: 'var(--color-primary)', boxShadow: '0 0 15px rgba(99, 102, 241, 0.3)' }}
        >
          <span className="material-symbols-outlined text-[16px]">commit</span>
          Commit & Push
        </button>
        <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
          {edits.length} edit(s) pending review
        </span>
      </div>
    </div>
  )
}

interface DiffLineData {
  type: 'add' | 'remove' | 'context'
  oldLineNo?: number
  newLineNo?: number
  content: string
}

function buildDiffLines(edit: Edit): DiffLineData[] {
  const lines: DiffLineData[] = []
  const oldLines = (edit.old_content || '').split('\n')
  const newLines = (edit.new_content || '').split('\n')

  // Simple diff: show old as removals, new as additions
  // For a real diff, you'd use a diff algorithm. This is V1.
  let oldLineNo = 1
  let newLineNo = 1

  for (const line of oldLines) {
    lines.push({ type: 'remove', oldLineNo: oldLineNo++, content: line })
  }
  for (const line of newLines) {
    lines.push({ type: 'add', newLineNo: newLineNo++, content: line })
  }

  return lines
}
