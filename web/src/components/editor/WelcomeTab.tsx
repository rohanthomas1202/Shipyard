export function WelcomeTab() {
  return (
    <div
      className="flex flex-col items-center justify-center h-full"
      style={{ maxWidth: 360, margin: '0 auto' }}
    >
      <span
        className="material-symbols-outlined"
        style={{
          fontSize: 48,
          color: 'var(--color-primary)',
          opacity: 0.6,
          marginBottom: 16,
        }}
      >
        code
      </span>
      <h2
        style={{
          fontSize: 20,
          fontWeight: 600,
          color: 'var(--color-text)',
          fontFamily: 'var(--font-ui)',
          marginBottom: 8,
        }}
      >
        No files open
      </h2>
      <p
        style={{
          fontSize: 14,
          fontWeight: 400,
          color: 'var(--color-muted)',
          fontFamily: 'var(--font-ui)',
          lineHeight: 1.5,
          textAlign: 'center',
        }}
      >
        Select a file from the explorer to view its contents, or wait for the agent to propose edits.
      </p>
    </div>
  )
}
