/**
 * Session Status Indicator
 *
 * Displays session status at the bottom of the chat view.
 * Shows icon + status text matching Figma design.
 *
 * Note: This is a status indicator, not a chat message type.
 * Rendered directly by ChatView, not through MessageRenderer.
 */

import { cn } from '@/lib/utils'
import { SESSION_STATUS_UI_CONFIG } from '@/lib/constants'
import type { SessionStatus } from '@/types'

export interface SessionStatusIndicatorProps {
  status: SessionStatus
  /**
   * Optional override for the label text. Used by the transient
   * ``agent_state`` signal so we can swap "In progress" for
   * "Waiting for model\u2026" without changing the underlying status.
   * The icon and color stay tied to ``status`` so the visual stack
   * (spinner + active color) is preserved.
   */
  labelOverride?: string
}

/**
 * Status indicator shown at the bottom of chat view.
 */
export function SessionStatusIndicator({ status, labelOverride }: SessionStatusIndicatorProps) {
  const config = SESSION_STATUS_UI_CONFIG[status]
  const StatusIcon = config.icon
  const label = labelOverride ?? config.chatLabel

  return (
    <div className="flex items-center gap-1">
      <StatusIcon className={cn('size-4 shrink-0', config.colorClass, config.iconClassName)} />
      <p className={cn('truncate text-sm leading-[21px] font-bold', config.colorClass)}>{label}</p>
    </div>
  )
}
