/**
 * Error Message
 *
 * Displays agent runtime error messages (metadata.type: 'error').
 * Examples: tool call failures, page not initialized, etc.
 *
 * Note: Run status errors (system message with status: 'error') are displayed
 * by SystemStatusMessage, not this component.
 */

import { Markdown } from '@/components/common'
import { HeaderedMessage } from './HeaderedMessage'

// =============================================================================
// Types
// =============================================================================

export interface ErrorMessageProps {
  /** Error message content */
  content: string
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders error message with red "Error" header.
 * Returns null when content is empty (hides entire message).
 */
export function ErrorMessage({ content }: ErrorMessageProps) {
  // Hide entire message when backend sends empty content
  if (!content) return null

  return (
    <HeaderedMessage header="Error" headerClassName="text-status-error">
      <Markdown>{content}</Markdown>
    </HeaderedMessage>
  )
}
