/** AppShell – retro dark sidebar + cream content area */
import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { FileText, LogOut } from 'lucide-react'
import { useAuth } from '@/lib/AuthContext'

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ── Sidebar ── */}
      <nav style={{
        width: 220,
        background: 'var(--black)',
        borderRight: '2px solid var(--black)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.25rem 0.875rem',
        flexShrink: 0,
        gap: '0.35rem',
      }}>
        {/* Brand */}
        <div style={{ marginBottom: '1.75rem', paddingBottom: '1rem', borderBottom: '2px solid #ffffff20' }}>
          <div style={{
            fontWeight: 800, fontSize: '1rem',
            textTransform: 'uppercase', letterSpacing: '0.06em',
            color: 'var(--yellow)',
          }}>
            RAG<span style={{
              background: 'var(--yellow)', color: 'var(--black)',
              padding: '0 4px', marginLeft: 4,
              border: '2px solid var(--yellow)',
            }}>INTEL</span>
          </div>
          <div style={{ color: '#ffffff50', fontSize: '0.65rem', marginTop: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Document Intelligence
          </div>
        </div>

        <NavLink
          to="/documents"
          id="nav-documents"
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <FileText size={15} />
          Documents
        </NavLink>

        {/* Bottom */}
        <div style={{ marginTop: 'auto', borderTop: '2px solid #ffffff20', paddingTop: '0.875rem' }}>
          <button
            id="btn-logout"
            className="nav-item"
            onClick={() => { logout(); navigate('/') }}
            style={{ width: '100%', background: 'transparent', border: '2px solid transparent', cursor: 'pointer', textAlign: 'left' }}
          >
            <LogOut size={15} />
            Sign Out
          </button>
        </div>
      </nav>

      {/* ── Main ── */}
      <main style={{ flex: 1, overflow: 'auto', background: 'var(--cream)' }}>
        {children}
      </main>
    </div>
  )
}
