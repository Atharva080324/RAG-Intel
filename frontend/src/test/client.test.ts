/**
 * Tests for the API client module.
 * We mock `fetch` globally so no real network calls are made.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { authApi, documentsApi, healthApi, ApiError } from '@/api/client'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function makeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('authApi.demo', () => {
  it('returns a token on 200', async () => {
    mockFetch.mockResolvedValue(makeResponse(200, {
      access_token: 'tok123',
      token_type: 'bearer',
      expires_in: 3600,
    }))
    const result = await authApi.demo()
    expect(result.access_token).toBe('tok123')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/demo'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('throws ApiError on 404', async () => {
    mockFetch.mockResolvedValue(makeResponse(404, { detail: 'Demo mode is not enabled on this deployment' }))
    await expect(authApi.demo()).rejects.toMatchObject({
      status: 404,
      message: 'Demo mode is not enabled on this deployment',
    })
  })
})

describe('authApi.login', () => {
  it('sends form-encoded credentials', async () => {
    mockFetch.mockResolvedValue(makeResponse(200, {
      access_token: 'jwt',
      token_type: 'bearer',
      expires_in: 1800,
    }))
    await authApi.login('user@test.com', 'pw')
    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(opts.body?.toString()).toContain('username=user%40test.com')
  })
})

describe('healthApi.check', () => {
  it('resolves when API is up', async () => {
    mockFetch.mockResolvedValue(makeResponse(200, { status: 'ok' }))
    const r = await healthApi.check()
    expect(r.status).toBe('ok')
  })

  it('throws on non-200', async () => {
    mockFetch.mockResolvedValue(makeResponse(503, { detail: 'unavailable' }))
    await expect(healthApi.check()).rejects.toBeInstanceOf(ApiError)
  })
})

describe('documentsApi.upload', () => {
  it('sends FormData with the file', async () => {
    mockFetch.mockResolvedValue(makeResponse(202, {
      job_id: 1, document_id: 2, status: 'queued', status_url: '/jobs/1',
    }))
    const file = new File(['pdf content'], 'test.pdf', { type: 'application/pdf' })
    const result = await documentsApi.upload('tok', file)
    expect(result.job_id).toBe(1)
    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(opts.body).toBeInstanceOf(FormData)
  })
})

describe('documentsApi.delete', () => {
  it('sends DELETE request with bearer token', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => null,
    })
    await documentsApi.delete('tok_abc', 42)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/documents/42'),
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({
          Authorization: 'Bearer tok_abc',
        }),
      }),
    )
  })
})

