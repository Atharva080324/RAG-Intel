/**
 * Typed API client – matches the FastAPI OpenAPI schema exactly.
 *
 * All calls read VITE_API_BASE from env.  The client never hard-codes URLs so
 * the same build works against localhost:8000 (dev) and the production Caddy
 * domain (prod via Vercel env vars).
 */

const BASE = (import.meta.env.VITE_API_BASE as string | undefined ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

// ── Types ────────────────────────────────────────────────────────────────────

export interface Token {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface UserRead {
  id: number
  email: string
  is_active: boolean
  created_at: string
}

export interface JobAccepted {
  job_id: number
  document_id: number
  status: string
  status_url: string
}

export interface JobRead {
  id: number
  document_id: number
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DocumentRead {
  id: number
  filename: string
  status: string
  content_hash: string
  created_at: string
  updated_at: string
}

export interface DocumentListRead {
  items: DocumentRead[]
  skip: number
  limit: number
}

export interface Citation {
  source: string     // e.g. "S1"
  page_number: number
  chunk_type: string
}

export interface RetrievalTrace {
  query_type: string
  semantic_candidates: number
  lexical_candidates: number
  fused_candidates: number
  returned_chunks: number
  retrieval_latency_ms: number
  rewritten_queries: string[]
}

export interface AnalyzeResponse {
  operation: string
  column: string
  value: number
  rows_used: number
  source_chunk_id: number
  retrieval_trace?: RetrievalTrace
}

export interface WorkflowEvent {
  intent: string
  rewrite_attempts: number
  relevance_score: number
  minimum_grounding_score: number
  answer_mode: 'grounded_answer' | 'insufficient_evidence'
  retrieval: RetrievalTrace & { rewritten_queries: string[] }
}

export interface HealthResponse {
  status: 'ok'
}

// ── Core fetch helper ────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...rest } = options
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string> | undefined),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!(rest.body instanceof FormData)) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, { ...rest, headers })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const j = await res.json()
      detail = j.detail ?? detail
    } catch { /* ignore */ }
    throw new ApiError(res.status, String(detail))
  }
  // 204 No Content
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  /** POST /auth/token  (OAuth2 password grant) */
  login(email: string, password: string): Promise<Token> {
    const body = new URLSearchParams({ username: email, password })
    return apiFetch('/auth/token', { method: 'POST', body })
  },

  /** POST /auth/signup */
  signup(email: string, password: string): Promise<UserRead> {
    return apiFetch('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  /** POST /auth/demo  – only works when DEMO_MODE=true on the backend */
  demo(): Promise<Token> {
    return apiFetch('/auth/demo', { method: 'POST' })
  },

  /** GET /auth/google/login  – returns a redirect; open in the same tab */
  googleLoginUrl(): string {
    return `${BASE}/auth/google/login`
  },
}

// ── Documents ────────────────────────────────────────────────────────────────

export const documentsApi = {
  list(token: string, skip = 0, limit = 20): Promise<DocumentListRead> {
    return apiFetch(`/documents/?skip=${skip}&limit=${limit}`, { token })
  },

  upload(token: string, file: File): Promise<JobAccepted> {
    const form = new FormData()
    form.append('file', file)
    return apiFetch('/documents/upload', { method: 'POST', body: form, token })
  },

  get(token: string, id: number): Promise<DocumentRead> {
    return apiFetch(`/documents/${id}`, { token })
  },
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

export const jobsApi = {
  get(token: string, jobId: number): Promise<JobRead> {
    return apiFetch(`/jobs/${jobId}`, { token })
  },
}

// ── Questions ────────────────────────────────────────────────────────────────

export const questionsApi = {
  analyze(token: string, documentId: number, question: string): Promise<AnalyzeResponse> {
    return apiFetch('/questions/analyze', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, question }),
      token,
    })
  },

  /**
   * Open a streaming SSE connection to /questions/stream.
   * Returns the raw EventSource; callers must close it when done.
   *
   * Because EventSource doesn't support POST bodies or custom headers,
   * we use fetch + ReadableStream for the actual implementation.
   */
  streamUrl(token: string, documentId: number, question: string): {
    url: string
    body: string
    token: string
  } {
    return {
      url: `${BASE}/questions/stream`,
      body: JSON.stringify({ document_id: documentId, question }),
      token,
    }
  },
}

// ── Health & Readiness ────────────────────────────────────────────────────────

export interface ReadyResponse {
  status: string
  warmed_up?: boolean
  dependencies: {
    database: string
    redis: string
  }
}

export const healthApi = {
  check(): Promise<HealthResponse> {
    return apiFetch('/health')
  },
}

export const readyApi = {
  check(): Promise<ReadyResponse> {
    return apiFetch('/ready')
  },
}

export { ApiError, BASE }

