import { structuredPatch } from 'diff'
import { useState, useEffect, useRef, useCallback } from 'react'
import { highlightCode, mapLanguage } from '../../lib/shiki'
import { api } from '../../lib/api'
import { DiffHeader } from './DiffHeader'
import type { Edit } from '../../types'

interface SideBySideDiffProps {
  edit: Edit
  onResolved?: () => void
}

interface DiffLineData {
  type: 'add' | 'remove' | 'context' | 'spacer' | 'hunk-sep'
  lineNo?: number
  content: string
  htmlContent?: string
}

interface HunkInfo {
  oldStart: number
  newStart: number
  oldLines: number
  newLines: number
}

function detectLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase() || ''
  return mapLanguage(ext)
}

function buildSides(
  edit: Edit,
): { left: DiffLineData[]; right: DiffLineData[]; hunks: HunkInfo[] } {
  const oldContent = edit.old_content || ''
  const newContent = edit.new_content || ''

  // Handle new file case
  if (!edit.old_content && edit.new_content) {
    const newLines = newContent.split('\n')
    const left: DiffLineData[] = [{
      type: 'context',
      content: '(New file)',
    }]
    const right: DiffLineData[] = newLines.map((line, i) => ({
      type: 'add' as const,
      lineNo: i + 1,
      content: line,
    }))
    // Pad left to match right length
    while (left.length < right.length) {
      left.push({ type: 'spacer', content: '' })
    }
    return { left, right, hunks: [] }
  }

  // Handle deleted file case
  if (edit.old_content && !edit.new_content) {
    const oldLines = oldContent.split('\n')
    const left: DiffLineData[] = oldLines.map((line, i) => ({
      type: 'remove' as const,
      lineNo: i + 1,
      content: line,
    }))
    const right: DiffLineData[] = [{
      type: 'context',
      content: '(File deleted)',
    }]
    while (right.length < left.length) {
      right.push({ type: 'spacer', content: '' })
    }
    return { left, right, hunks: [] }
  }

  const patch = structuredPatch(
    edit.file_path, edit.file_path,
    oldContent, newContent,
    '', '', { context: 3 }
  )

  const left: DiffLineData[] = []
  const right: DiffLineData[] = []
  const hunks: HunkInfo[] = []

  for (let hi = 0; hi < patch.hunks.length; hi++) {
    const hunk = patch.hunks[hi]
    hunks.push({
      oldStart: hunk.oldStart,
      newStart: hunk.newStart,
      oldLines: hunk.oldLines,
      newLines: hunk.newLines,
    })

    // Add hunk separator (except for first hunk if it starts at line 1)
    if (hi > 0 || hunk.oldStart > 1) {
      const sepText = `@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@`
      left.push({ type: 'hunk-sep', content: sepText })
      right.push({ type: 'hunk-sep', content: sepText })
    }

    let oldLineNo = hunk.oldStart
    let newLineNo = hunk.newStart

    for (const line of hunk.lines) {
      const prefix = line[0]
      const text = line.slice(1)

      if (prefix === ' ') {
        left.push({ type: 'context', lineNo: oldLineNo++, content: text })
        right.push({ type: 'context', lineNo: newLineNo++, content: text })
      } else if (prefix === '-') {
        left.push({ type: 'remove', lineNo: oldLineNo++, content: text })
        right.push({ type: 'spacer', content: '' })
      } else if (prefix === '+') {
        left.push({ type: 'spacer', content: '' })
        right.push({ type: 'add', lineNo: newLineNo++, content: text })
      }
    }
  }

  return { left, right, hunks }
}

function extractLineHtml(fullHtml: string): string[] {
  // Shiki wraps output in <pre><code>...</code></pre>
  // Each line is separated by \n inside the <code> block
  // Extract the inner HTML of the <code> element
  const codeMatch = fullHtml.match(/<code[^>]*>([\s\S]*?)<\/code>/)
  if (!codeMatch) return []
  const inner = codeMatch[1]
  // Split by newline -- Shiki uses \n between lines within span structures
  return inner.split('\n')
}

