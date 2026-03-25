export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-2">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-2 h-2 rounded-full"
          style={{
            background: 'var(--color-primary)',
            animation: `bounce-dot 1.4s infinite ease-in-out both`,
            animationDelay: `${i * 0.16}s`,
          }}
        />
      ))}
    </div>
  )
}
