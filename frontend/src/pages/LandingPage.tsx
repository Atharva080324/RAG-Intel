/** Landing page – retro style with "Try Demo" CTA */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/lib/AuthContext'
import { authApi } from '@/api/client'
import type { ApiError } from '@/api/client'
import { Zap, FileText, Search, Brain, Table, ChevronRight } from 'lucide-react'

const FEATURES = [
  { icon: <FileText size={20} />, title: 'PDF & Text Upload', desc: 'Drag-drop PDFs, TXTs, Markdown. Content-hash dedup.' },
  { icon: <Search size={20} />, title: 'Hybrid Retrieval', desc: 'Vector + full-text fused with RRF. No hallucination.' },
  { icon: <Brain size={20} />, title: 'Corrective RAG', desc: 'LangGraph workflow rewrites weak queries automatically.' },
  { icon: <Table size={20} />, title: 'Table Analytics', desc: 'Sum / avg / min / max over extracted Markdown tables.' },
  { icon: <Zap size={20} />, title: 'Streaming Answers', desc: 'SSE token stream direct to browser, no buffering.' },
  { icon: <Search size={20} />, title: 'Retrieval Inspector', desc: 'See every retrieval decision — vector hits, reranks, retries.' },
]

const TICKER_ITEMS = [
  '★ HYBRID RETRIEVAL', '★ CORRECTIVE RAG', '★ STREAMING SSE',
  '★ PGVECTOR', '★ CROSS-ENCODER RERANKING', '★ TABLE ANALYTICS',
  '★ LANGGRAPH', '★ GROQ LLM', '★ ORACLE CLOUD ARM',
]

interface LandingPageProps {
  reachable?: boolean
  warmedUp?: boolean
}