export function SideBySideDiff({ edit, onResolved }: SideBySideDiffProps) {
  const [loading, setLoading] = useState(false)
  const [oldHighlightedLines, setOldHighlightedLines] = useState<string[]>([])
  const [newHighlightedLines, setNewHighlightedLines] = useState<string[]>([])
  const leftScrollRef = useRef<HTMLDivElement>(null)
  const rightScrollRef = useRef<HTMLDivElement>(null)
  const isSyncingScroll = useRef(false)

  const { left, right } = buildSides(edit)
  const lang = detectLanguage(edit.file_path)

  // Highlight both sides
  useEffect(() => {
    let cancelled = false
    async function highlight() {
      const oldCode = edit.old_content || ''
      const newCode = edit.new_content || ''

      const [oldHtml, newHtml] = await Promise.all([
        oldCode ? highlightCode(oldCode, lang) : Promise.resolve(''),
        newCode ? highlightCode(newCode, lang) : Promise.resolve(''),
      ])

      if (cancelled) return
      setOldHighlightedLines(oldHtml ? extractLineHtml(oldHtml) : [])
      setNewHighlightedLines(newHtml ? extractLineHtml(newHtml) : [])
    }
    highlight()
    return () => { cancelled = true }
  }, [edit.old_content, edit.new_content, lang])

  // Synchronized scroll
  const handleLeftScroll = useCallback(() => {
    if (isSyncingScroll.current) return
    isSyncingScroll.current = true
    if (leftScrollRef.current && rightScrollRef.current) {
      rightScrollRef.current.scrollTop = leftScrollRef.current.scrollTop
    }
    requestAnimationFrame(() => { isSyncingScroll.current = false })
  }, [])

  const handleRightScroll = useCallback(() => {
    if (isSyncingScroll.current) return
    isSyncingScroll.current = true
    if (leftScrollRef.current && rightScrollRef.current) {
      leftScrollRef.current.scrollTop = rightScrollRef.current.scrollTop
    }
    requestAnimationFrame(() => { isSyncingScroll.current = false })
  }, [])

  // Map original line numbers to highlighted HTML lines
  function getHighlightedContent(
    lineNo: number | undefined,
    side: 'old' | 'new',
    fallbackContent: string,
  ): string {
    const lines = side === 'old' ? oldHighlightedLines : newHighlightedLines
    if (lineNo !== undefined && lineNo > 0 && lineNo <= lines.length) {
      return lines[lineNo - 1]
    }
    // Escape fallback content
    return fallbackContent
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }

  const handleAccept = async () => {
    setLoading(true)
    try {
      const opId = `op_${edit.id}_approve`
      await api.patchEdit(edit.run_id, edit.id, 'approve', opId)
      onResolved?.()
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    setLoading(true)
    try {
      const opId = `op_${edit.id}_reject`
      await api.patchEdit(edit.run_id, edit.id, 'reject', opId)
      onResolved?.()
    } finally {
      setLoading(false)
    }
  }

  const renderLine = (
    line: DiffLineData,
    side: 'old' | 'new',
    index: number,
  ) => {
    if (line.type === 'hunk-sep') {
      return (
        <div
          key={`sep-${index}`}
          className="flex items-center justify-center"
          style={{
            background: 'rgba(99, 102, 241, 0.08)',
            height: 28,
            fontSize: 11,
            color: 'var(--color-muted)',
            fontFamily: 'var(--font-code)',
          }}
        >
          {line.content}
        </div>
      )
    }

    if (line.type === 'spacer') {
      return (
        <div
          key={`spacer-${index}`}
          className="flex"
          style={{ height: 'calc(1.7em + 1px)', minHeight: 22 }}
        >
          <div
            className="shrink-0 text-right select-none pr-2"
            style={{
              width: 50,
              color: 'rgba(148, 163, 184, 0.4)',
              borderRight: '1px solid var(--color-border)',
            }}
          />
          <div className="flex-1 pl-4" />
        </div>
      )
    }

    const bgColor = line.type === 'remove'
      ? 'rgba(239, 68, 68, 0.15)'
      : line.type === 'add'
        ? 'rgba(16, 185, 129, 0.15)'
        : 'transparent'

    const borderLeft = line.type === 'remove'
      ? '3px solid rgba(239, 68, 68, 0.8)'
      : line.type === 'add'
        ? '3px solid rgba(16, 185, 129, 0.8)'
        : 'none'

    const htmlContent = getHighlightedContent(line.lineNo, side, line.content)

    return (
      <div
        key={`line-${index}`}
        className="flex hover:bg-white/[0.03]"
        style={{
          background: bgColor,
          minHeight: 22,
        }}
      >
        <div
          className="shrink-0 text-right select-none pr-2 py-0"
          style={{
            width: 50,
            color: 'rgba(148, 163, 184, 0.4)',
            borderRight: '1px solid var(--color-border)',
            fontFamily: 'var(--font-code)',
            fontSize: 13,
            lineHeight: '1.7',
          }}
        >
          {line.lineNo ?? ''}
        </div>
        <div
          className="flex-1 whitespace-pre overflow-x-auto py-0 pl-4"
          style={{
            borderLeft,
            fontFamily: 'var(--font-code)',
            fontSize: 13,
            lineHeight: '1.7',
            color: 'var(--color-text)',
          }}
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <DiffHeader
        filePath={edit.file_path}
        stepLabel={`Step ${edit.step + 1}`}
        onAccept={handleAccept}
        onReject={handleReject}
        loading={loading}
      />

      <div className="flex flex-1 overflow-hidden" style={{ background: 'rgba(15, 17, 26, 0.95)' }}>
        {/* Left side - Old */}
        <div className="flex flex-col w-1/2" style={{ borderRight: '1px solid var(--color-border)' }}>
          <div
            className="shrink-0 px-4 py-1.5 text-[11px] font-medium uppercase tracking-wider"
            style={{
              color: 'var(--color-muted)',
              background: 'rgba(30, 33, 43, 0.3)',
              borderBottom: '1px solid var(--color-border)',
            }}
          >
            Old
          </div>
          <div
            ref={leftScrollRef}
            className="flex-1 overflow-auto"
            onScroll={handleLeftScroll}
          >
            {left.map((line, i) => renderLine(line, 'old', i))}
          </div>
        </div>

        {/* Right side - New */}
        <div className="flex flex-col w-1/2">
          <div
            className="shrink-0 px-4 py-1.5 text-[11px] font-medium uppercase tracking-wider"
            style={{
              color: 'var(--color-muted)',
              background: 'rgba(30, 33, 43, 0.3)',
              borderBottom: '1px solid var(--color-border)',
            }}
          >
            New
          </div>
          <div
            ref={rightScrollRef}
            className="flex-1 overflow-auto"
            onScroll={handleRightScroll}
          >
            {right.map((line, i) => renderLine(line, 'new', i))}
          </div>
        </div>
      </div>
    </div>
  )
}
