/**
 * System Status Message
 *
 * Displays system status messages (complete, error, stopped, paused, awaiting_input, etc.)
 * with a colored header based on status type.
 * Uses HeaderedMessage for consistent styling.
 */

import { Markdown } from '@/components/common'
import type { ServerRunStatus } from '@/types/api'
import { HeaderedMessage } from './HeaderedMessage'

// =============================================================================
// Types
// =============================================================================

export interface SystemStatusMessageProps {
  /** Status type determines header text and color */
  status: ServerRunStatus
  /** Message content to display below header */
  content: string
}

// =============================================================================
// Constants
// =============================================================================

/** Header configuration for each status type */
const STATUS_CONFIG: Record<ServerRunStatus, { label: string; className: string }> = {
  created: { label: 'Created', className: 'text-muted-foreground' },
  active: { label: 'Active', className: 'text-status-active' },
  complete: { label: 'Complete', className: 'text-status-completed' },
  error: { label: 'Error', className: 'text-status-error' },
  stopped: { label: 'Stopped', className: 'text-status-stopped' },
  paused: { label: 'Paused', className: 'text-status-waiting-input' },
  awaiting_input: { label: 'Awaiting Input', className: 'text-status-waiting-input' },
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders system status message with colored header and body content.
 * Returns null when content is empty (hides entire message).
 */
export function SystemStatusMessage({ status, content }: SystemStatusMessageProps) {
  // Hide entire message when backend sends empty content
  if (!content) return null

  const { label, className } = STATUS_CONFIG[status]

  return (
    <HeaderedMessage header={label} headerClassName={className}>
      <Markdown>{content}</Markdown>
    </HeaderedMessage>
  )
}
