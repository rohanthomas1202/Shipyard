export function MeshBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden" style={{ background: '#0F111A' }}>
      <div
        className="absolute rounded-full opacity-50"
        style={{
          background: '#3B82F6',
          width: '600px',
          height: '600px',
          top: '-100px',
          left: '-100px',
          filter: 'blur(120px)',
          animation: 'float 20s infinite ease-in-out alternate',
        }}
      />
      <div
        className="absolute rounded-full opacity-50"
        style={{
          background: '#8B5CF6',
          width: '500px',
          height: '500px',
          bottom: '-50px',
          right: '-50px',
          filter: 'blur(120px)',
          animation: 'float 20s infinite ease-in-out alternate',
          animationDelay: '-5s',
        }}
      />
      <div
        className="absolute rounded-full opacity-30"
        style={{
          background: '#EC4899',
          width: '400px',
          height: '400px',
          top: '40%',
          left: '40%',
          filter: 'blur(120px)',
          animation: 'float 20s infinite ease-in-out alternate',
          animationDelay: '-10s',
        }}
      />
    </div>
  )
}
