/**
 * Tests for VerificationAlert shared component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VerificationAlert } from '@/components/common/ModelConfigCard'

describe('VerificationAlert', () => {
  it('renders nothing when errors array is empty', () => {
    const { container } = render(<VerificationAlert errors={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders title and single error', () => {
    render(<VerificationAlert errors={['Orchestrator model: Connection refused']} />)
    expect(screen.getByText('Verification Failed')).toBeDefined()
    expect(screen.getByText(/Connection refused/)).toBeDefined()
  })

  it('renders multiple errors on separate lines', () => {
    render(
      <VerificationAlert
        errors={[
          "Orchestrator model: Model 'bad' not found. Available: magenticbrain-v1",
          'Browser use model: Connection timed out',
        ]}
      />
    )
    expect(screen.getByText('Verification Failed')).toBeDefined()
    // Each error gets its own div
    const divs = screen.getAllByText(/Orchestrator model|Browser use model/)
    expect(divs).toHaveLength(2)
  })

  it('bolds the model name prefix before colon', () => {
    const { container } = render(<VerificationAlert errors={['Orchestrator model: failed']} />)
    const bold = container.querySelector('.font-semibold')
    expect(bold).not.toBeNull()
    expect(bold!.textContent).toBe('Orchestrator model')
  })

  it('handles errors without colon separator', () => {
    render(<VerificationAlert errors={['Network error']} />)
    expect(screen.getByText('Network error')).toBeDefined()
  })
})
