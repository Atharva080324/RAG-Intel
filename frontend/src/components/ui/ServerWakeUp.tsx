/** Server wake-up loading screen — retro spinner */
import { useEffect, useState } from 'react'

const MESSAGES = [
  'Waking up the Oracle ARM server…',
  'Loading the RAG pipeline…',
  'Connecting to pgvector…',
  'Almost ready…',
]

export function ServerWakeUp({ checking }: { checking: boolean }) {
  const [msgIdx, setMsgIdx] = useState(0)
  const [dots, setDots] = useState('')

  useEffect(() => {
    const m = setInterval(() => setMsgIdx(i => (i + 1) % MESSAGES.length), 2800)
    const d = setInterval(() => setDots(s => s.length >= 3 ? '' : s + '.'), 500)
    return () => { clearInterval(m); clearInterval(d) }
  }, [])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100vh', gap: '2rem',
      background: 'var(--cream)', padding: '2rem', textAlign: 'center',
    }}>
      {/* Retro spinner */}
      <div style={{ position: 'relative', width: 80, height: 80 }}>
        <div style={{
          position: 'absolute', inset: 0,
          border: '4px solid var(--black)',
          borderTopColor: 'var(--yellow)',
          borderRadius: '50%',
          animation: 'spin 0.9s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: 12,
          border: '4px solid var(--black)',
          borderBottomColor: 'var(--orange)',
          borderRadius: '50%',
          animation: 'spin 1.4s linear infinite reverse',
        }} />
      </div>

      {/* Title */}
      <div>
        <div style={{
          fontWeight: 800, fontSize: '2rem', textTransform: 'uppercase',
          letterSpacing: '-0.01em', marginBottom: '0.5rem',
        }}>
          RAG<span style={{
            background: 'var(--yellow)', border: '2px solid var(--black)',
            padding: '0 6px', marginLeft: 6,
          }}>INTEL</span>
        </div>
        <p style={{
          fontFamily: 'Space Mono, monospace', fontSize: '0.82rem',
          color: 'var(--muted)', fontWeight: 700, textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}>
          {checking ? 'Connecting' : MESSAGES[msgIdx]}{dots}
        </p>
      </div>

      {/* Info card */}
      <div className="card" style={{ maxWidth: 400, fontSize: '0.875rem', color: 'var(--muted)', textAlign: 'left' }}>
        <div className="label-strip" style={{ marginBottom: '0.75rem' }}>ℹ️ Cold start</div>
        <p>
          The API runs on an <strong style={{ color: 'var(--black)' }}>Oracle Cloud Always Free ARM</strong> instance.
          First load takes <strong style={{ color: 'var(--black)' }}>10–20 seconds</strong> while the container warms up.
        </p>
        <p style={{ marginTop: '0.5rem' }}>Auto-retrying — no refresh needed.</p>
      </div>

      {/* Dots */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 10, height: 10,
            background: i % 2 === 0 ? 'var(--yellow)' : 'var(--black)',
            border: '2px solid var(--black)',
            borderRadius: 2,
            animation: `pulse 1.4s ease ${i * 0.25}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}
