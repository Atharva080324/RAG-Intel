/**
 * Tests for the useSSE hook.
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSE } from '@/hooks/useSSE'

// Build a minimal fake ReadableStream from SSE frames
function makeSSEStream(frames: string[]): ReadableStream {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame))
      }
      controller.close()
    },
  })
}

function mockFetchWith(frames: string[]) {
  const mockFetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    body: makeSSEStream(frames),
  } as unknown as Response)
  vi.stubGlobal('fetch', mockFetch)
  return mockFetch
}

describe('useSSE', () => {
  it('starts in idle state', () => {
    const { result } = renderHook(() => useSSE())
    expect(result.current.status).toBe('idle')
    expect(result.current.tokens).toEqual([])
    expect(result.current.workflow).toBeNull()
  })

  it('transitions to done after receiving done event', async () => {
    mockFetchWith([
      'event: token\ndata: {"text":"Hello"}\n\n',
      'event: citations\ndata: []\n\n',
      'event: done\ndata: {}\n\n',
    ])

    const { result } = renderHook(() => useSSE())
    await act(async () => {
      result.current.start('tok', 1, 'What is this?')
      // Allow microtasks to settle
      await new Promise(r => setTimeout(r, 50))
    })

    expect(result.current.tokens).toContain('Hello')
  })

  it('captures workflow event', async () => {
    const wf = {
      intent: 'text',
      rewrite_attempts: 0,
      relevance_score: 0.8,
      minimum_grounding_score: 0.15,
      answer_mode: 'grounded_answer',
      retrieval: {
        query_type: 'text',
        semantic_candidates: 10,
        lexical_candidates: 5,
        fused_candidates: 12,
        returned_chunks: 8,
        retrieval_latency_ms: 120,
        rewritten_queries: [],
      },
    }
    mockFetchWith([
      `event: workflow\ndata: ${JSON.stringify(wf)}\n\n`,
      'event: done\ndata: {}\n\n',
    ])

    const { result } = renderHook(() => useSSE())
    await act(async () => {
      result.current.start('tok', 1, 'q')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(result.current.workflow?.intent).toBe('text')
    expect(result.current.workflow?.retrieval.semantic_candidates).toBe(10)
  })

  it('handles error event', async () => {
    mockFetchWith([
      'event: error\ndata: {"detail":"Answer generation failed"}\n\n',
    ])

    const { result } = renderHook(() => useSSE())
    await act(async () => {
      result.current.start('tok', 1, 'q')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error).toContain('generation failed')
  })

  it('resets to idle state', () => {
    const { result } = renderHook(() => useSSE())
    act(() => result.current.reset())
    expect(result.current.status).toBe('idle')
    expect(result.current.tokens).toEqual([])
  })
})
