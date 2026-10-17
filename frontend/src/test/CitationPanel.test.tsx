/**
 * Tests for the CitationPanel component.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CitationPanel } from '@/components/chat/CitationPanel'
import type { Citation } from '@/api/client'

const mockCitation: Citation = {
  source: 'S1',
  page_number: 5,
  chunk_type: 'text',
}

describe('CitationPanel', () => {
  it('renders nothing when citation is null', () => {
    const { container } = render(<CitationPanel citation={null} onClose={vi.fn()} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows source, page number, and chunk type', () => {
    render(<CitationPanel citation={mockCitation} onClose={vi.fn()} />)
    expect(screen.getByText(/Source \[S1\]/i)).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('TEXT')).toBeInTheDocument()
  })

  it('calls onClose when X button is clicked', () => {
    const onClose = vi.fn()
    render(<CitationPanel citation={mockCitation} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: '' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders a table chunk type correctly', () => {
    const tableCitation: Citation = { source: 'S2', page_number: 3, chunk_type: 'table' }
    render(<CitationPanel citation={tableCitation} onClose={vi.fn()} />)
    expect(screen.getByText('TABLE')).toBeInTheDocument()
  })
})