export function LandingPage({ reachable = true, warmedUp = true }: LandingPageProps) {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'login' | 'signup'>('login')

  const handleDemo = async () => {
    setDemoLoading(true)
    setError('')
    try {
      const t = await authApi.demo()
      login(t.access_token)
      navigate('/documents')
    } catch (e) {
      setError('Demo mode is not enabled on this server.')
    } finally {
      setDemoLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      if (mode === 'signup') {
        await authApi.signup(email, password)
      }
      const t = await authApi.login(email, password)
      login(t.access_token)
      navigate('/documents')
    } catch (e) {
      const err = e as ApiError
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--cream)' }}>

      {/* ── Optional Warm-Up Status Banner ── */}
      {(!reachable || !warmedUp) && (
        <div style={{
          background: 'var(--yellow)',
          borderBottom: '2px solid var(--black)',
          padding: '0.45rem 1rem',
          textAlign: 'center',
          fontSize: '0.78rem',
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.5rem',
        }}>
          <span>⚡ Backend models warming up on Oracle ARM (~2s)... Demo login is ready anytime.</span>
        </div>
      )}

      {/* ── Nav ── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '1rem 2rem', borderBottom: '2px solid var(--black)',
        background: 'var(--surface)',
      }}>
        <div style={{ fontWeight: 800, fontSize: '1.1rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          RAG<span style={{ background: 'var(--yellow)', padding: '0 4px', border: '2px solid var(--black)', marginLeft: 4 }}>INTEL</span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <a href={authApi.googleLoginUrl()} className="btn btn-ghost" style={{ fontSize: '0.8rem' }}>
            Google Login
          </a>
          <button className="btn btn-dark" id="btn-hero-demo" onClick={handleDemo} disabled={demoLoading}>
            {demoLoading ? 'Loading…' : 'Try Demo →'}
          </button>
        </div>
      </header>

      {/* ── Ticker ── */}
      <div className="marquee-wrapper">
        <div className="marquee-track">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
            <span className="marquee-item" key={i}>{item}</span>
          ))}
        </div>
      </div>

      {/* ── Hero ── */}
      <section className="hero" style={{ padding: '5rem 2rem' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <span className="label-strip">Open Source</span>
            <span className="label-strip" style={{ background: 'var(--black)', color: 'var(--yellow)' }}>Oracle Cloud ARM</span>
            <span className="label-strip" style={{ background: 'var(--orange)', color: 'white' }}>Live Demo</span>
          </div>

          <h1 className="hero-title" style={{ marginBottom: '1.5rem' }}>
            Document<br />
            <span className="hero-accent">Intelligence</span><br />
            At Scale
          </h1>

          <p style={{ fontSize: '1.1rem', color: 'var(--muted)', maxWidth: 560, marginBottom: '2rem', fontWeight: 500 }}>
            Upload PDFs. Ask questions. Get grounded answers with source citations —
            powered by hybrid retrieval, corrective RAG, and table analytics.
          </p>

          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              id="btn-try-demo"
              className="btn btn-primary btn-lg"
              onClick={handleDemo}
              disabled={demoLoading}
            >
              <Zap size={18} />
              {demoLoading ? 'Waking up…' : 'Try Demo — No Login'}
            </button>
            <a
              href="https://github.com/Atharva080324/rag-document-intelligence"
              target="_blank"
              rel="noreferrer"
              className="btn btn-ghost btn-lg"
            >
              View on GitHub <ChevronRight size={16} />
            </a>
          </div>

          {error && (
            <div style={{
              marginTop: '1rem', padding: '0.75rem 1rem',
              background: '#fdecea', border: '2px solid var(--red)',
              borderRadius: 'var(--radius)', color: 'var(--red)', fontWeight: 600,
              fontSize: '0.875rem',
            }}>
              {error}
            </div>
          )}
        </div>
      </section>

      {/* ── Feature grid ── */}
      <section style={{ padding: '3rem 2rem', borderBottom: '2px solid var(--black)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '1.5rem' }}>What's inside</h2>
          <div className="feature-grid">
            {FEATURES.map(f => (
              <div className="feature-tile" key={f.title}>
                <div className="feature-icon">{f.icon}</div>
                <h3>{f.title}</h3>
                <p style={{ color: 'var(--muted)', fontSize: '0.82rem', lineHeight: 1.5 }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Login / Signup form ── */}
      <section style={{ padding: '3rem 2rem' }}>
        <div style={{ maxWidth: 420, margin: '0 auto' }}>
          <div className="card">
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
              {(['login', 'signup'] as const).map(m => (
                <button
                  key={m}
                  className={`btn ${mode === m ? 'btn-dark' : 'btn-ghost'}`}
                  style={{ flex: 1 }}
                  onClick={() => setMode(m)}
                  id={`btn-mode-${m}`}
                >
                  {m === 'login' ? 'Sign In' : 'Sign Up'}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.35rem' }}>
                  Email
                </label>
                <input
                  id="input-email"
                  className="input"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.35rem' }}>
                  Password
                </label>
                <input
                  id="input-password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </div>

              {error && (
                <div style={{ fontSize: '0.82rem', color: 'var(--red)', fontWeight: 600 }}>{error}</div>
              )}

              <button id="btn-submit-auth" className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: '0.25rem' }}>
                {loading ? 'Loading…' : mode === 'login' ? 'Sign In →' : 'Create Account →'}
              </button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: '1rem 0' }}>
              <hr className="divider" style={{ flex: 1, margin: 0 }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 600 }}>OR</span>
              <hr className="divider" style={{ flex: 1, margin: 0 }} />
            </div>

            <a href={authApi.googleLoginUrl()} className="btn btn-ghost w-full" id="btn-google-login" style={{ justifyContent: 'center' }}>
              <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="var(--orange)" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="var(--yellow-2)" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="var(--red)" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              Continue with Google
            </a>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="site-footer">
        <p>Built with <strong>FastAPI · LangGraph · pgvector · React</strong> · Deployed on <strong>Oracle Cloud Always Free ARM</strong></p>
      </footer>
    </div>
  )
}
