/**
 * Notification Center Component
 *
 * Dropdown menu showing unseen notifications.
 * Click on a notification to navigate to the session and mark it as seen.
 */

import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  useNotificationStore,
  useUnseenNotifications,
  useUnseenNotificationCount,
  type Notification,
} from '@/stores'
import { SESSION_STATUS_UI_CONFIG, NOTIFICATION_TYPE_TO_STATUS } from '@/lib/constants'
import { useSessionList } from '@/api'
import { useNow } from '@/hooks'
import { cn } from '@/lib/utils'
import { formatRelativeShort } from '@/lib/timeFormat'

interface NotificationItemProps {
  notification: Notification
  onClick: () => void
}

function NotificationItem({ notification, onClick }: NotificationItemProps) {
  const sessionStatus = NOTIFICATION_TYPE_TO_STATUS[notification.type]
  const config = SESSION_STATUS_UI_CONFIG[sessionStatus]
  const StatusIcon = config.icon
  // Tick periodically so the relative time label stays fresh while the popover is open.
  const now = useNow()
  // notification.timestamp is epoch ms (number); pass directly so we don't risk
  // a RangeError from new Date(...).toISOString() if the value is ever invalid.
  const timestampLabel = formatRelativeShort(notification.timestamp, now)

  return (
    <DropdownMenuItem
      className="flex cursor-pointer flex-col items-start gap-1 p-3"
      onClick={onClick}
    >
      {/* Session title */}
      <span className="text-foreground w-full truncate text-sm font-medium">
        {notification.sessionName}
      </span>
      {/* Status row: icon + label on the left, timestamp on the right (mirrors SessionCard) */}
      <div className="flex w-full items-center gap-1.5">
        <StatusIcon className={cn('size-3.5 shrink-0', config.colorClass, config.iconClassName)} />
        <span className={cn('flex-1 truncate text-xs font-medium', config.colorClass)}>
          {config.cardLabel}
        </span>
        {timestampLabel && (
          <span className="text-muted-foreground shrink-0 text-xs whitespace-nowrap">
            {timestampLabel}
          </span>
        )}
      </div>
    </DropdownMenuItem>
  )
}

export function NotificationCenter() {
  const navigate = useNavigate()
  const { sessions } = useSessionList()
  const notifications = useUnseenNotifications()
  const count = useUnseenNotificationCount()
  const removeSessionNotifications = useNotificationStore((s) => s.removeSessionNotifications)
  const clearAll = useNotificationStore((s) => s.clearAll)

  const handleNotificationClick = useCallback(
    (notification: Notification) => {
      // Always remove the notification first (click = read = remove)
      removeSessionNotifications(notification.sessionId)

      // Check if session still exists before navigating
      const sessionExists = sessions.some((s) => s.id === notification.sessionId)

      if (!sessionExists) {
        console.warn(
          `[NotificationCenter] Session ${notification.sessionId} no longer exists, skipping navigation`
        )
        return
      }

      // Navigate to the session
      navigate(`/sessions/${notification.sessionId}`)
    },
    [navigate, sessions, removeSessionNotifications]
  )

  const handleClearAll = useCallback(() => {
    clearAll()
  }, [clearAll])

  const tooltipLabel = count > 0 ? `${count} notification${count > 1 ? 's' : ''}` : 'Notifications'

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button
              variant={count > 0 ? 'destructive' : 'secondary'}
              size="icon"
              className={cn('h-9 text-base', count > 9 ? 'w-auto min-w-9 px-2.5' : 'w-9')}
              aria-label={tooltipLabel}
            >
              {count > 0 ? count : <Bell className="size-4" />}
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>{tooltipLabel}</TooltipContent>
      </Tooltip>

      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Notifications</span>
          {count > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-auto px-2 py-1 text-xs"
              onClick={handleClearAll}
            >
              Mark all read
            </Button>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {notifications.length === 0 ? (
          <div className="text-muted-foreground p-4 text-center text-sm">No new notifications</div>
        ) : (
          <div className="max-h-80 overflow-y-auto">
            {notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                onClick={() => handleNotificationClick(notification)}
              />
            ))}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
