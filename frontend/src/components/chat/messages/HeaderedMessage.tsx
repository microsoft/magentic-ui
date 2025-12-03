/**
 * Headered Message
 *
 * Base component for messages with a styled header and body content.
 * Used by FinalAnswerMessage, InputRequestMessage, and SystemStatusMessage.
 */

import { cn } from '@/lib/utils'

// =============================================================================
// Types
// =============================================================================

export interface HeaderedMessageProps {
  /** Header text */
  header: string
  /** Optional class name for header styling (e.g., color) */
  headerClassName?: string
  /** Body content */
  children: React.ReactNode
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders a message with a styled header and body content.
 */
export function HeaderedMessage({ header, headerClassName, children }: HeaderedMessageProps) {
  return (
    <div className="flex flex-col">
      <h3 className={cn('mb-2 text-lg leading-7 font-bold', headerClassName)}>{header}</h3>
      <div className="text-base leading-6">{children}</div>
    </div>
  )
}
