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
}

/**
 * Status indicator shown at the bottom of chat view.
 */
export function SessionStatusIndicator({ status }: SessionStatusIndicatorProps) {
  const config = SESSION_STATUS_UI_CONFIG[status]
  const StatusIcon = config.icon

  return (
    <div className="flex items-center gap-1">
      <StatusIcon className={cn('size-4 shrink-0', config.colorClass, config.iconClassName)} />
      <p className={cn('truncate text-sm leading-[21px] font-bold', config.colorClass)}>
        {config.chatLabel}
      </p>
    </div>
  )
}
