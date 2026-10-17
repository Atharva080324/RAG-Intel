/** Retrieval Inspector panel – collapsible, retro style */
import { useState } from 'react'
import type { WorkflowEvent } from '@/api/client'
import { ChevronDown, ChevronUp } from 'lucide-react'

export function RetrievalInspector({ workflow }: { workflow: WorkflowEvent }) {
  const [open, setOpen] = useState(true)
  const r = workflow.retrieval

  return (
    <div className="inspector animate-fade-in-up">
      <div className="inspector-header" onClick={() => setOpen(o => !o)} id="inspector-toggle">
        <span>🔬 Retrieval Inspector</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: '0.7rem', color: 'var(--yellow)' }}>
            {workflow.intent.toUpperCase()} QUERY
          </span>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>

      {open && (
        <div className="inspector-body">
          {/* Workflow summary */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <MetricCard label="Query type" value={workflow.intent.toUpperCase()} yellow />
            <MetricCard label="Rewrite attempts" value={String(workflow.rewrite_attempts)} />
            <MetricCard
              label="Relevance score"
              value={`${(workflow.relevance_score * 100).toFixed(1)}%`}
              yellow={workflow.relevance_score >= workflow.minimum_grounding_score}
              danger={workflow.relevance_score < workflow.minimum_grounding_score}
            />
            <MetricCard
              label="Answer mode"
              value={workflow.answer_mode === 'grounded_answer' ? 'GROUNDED ✓' : 'INSUFFICIENT'}
              yellow={workflow.answer_mode === 'grounded_answer'}
              danger={workflow.answer_mode !== 'grounded_answer'}
            />
          </div>

          {/* Retrieval stats */}
          <div style={{ borderTop: '2px dashed var(--cream-3)', paddingTop: '0.75rem' }}>
            <div className="label-strip" style={{ marginBottom: '0.5rem', fontSize: '0.65rem' }}>Retrieval pipeline</div>
            <div className="stat-row">
              <span className="stat-label">Vector (semantic) hits</span>
              <span className="stat-value">{r.semantic_candidates}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Lexical (FTS) hits</span>
              <span className="stat-value">{r.lexical_candidates}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">After RRF fusion</span>
              <span className="stat-value">{r.fused_candidates}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">After reranking</span>
              <span className="stat-value">{r.returned_chunks}</span>
            </div>
            <div className="stat-row" style={{ borderBottom: 'none' }}>
              <span className="stat-label">Retrieval latency</span>
              <span className="stat-value">{r.retrieval_latency_ms} ms</span>
            </div>
          </div>

          {/* Rewritten queries */}
          {r.rewritten_queries.length > 0 && (
            <div style={{ borderTop: '2px dashed var(--cream-3)', paddingTop: '0.75rem' }}>
              <div className="label-strip" style={{ marginBottom: '0.5rem', fontSize: '0.65rem' }}>
                ↻ Rewritten queries ({r.rewritten_queries.length})
              </div>
              {r.rewritten_queries.map((q, i) => (
                <div key={i} style={{
                  background: 'var(--surface)', border: '2px solid var(--black)',
                  borderRadius: 'var(--radius)', padding: '0.4rem 0.6rem',
                  fontSize: '0.78rem', fontFamily: 'Space Mono, monospace',
                  marginBottom: '0.35rem', color: 'var(--muted)',
                }}>
                  <span style={{ fontWeight: 700, color: 'var(--black)' }}>#{i + 1}</span> {q}
                </div>
              ))}
            </div>
          )}

          {/* Min score info */}
          <div style={{
            background: 'var(--cream-3)', border: '2px solid var(--black)',
            borderRadius: 'var(--radius)', padding: '0.5rem 0.75rem',
            fontSize: '0.72rem', fontFamily: 'Space Mono, monospace',
            color: 'var(--muted)',
          }}>
            Min grounding threshold: {workflow.minimum_grounding_score}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({
  label, value, yellow, danger,
}: { label: string; value: string; yellow?: boolean; danger?: boolean }) {
  return (
    <div style={{
      background: 'var(--surface)', border: '2px solid var(--black)',
      borderRadius: 'var(--radius)', padding: '0.6rem 0.75rem',
      boxShadow: '2px 2px 0 var(--black)',
    }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.2rem' }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'Space Mono, monospace', fontWeight: 700, fontSize: '0.9rem',
        color: danger ? 'var(--red)' : yellow ? 'var(--brown)' : 'var(--black)',
      }}>
        {value}
      </div>
    </div>
  )
}
