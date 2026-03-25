interface DiffLineProps {
  type: 'add' | 'remove' | 'context'
  oldLineNo?: number
  newLineNo?: number
  content: string
}

export function DiffLine({ type, oldLineNo, newLineNo, content }: DiffLineProps) {
  const bgColor = type === 'add'
    ? 'rgba(16, 185, 129, 0.15)'
    : type === 'remove'
    ? 'rgba(239, 68, 68, 0.15)'
    : 'transparent'

  const borderColor = type === 'add'
    ? 'rgba(16, 185, 129, 0.8)'
    : type === 'remove'
    ? 'rgba(239, 68, 68, 0.8)'
    : 'transparent'

  const lineNoColor = type === 'add'
    ? 'rgba(16, 185, 129, 0.8)'
    : type === 'remove'
    ? 'rgba(239, 68, 68, 0.7)'
    : 'rgba(148, 163, 184, 0.4)'

  return (
    <tr
      className="group hover:bg-white/[0.03]"
      style={{ background: bgColor }}
    >
      <td
        className="text-center select-none py-0.5 w-[50px]"
        style={{ color: lineNoColor, borderRight: '1px solid var(--color-border)' }}
      >
        {type !== 'add' ? oldLineNo : ''}
      </td>
      <td
        className="text-center select-none py-0.5 w-[50px]"
        style={{ color: lineNoColor, borderRight: '1px solid var(--color-border)' }}
      >
        {type !== 'remove' ? newLineNo : ''}
      </td>
      <td
        className="pl-4 py-0.5 whitespace-pre font-code text-[13px]"
        style={{
          color: type === 'remove' ? 'rgba(239, 68, 68, 0.9)' : 'var(--color-text)',
          borderLeft: type !== 'context' ? `3px solid ${borderColor}` : 'none',
          fontFamily: 'var(--font-code)',
        }}
      >
        {content}
      </td>
    </tr>
  )
}
