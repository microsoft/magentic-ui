/**
 * Tests for the MessageList component.
 *
 * Regression coverage for the bug fixed in PR #613: the `renderItems`
 * useMemo previously depended on `messages.length` instead of `messages`,
 * so the memo was reused (and stale message refs were rendered) whenever
 * the array changed without a length change. This happens in real flows
 * such as `setMessages` overwriting WS messages with API messages of the
 * same length, or `replaceOptimisticUserMessage` swapping a single entry.
 *
 * MessageRenderer is wrapped in React.memo, so a stale message ref also
 * means the rendered DOM doesn't update — exactly what the user reported
 * as "messages suddenly fail to load until you refresh". The mock below
 * is wrapped in React.memo to mirror this real behavior.
 */
import { memo } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MessageList } from '@/components/chat/MessageList'
import type { ParsedMessage } from '@/types'
import type { Message } from '@/types/api'

// Mock MessageRenderer with a memoized renderer that mirrors the real
// component's React.memo wrapping. This way the test fails for the same
// underlying reason the user sees: when MessageList passes a stale message
// reference, memo skips re-rendering and the DOM stays out of date.
vi.mock('@/components/chat/MessageRenderer', () => ({
  MessageRenderer: memo(function MockMessageRenderer({ message }: { message: ParsedMessage }) {
    return (
      <div data-testid={`msg-${message.id}`}>
        {message.kind === 'text' || message.kind === 'user' ? message.content : message.kind}
      </div>
    )
  }),
}))

// Mock heavy children that aren't relevant to this test.
vi.mock('@/components/browser', () => ({
  BrowserEmbed: () => null,
}))

vi.mock('@/components/chat/messages', () => ({
  CuaMessage: () => null,
  CollapsibleHeader: () => null,
}))

// =============================================================================
// Helpers
// =============================================================================

function createRawMessage(id: number): Message {
  return {
    id,
    session_id: 1,
    run_id: 'run-1',
    config: { source: 'orchestrator', content: 'raw' },
    created_at: '2025-01-01T00:00:00Z',
  }
}

function createTextMessage(id: string, content: string): ParsedMessage {
  const numericId = Number(id)
  return {
    kind: 'text',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'orchestrator',
    content,
    raw: createRawMessage(Number.isNaN(numericId) ? 1 : numericId),
  }
}

// =============================================================================
// Tests
// =============================================================================

describe('MessageList', () => {
  it('updates rendered content when the messages array is replaced with a new array of the same length', () => {
    // Initial render: one message with content "v1".
    const initial: ParsedMessage[] = [createTextMessage('1', 'v1')]
    const { rerender } = render(<MessageList messages={initial} sessionId={1} />)
    expect(screen.getByTestId('msg-1')).toHaveTextContent('v1')

    // Re-render with a NEW array (different reference) of the same length but
    // updated content. This mimics chatStore.setMessages replacing WS messages
    // with API messages, or replaceOptimisticUserMessage swapping a single
    // entry — both produce a new array reference with messages.length unchanged.
    const replaced: ParsedMessage[] = [createTextMessage('1', 'v2')]
    rerender(<MessageList messages={replaced} sessionId={1} />)
    expect(screen.getByTestId('msg-1')).toHaveTextContent('v2')
  })

  it('renders newly added messages when array length grows', () => {
    const initial: ParsedMessage[] = [createTextMessage('1', 'first')]
    const { rerender } = render(<MessageList messages={initial} sessionId={1} />)
    expect(screen.getByTestId('msg-1')).toHaveTextContent('first')
    expect(screen.queryByTestId('msg-2')).toBeNull()

    const grown: ParsedMessage[] = [...initial, createTextMessage('2', 'second')]
    rerender(<MessageList messages={grown} sessionId={1} />)
    expect(screen.getByTestId('msg-1')).toHaveTextContent('first')
    expect(screen.getByTestId('msg-2')).toHaveTextContent('second')
  })
})
