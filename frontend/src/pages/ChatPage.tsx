/**
 * ChatPage – streaming chat with [S1]-style citations, retrieval inspector,
 * and table analytics display. Full retro theme.
 */
import { useState, useRef, useEffect, lazy, Suspense } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAuth } from '@/lib/AuthContext'
import { documentsApi } from '@/api/client'
import type { Citation } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import { Send, ArrowLeft, MessageSquare } from 'lucide-react'

// Code-split inspector and citation drawer
const RetrievalInspector = lazy(() => import('@/components/inspector/RetrievalInspector').then(m => ({ default: m.RetrievalInspector })))
const CitationPanel = lazy(() => import('@/components/chat/CitationPanel').then(m => ({ default: m.CitationPanel })))


const STARTERS = [
  'How does Reciprocal Rank Fusion (RRF) combine dense and sparse retrieval scores?',
  'What was the total revenue across all four quarters of FY2025?',
  'What was the average quarterly cloud hosting expense in FY2025?',
  'Which quarter achieved the maximum net income, and what was the value?',
  'What chunking strategy and overlap size are used during ingestion?',
]

export function ChatPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const { token } = useAuth()
  const navigate = useNavigate()
  const docId = Number(documentId)

  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string; citations?: Citation[] }>>([])
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { status, tokens, citations, workflow, error, start, reset } = useSSE()

  const { data: doc } = useQuery({
    queryKey: ['document', docId],
    queryFn: () => documentsApi.get(token!, docId),
    enabled: !!token && !!docId,
  })

  // Append streamed answer to history when done
  useEffect(() => {
    if (status === 'done' && tokens.length > 0) {
      setHistory(h => [...h, {
        role: 'assistant',
        content: tokens.join(''),
        citations,
      }])
      reset()
    }
  }, [status, tokens, citations, reset])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, tokens, status])

  const submit = (q: string) => {
    if (!q.trim() || status === 'streaming' || status === 'connecting') return
    reset()
    setHistory(h => [...h, { role: 'user', content: q }])
    setQuestion('')
    start(token!, docId, q)
  }

  const streamText = tokens.join('')
  const isStreaming = status === 'streaming' || status === 'connecting'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', position: 'relative' }}>
      {/* ── Main chat column ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header */}
        <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            className="btn btn-ghost"
            onClick={() => navigate('/documents')}
            id="btn-back"
            style={{ color: 'var(--yellow)', border: '2px solid var(--yellow)', padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
          >
            <ArrowLeft size={14} /> Back
          </button>
          <div>
            <h1 style={{ fontSize: '1rem', color: 'var(--yellow)' }}>
              {doc?.filename ?? `Document #${docId}`}
            </h1>
            <p style={{ color: 'var(--cream-3)', fontSize: '0.7rem', fontFamily: 'Space Mono, monospace' }}>
              Streaming RAG · pgvector + FTS · Cross-encoder reranking
            </p>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }}>
          {history.length === 0 && status === 'idle' && (
            <EmptyState onSelect={submit} />
          )}

          {history.map((msg, i) => (
            <div key={i} style={{ marginBottom: '1.25rem' }}>
              {msg.role === 'user' ? (
                <UserBubble text={msg.content} />
              ) : (
                <AssistantBubble
                  text={msg.content}
                  citations={msg.citations ?? []}
                  onCitation={setActiveCitation}
                />
              )}
            </div>
          ))}

          {/* Live stream */}
          {(status === 'connecting' || status === 'streaming') && (
            <div style={{ marginBottom: '1.25rem' }}>
              <AssistantBubble
                text={streamText}
                citations={[]}
                onCitation={setActiveCitation}
                streaming
              />
            </div>
          )}

          {/* Retrieval inspector */}
          {workflow && (
            <div style={{ marginBottom: '1.25rem' }}>
              <Suspense fallback={<div className="skeleton" style={{ height: 100 }} />}>
                <RetrievalInspector workflow={workflow} />
              </Suspense>
            </div>
          )}

          {error && (
            <div style={{
              padding: '0.75rem 1rem', background: '#fdecea',
              border: '2px solid var(--red)', borderRadius: 'var(--radius)',
              color: 'var(--red)', fontWeight: 600, fontSize: '0.875rem', marginBottom: '1rem',
            }}>
              ✗ {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{
          padding: '1rem 1.5rem', borderTop: '2px solid var(--black)',
          background: 'var(--surface)', display: 'flex', gap: '0.75rem',
        }}>
          <input
            id="input-question"
            className="input"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && submit(question)}
            placeholder="Ask anything about the document…"
            disabled={isStreaming}
          />
          <button
            id="btn-send"
            className="btn btn-dark"
            onClick={() => submit(question)}
            disabled={isStreaming || !question.trim()}
            style={{ flexShrink: 0 }}
          >
            {isStreaming ? (
              <span className="animate-spin" style={{ display: 'inline-block' }}>⟳</span>
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>
      </div>

      {/* ── Citation side panel ── */}
      <Suspense fallback={null}>
        <CitationPanel citation={activeCitation} onClose={() => setActiveCitation(null)} />
      </Suspense>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function UserBubble({ text }: { text: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div className="chat-bubble chat-bubble-user">
        <p style={{ fontWeight: 600 }}>{text}</p>
      </div>
    </div>
  )
}

function AssistantBubble({
  text, citations, onCitation, streaming,
}: {
  text: string
  citations: Citation[]
  onCitation: (c: Citation) => void
  streaming?: boolean
}) {
  // Replace [S1] markers with clickable chips
  const rendered = text.replace(/\[S(\d+)\]/g, (_, n) => `[[CITE:${n}]]`)

  return (
    <div className="chat-bubble chat-bubble-assistant">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <div style={{
          width: 24, height: 24, background: 'var(--yellow)', border: '2px solid var(--black)',
          borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.65rem', fontWeight: 800,
        }}>AI</div>
        <span style={{ fontSize: '0.72rem', color: 'var(--muted)', fontFamily: 'Space Mono, monospace', textTransform: 'uppercase' }}>
          RAG Intel
        </span>
        {streaming && <span className="badge badge-running" style={{ fontSize: '0.65rem' }}>streaming</span>}
      </div>

      <div className={`prose ${streaming && !text ? 'stream-cursor' : ''}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: ({ children }) => <p>{renderCitations(children, citations, onCitation)}</p>,
            text: ({ children }) => <>{renderCitations(children, citations, onCitation)}</>,
          }}
        >
          {rendered}
        </ReactMarkdown>
        {streaming && text && <span className="stream-cursor" />}
      </div>

      {citations.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.75rem', borderTop: '1px dashed var(--cream-3)', paddingTop: '0.5rem' }}>
          {citations.map(c => (
            <button
              key={c.source}
              className="citation-chip"
              id={`citation-${c.source}`}
              onClick={() => onCitation(c)}
              title={`Page ${c.page_number} · ${c.chunk_type}`}
            >
              {c.source} · p.{c.page_number}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function renderCitations(
  children: React.ReactNode,
  citations: Citation[],
  onCitation: (c: Citation) => void,
): React.ReactNode {
  if (typeof children !== 'string') return children
  const parts = children.split(/(\[\[CITE:\d+\]\])/g)
  return parts.map((part, i) => {
    const match = part.match(/\[\[CITE:(\d+)\]\]/)
    if (match) {
      const n = Number(match[1])
      const cit = citations.find(c => c.source === `S${n}`)
      return (
        <button
          key={i}
          className="citation-chip"
          id={`inline-citation-S${n}`}
          onClick={() => cit && onCitation(cit)}
        >
          S{n}
        </button>
      )
    }
    return part
  })
}

function EmptyState({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div style={{ textAlign: 'center', paddingTop: '3rem' }}>
      <div style={{
        width: 60, height: 60, background: 'var(--yellow)', border: '2px solid var(--black)',
        borderRadius: 'var(--radius-lg)', margin: '0 auto 1rem',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: 'var(--shadow)',
      }}>
        <MessageSquare size={28} />
      </div>
      <h2 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Start a conversation</h2>
      <p style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
        Ask anything about your document
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center', maxWidth: 520, margin: '0 auto' }}>
        {STARTERS.map(q => (
          <button
            key={q}
            className="btn btn-ghost"
            style={{ fontSize: '0.8rem' }}
            onClick={() => onSelect(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
