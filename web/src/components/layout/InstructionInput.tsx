import { useState, useRef, useCallback } from 'react'

interface InstructionInputProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

export function InstructionInput({ onSubmit, disabled }: InstructionInputProps) {
  const [text, setText] = useState('')
  const [expanded, setExpanded] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = useCallback(() => {
    if (!text.trim() || disabled) return
    onSubmit(text.trim())
    setText('')
    setExpanded(false)
    textareaRef.current?.blur()
  }, [text, disabled, onSubmit])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    }
  }, [handleSubmit])

  return (
    <div className="flex-1 flex items-center gap-2">
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={() => setExpanded(true)}
        onBlur={() => { if (!text) setExpanded(false) }}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={expanded
          ? 'Describe what you want the agent to do. Be specific about files, functions, and the expected outcome.'
          : 'Describe the code change you want...'
        }
        rows={expanded ? 3 : 1}
        className="flex-1 resize-none rounded-lg px-3 py-2 text-sm focus:outline-none"
        style={{
          background: 'rgba(30, 33, 43, 0.4)',
          border: `1px solid ${expanded ? 'var(--color-primary)' : 'var(--color-border)'}`,
          color: 'var(--color-text)',
          height: expanded ? 'auto' : '36px',
          maxHeight: '120px',
          opacity: disabled ? 0.5 : 1,
          fontFamily: 'var(--font-ui)',
        }}
      />
      {expanded && (
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || disabled}
          className="px-3 py-2 rounded-lg text-sm font-semibold text-white flex-shrink-0"
          style={{
            background: !text.trim() || disabled ? 'rgba(99, 102, 241, 0.3)' : 'var(--color-primary)',
          }}
        >
          Run instruction
        </button>
      )}
    </div>
  )
}
