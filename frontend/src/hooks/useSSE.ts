/**
 * useSSE – React hook for consuming a POST-based Server-Sent Events stream.
 *
 * FastAPI's /questions/stream uses POST with a JSON body, which native
 * EventSource doesn't support. We use fetch + ReadableStream instead, parsing
 * each `event: X\ndata: Y\n\n` frame manually.
 *
 * Usage:
 *   const { start, status, tokens, citations, workflow, error } = useSSE()
 *   start(token, documentId, question)
 */
import { useCallback, useRef, useState } from 'react'
import type { Citation, WorkflowEvent } from '@/api/client'
import { BASE } from '@/api/client'

export type SSEStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error'

export interface SSEState {
  status: SSEStatus
  tokens: string[]           // raw token strings, joined for the full answer
  citations: Citation[]
  workflow: WorkflowEvent | null
  error: string | null
}

interface UseSSE extends SSEState {
  start: (token: string, documentId: number, question: string) => void
  reset: () => void
}

const INITIAL: SSEState = {
  status: 'idle',
  tokens: [],
  citations: [],
  workflow: null,
  error: null,
}

export function useSSE(): UseSSE {
  const [state, setState] = useState<SSEState>(INITIAL)
  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState(INITIAL)
  }, [])

  const start = useCallback(
    async (bearerToken: string, documentId: number, question: string) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setState({ ...INITIAL, status: 'connecting' })

      try {
        const res = await fetch(`${BASE}/questions/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${bearerToken}`,
            // Tell Caddy/Nginx not to buffer this response.
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({ document_id: documentId, question }),
          signal: controller.signal,
        })

        if (!res.ok) {
          let detail = `HTTP ${res.status}`
          try { const j = await res.json(); detail = j.detail ?? detail } catch { /* */ }
          setState(s => ({ ...s, status: 'error', error: detail }))
          return
        }

        setState(s => ({ ...s, status: 'streaming' }))

        const reader = res.body?.getReader()
        if (!reader) {
          setState(s => ({ ...s, status: 'error', error: 'No response body' }))
          return
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          // SSE frames end with \n\n
          const frames = buffer.split('\n\n')
          buffer = frames.pop() ?? ''
          for (const frame of frames) {
            parseFrame(frame, setState)
          }
        }

        setState(s => ({ ...s, status: s.status === 'error' ? 'error' : 'done' }))
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setState(s => ({
          ...s,
          status: 'error',
          error: err instanceof Error ? err.message : 'Unknown error',
        }))
      }
    },
    [],
  )

  return { ...state, start, reset }
}

// ── Frame parser ─────────────────────────────────────────────────────────────

function parseFrame(
  frame: string,
  setState: React.Dispatch<React.SetStateAction<SSEState>>,
): void {
  let eventType = ''
  let dataLine = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) eventType = line.slice(7).trim()
    if (line.startsWith('data: ')) dataLine = line.slice(6).trim()
  }
  if (!eventType || !dataLine) return
  try {
    const payload = JSON.parse(dataLine)
    switch (eventType) {
      case 'workflow':
        setState(s => ({ ...s, workflow: payload as WorkflowEvent }))
        break
      case 'token':
        setState(s => ({ ...s, tokens: [...s.tokens, (payload as { text: string }).text] }))
        break
      case 'citations':
        setState(s => ({ ...s, citations: payload as Citation[] }))
        break
      case 'done':
        setState(s => ({ ...s, status: 'done' }))
        break
      case 'error':
        setState(s => ({
          ...s,
          status: 'error',
          error: (payload as { detail: string }).detail ?? 'Stream error',
        }))
        break
    }
  } catch { /* malformed frame — skip */ }
}
