/** AppShell – retro dark sidebar + cream content area, fully mobile responsive */
import { useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { FileText, LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '@/lib/AuthContext'

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleSignOut = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="app-shell-root">
      {/* ── Mobile topbar (< 768px) ── */}
      <header className="mobile-topbar">
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileMenuOpen(o => !o)}
          aria-label="Toggle navigation menu"
          id="btn-mobile-menu"
        >
          {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
        </button>

        <div className="mobile-brand">
          RAG<span>INTEL</span>
        </div>

        <button
          className="mobile-logout-btn"
          onClick={handleSignOut}
          title="Sign Out"
          aria-label="Sign Out"
          id="btn-mobile-logout"
        >
          <LogOut size={16} />
        </button>
      </header>

      {/* ── Mobile Drawer Backdrop & Menu ── */}
      {mobileMenuOpen && (
        <div className="mobile-drawer-backdrop" onClick={() => setMobileMenuOpen(false)}>
          <div className="mobile-drawer" onClick={e => e.stopPropagation()}>
            <div className="mobile-drawer-header">
              <div className="mobile-brand">
                RAG<span>INTEL</span>
              </div>
              <button
                className="btn btn-ghost"
                style={{ padding: '0.3rem 0.5rem', color: 'var(--yellow)', borderColor: 'var(--yellow)' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="mobile-drawer-body">
              <NavLink
                to="/documents"
                id="nav-mobile-documents"
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={() => setMobileMenuOpen(false)}
              >
                <FileText size={16} />
                Documents
              </NavLink>
              <button
                id="btn-drawer-logout"
                className="nav-item"
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: '2px solid transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  marginTop: '1rem',
                  color: 'var(--yellow)',
                }}
                onClick={() => {
                  setMobileMenuOpen(false)
                  handleSignOut()
                }}
              >
                <LogOut size={16} />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Desktop Sidebar ── */}
      <nav className="desktop-sidebar">
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
            onClick={handleSignOut}
            style={{ width: '100%', background: 'transparent', border: '2px solid transparent', cursor: 'pointer', textAlign: 'left' }}
          >
            <LogOut size={15} />
            Sign Out
          </button>
        </div>
      </nav>

      {/* ── Main Content Area ── */}
      <main className="app-main-content">
        {children}
      </main>
    </div>
  )
}

