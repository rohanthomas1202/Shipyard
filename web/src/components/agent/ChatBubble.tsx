import type { ReactNode } from 'react'

interface ChatBubbleProps {
  role: 'user' | 'agent'
  children: ReactNode
}

export function ChatBubble({ role, children }: ChatBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      {!isUser && (
        <div className="flex items-center gap-2 mb-1">
          <div
            className="w-5 h-5 rounded flex items-center justify-center"
            style={{
              background: 'rgba(99, 102, 241, 0.2)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              color: 'var(--color-primary)',
            }}
          >
            <span className="material-symbols-outlined text-[12px]">smart_toy</span>
          </div>
          <span className="text-xs font-medium" style={{ color: 'var(--color-muted)' }}>Agent</span>
        </div>
      )}
      <div
        className={`p-3 max-w-[90%] text-sm ${
          isUser ? 'rounded-t-lg rounded-bl-lg rounded-br-sm' : 'rounded-t-lg rounded-br-lg rounded-bl-sm w-full'
        }`}
        style={{
          background: isUser ? 'rgba(255,255,255,0.05)' : 'rgba(99, 102, 241, 0.1)',
          border: `1px solid ${isUser ? 'var(--color-border)' : 'rgba(99, 102, 241, 0.2)'}`,
          color: 'var(--color-text)',
        }}
      >
        {children}
      </div>
    </div>
  )
}
