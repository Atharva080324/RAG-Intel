/**
 * CitationPanel – side panel shown when user clicks a [S1] chip.
 * Displays the source citation details.
 */
import type { Citation } from '@/api/client'
import { X, FileText } from 'lucide-react'

interface Props {
  citation: Citation | null
  onClose: () => void
}

export function CitationPanel({ citation, onClose }: Props) {
  if (!citation) return null

  return (
    <div
      className="citation-panel-container"
      style={{
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
        width: 'min(360px, 100vw)',
        maxWidth: '100vw',
        background: 'var(--surface)',
        borderLeft: '2px solid var(--black)',
        boxShadow: '-4px 0 0 var(--black)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 100,
        animation: 'fadeInUp 0.2s ease both',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '1rem', background: 'var(--black)', color: 'var(--yellow)',
        borderBottom: '2px solid var(--black)',
      }}>
        <span style={{ fontWeight: 800, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Source [{citation.source}]
        </span>
        <button
          id="btn-close-citation"
          onClick={onClose}
          style={{
            background: 'none', border: '2px solid var(--yellow)',
            borderRadius: 'var(--radius)', color: 'var(--yellow)',
            cursor: 'pointer', padding: '0.2rem',
            display: 'flex', alignItems: 'center',
          }}
        >
          <X size={14} />
        </button>
      </div>

      {/* Body */}
      <div style={{ padding: '1.25rem', flex: 1, overflow: 'auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Meta */}
          <div className="card" style={{ padding: '0.875rem', gap: '0.5rem', display: 'flex', flexDirection: 'column' }}>
            <div className="stat-row">
              <span className="stat-label">Page</span>
              <span className="stat-value">{citation.page_number}</span>
            </div>
            <div className="stat-row" style={{ borderBottom: 'none' }}>
              <span className="stat-label">Type</span>
              <span className="stat-value">{citation.chunk_type.toUpperCase()}</span>
            </div>
          </div>

          {/* Icon */}
          <div style={{ textAlign: 'center', color: 'var(--muted)', padding: '1.5rem 0' }}>
            <FileText size={40} style={{ opacity: 0.3, marginBottom: '0.5rem' }} />
            <p style={{ fontSize: '0.8rem' }}>
              Page {citation.page_number} of the uploaded document.
            </p>
            <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
              Chunk type: <strong>{citation.chunk_type}</strong>
            </p>
          </div>

          <div style={{
            background: 'var(--cream-2)', border: '2px solid var(--black)',
            borderRadius: 'var(--radius)', padding: '0.75rem',
            fontSize: '0.78rem', fontFamily: 'Space Mono, monospace',
            color: 'var(--muted)',
          }}>
            Full chunk text is not exposed via the API to protect document privacy.
            See the source document at page {citation.page_number}.
          </div>
        </div>
      </div>
    </div>
  )
}
