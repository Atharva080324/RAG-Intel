/** Documents page – upload + list with retro card design */
import { useRef, useState, DragEvent } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/lib/AuthContext'
import { documentsApi, jobsApi } from '@/api/client'
import type { DocumentRead, JobAccepted } from '@/api/client'
import { FileText, Upload, MessageSquare, AlertTriangle, CheckCircle, Clock, Loader } from 'lucide-react'

const STARTER_QUESTIONS = [
  'Summarise the key findings in this document',
  'What tables are present? Show the totals.',
  'What are the main conclusions?',
  'List all numeric data mentioned.',
]

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: 'badge-success',
    queued: 'badge-warn',
    running: 'badge-running',
    failed: 'badge-danger',
  }
  const icons: Record<string, React.ReactNode> = {
    completed: <CheckCircle size={11} />,
    queued: <Clock size={11} />,
    running: <Loader size={11} className="animate-spin" />,
    failed: <AlertTriangle size={11} />,
  }
  return (
    <span className={`badge ${map[status] ?? 'badge-info'}`}>
      {icons[status]}
      {status}
    </span>
  )
}

function JobTracker({ job, token }: { job: JobAccepted; token: string }) {
  const { data } = useQuery({
    queryKey: ['job', job.job_id],
    queryFn: () => jobsApi.get(token, job.job_id),
    refetchInterval: (query) => (query.state.data?.status === 'completed' || query.state.data?.status === 'failed' ? false : 2000),
  })
  const st = data?.status ?? 'queued'
  const prog = data?.progress ?? 0
  return (
    <div style={{ marginTop: '0.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.25rem', fontFamily: 'Space Mono, monospace' }}>
        <span style={{ color: 'var(--muted)' }}>Ingestion</span>
        <StatusBadge status={st} />
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${prog}%` }} />
      </div>
      {st === 'failed' && data?.error_message && (
        <p style={{ fontSize: '0.75rem', color: 'var(--red)', marginTop: '0.25rem' }}>
          ✗ {data.error_message}
        </p>
      )}
    </div>
  )
}

export function DocumentsPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [recentJobs, setRecentJobs] = useState<JobAccepted[]>([])
  const [uploadError, setUploadError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list(token!, 0, 30),
    enabled: !!token,
  })

  const upload = useMutation({
    mutationFn: (file: File) => documentsApi.upload(token!, file),
    onSuccess: job => {
      setRecentJobs(j => [job, ...j])
      setUploadError('')
      void qc.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (e: Error) => setUploadError(e.message),
  })

  const handleFiles = (files: FileList | null) => {
    if (!files) return
    Array.from(files).forEach(f => upload.mutate(f))
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <h1 style={{ fontSize: '1.25rem' }}>Documents</h1>
        <p style={{ color: 'var(--cream-3)', fontSize: '0.8rem', marginTop: '0.2rem', fontFamily: 'Space Mono, monospace' }}>
          Upload PDFs, TXTs, and Markdown files
        </p>
      </div>

      <div className="content-area">
        {/* ── Upload zone ── */}
        <div
          className={`drop-zone ${dragging ? 'drag-over' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          id="drop-zone"
          style={{ marginBottom: '1.5rem', cursor: 'pointer' }}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md"
            style={{ display: 'none' }}
            onChange={e => handleFiles(e.target.files)}
            id="input-file-upload"
          />
          <div style={{ marginBottom: '0.75rem' }}>
            <Upload size={36} strokeWidth={2.5} color="var(--black)" />
          </div>
          <p style={{ fontWeight: 800, fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.25rem' }}>
            {dragging ? 'Drop to upload' : 'Drag & Drop files here'}
          </p>
          <p style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>PDF, TXT, MD — max 10 MB each</p>
          <button className="btn btn-primary" style={{ marginTop: '1rem', pointerEvents: 'none' }}>
            <Upload size={14} /> Choose Files
          </button>
        </div>

        {uploadError && (
          <div style={{
            padding: '0.75rem 1rem', background: '#fdecea',
            border: '2px solid var(--red)', borderRadius: 'var(--radius)',
            color: 'var(--red)', fontWeight: 600, fontSize: '0.875rem', marginBottom: '1rem',
          }}>
            ✗ {uploadError}
          </div>
        )}

        {/* ── Recent uploads ── */}
        {recentJobs.length > 0 && (
          <div style={{ marginBottom: '1.5rem' }}>
            <div className="label-strip" style={{ marginBottom: '0.75rem' }}>⏳ Processing</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {recentJobs.map(j => (
                <div className="card" key={j.job_id} style={{ padding: '1rem' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>Doc #{j.document_id}</div>
                  <JobTracker job={j} token={token!} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Starter questions ── */}
        <div className="card" style={{ marginBottom: '1.5rem', background: 'var(--cream-2)' }}>
          <div className="label-strip" style={{ marginBottom: '0.75rem' }}>💡 Starter Questions</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.5rem' }}>
            {STARTER_QUESTIONS.map(q => (
              <div key={q} style={{
                background: 'var(--surface)', border: '2px solid var(--black)',
                borderRadius: 'var(--radius)', padding: '0.6rem 0.75rem',
                fontSize: '0.8rem', fontWeight: 500, color: 'var(--muted)',
                boxShadow: '2px 2px 0 var(--black)',
              }}>
                "{q}"
              </div>
            ))}
          </div>
        </div>

        {/* ── Document list ── */}
        <div>
          <div className="label-strip" style={{ marginBottom: '0.875rem' }}>📄 Your Documents</div>

          {isLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {[1, 2, 3].map(i => (
                <div key={i} className="skeleton" style={{ height: 72 }} />
              ))}
            </div>
          )}

          {!isLoading && (!data?.items.length) && (
            <div style={{
              textAlign: 'center', padding: '3rem', border: '2px dashed var(--black)',
              borderRadius: 'var(--radius-lg)', color: 'var(--muted)',
            }}>
              <FileText size={40} style={{ marginBottom: '0.75rem', opacity: 0.4 }} />
              <p style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>No documents yet</p>
              <p style={{ fontSize: '0.82rem', marginTop: '0.25rem' }}>Upload a PDF to get started</p>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {data?.items.map((doc, i) => (
              <DocCard key={doc.id} doc={doc} delay={i * 0.05}
                onChat={() => navigate(`/chat/${doc.id}`)} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function DocCard({ doc, delay, onChat }: { doc: DocumentRead; delay: number; onChat: () => void }) {
  return (
    <div
      className="doc-card"
      style={{ animationDelay: `${delay}s` }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', flex: 1, minWidth: 0 }}>
        <div style={{
          width: 40, height: 40, background: 'var(--cream-2)',
          border: '2px solid var(--black)', borderRadius: 'var(--radius)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, boxShadow: '2px 2px 0 var(--black)',
        }}>
          <FileText size={18} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {doc.filename}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
            <StatusBadge status={doc.status} />
            <span style={{ fontSize: '0.72rem', color: 'var(--muted)', fontFamily: 'Space Mono, monospace' }}>
              {new Date(doc.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>

      {doc.status === 'completed' && (
        <button
          className="btn btn-primary"
          onClick={onChat}
          id={`btn-chat-${doc.id}`}
          style={{ flexShrink: 0, fontSize: '0.8rem', padding: '0.5rem 1rem' }}
        >
          <MessageSquare size={14} /> Chat
        </button>
      )}
    </div>
  )
}
