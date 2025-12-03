/**
 * Final Answer Message
 *
 * Displays the agent's final answer with a "Final Answer" headline
 * and formatted content below.
 */

import { Markdown } from '@/components/common'
import { HeaderedMessage } from './HeaderedMessage'

// =============================================================================
// Types
// =============================================================================

export interface FinalAnswerMessageProps {
  /** Pre-extracted content from ParsedFinalAnswerMessage */
  content: string
}

// =============================================================================
// Constants
// =============================================================================

/** Prefix to strip from content (backend includes this in the message) */
const FINAL_ANSWER_PREFIX = 'Final Answer:'

// =============================================================================
// Component
// =============================================================================

/**
 * Renders final answer with styled headline and body content.
 *
 * Backend format: "Final Answer: <actual content>"
 * UI format:
 *   Final Answer (headline)
 *   <actual content> (body)
 */
export function FinalAnswerMessage({ content }: FinalAnswerMessageProps) {
  const bodyContent = extractBodyContent(content)

  return (
    <HeaderedMessage header="Final Answer" headerClassName="text-status-completed">
      <Markdown>{bodyContent}</Markdown>
    </HeaderedMessage>
  )
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Extract the body content by removing the "Final Answer: " prefix if present.
 */
function extractBodyContent(content: string): string {
  // Remove "Final Answer: " prefix if present (case-insensitive, with optional whitespace)
  const prefixRegex = new RegExp(`^${FINAL_ANSWER_PREFIX}\\s*`, 'i')
  return content.replace(prefixRegex, '').trim()
}
