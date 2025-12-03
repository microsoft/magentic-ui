/**
 * SessionCard Component
 *
 * Displays a session card with title and status.
 * Used in both Dashboard (grid) and Sidebar (list) views.
 */
import { cn } from '@/lib/utils'
import { SESSION_STATUS_UI_CONFIG } from '@/lib/constants'
import { formatRelativeShort } from '@/lib/timeFormat'
import { useNow } from '@/hooks'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { MoreVertical, Pencil, Trash2 } from 'lucide-react'
import { useHasNotification } from '@/stores'
import type { SessionStatus } from '@/types'

/** Layout variant: 'dashboard' has fixed height, 'sidebar' hugs content */
export type SessionCardVariant = 'dashboard' | 'sidebar'

export interface SessionCardProps {
  sessionId?: number
  title: string
  status: SessionStatus
  /**
   * ISO timestamp of the latest activity (run.updated_at). Rendered as a
   * compact relative time on the right of the status row. Hidden when the
   * card is hovered (the "..." menu takes its place) or when status is
   * "active" (the running indicator already conveys liveness).
   */
  timestamp?: string | null
  variant?: SessionCardVariant
  selected?: boolean
  onClick?: () => void
  onRename?: (sessionId: number, currentName: string) => void
  onDelete?: (sessionId: number, name: string) => void
}

export function SessionCard({
  sessionId,
  title,
  status,
  timestamp,
  variant = 'dashboard',
  selected = false,
  onClick,
  onRename,
  onDelete,
}: SessionCardProps) {
  const config = SESSION_STATUS_UI_CONFIG[status]
  const StatusIcon = config.icon
  const hasNotification = useHasNotification(sessionId ?? -1)
  const hasMenu = Boolean(onRename || onDelete)
  const showTimestamp = Boolean(timestamp) && status !== 'active'
  // Tick the relative-time label periodically so cards don't get stuck on "Just now".
  const now = useNow()
  const timestampLabel = showTimestamp ? formatRelativeShort(timestamp, now) : ''

  return (
    <Card
      role="button"
      tabIndex={0}
      className={cn(
        'group flex flex-col gap-3 p-4 transition-colors',
        'hover:bg-card-hover cursor-pointer',
        // Dashboard: push status to bottom
        variant === 'dashboard' && 'justify-between',
        // Selected state
        selected && 'border-primary shadow-[0_0_0_3px_var(--card-selected-ring)]',
        // Focus state for keyboard navigation
        'focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none'
      )}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      }}
    >
      {/* Title */}
      <h3 className={cn('text-foreground line-clamp-2 text-lg leading-[22px] font-bold')}>
        {title}
      </h3>

      {/* Status indicator */}
      <div className="flex items-center gap-1">
        <StatusIcon className={cn('size-4 shrink-0', config.colorClass, config.iconClassName)} />
        <p
          className={cn(
            'flex-1 truncate text-sm leading-[21px] font-bold tracking-tight',
            config.colorClass
          )}
        >
          {config.cardLabel}
        </p>

        {/*
          Right side action area.
          Default state: [timestamp] [notification dot]
          On card hover (and only when actions exist): [...] menu fades in over them.
          Min-width preserves the slot so layout doesn't shift between states.
        */}
        <div className="relative flex h-6 shrink-0 items-center justify-end">
          {/* Default-state contents (timestamp + dot). Wrapped together so they fade as a unit. */}
          {(showTimestamp || hasNotification) && (
            <div
              className={cn(
                'flex items-center gap-1.5 transition-all',
                hasMenu && 'group-hover:invisible group-hover:opacity-0',
                hasMenu &&
                  'group-has-data-[state=open]:invisible group-has-data-[state=open]:opacity-0'
              )}
            >
              {showTimestamp && (
                <span
                  className="text-muted-foreground text-sm leading-[22px] whitespace-nowrap"
                  aria-label={`Last updated ${timestampLabel}`}
                >
                  {timestampLabel}
                </span>
              )}
              {hasNotification && (
                <span
                  className={cn('size-2 shrink-0 rounded-full', config.dotColorClass)}
                  aria-label="New notification"
                />
              )}
            </div>
          )}

          {/* More button with dropdown - only visible on hover, hidden when no actions */}
          {hasMenu && (
            <Tooltip>
              <DropdownMenu>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        // Anchor to the right edge of the action area
                        'absolute top-1/2 right-0 size-6 -translate-y-1/2',
                        // Hidden by default
                        'invisible opacity-0 transition-all',
                        // Show on card hover
                        'group-hover:visible group-hover:opacity-100',
                        // Keep visible when dropdown is open
                        'data-[state=open]:visible data-[state=open]:opacity-100',
                        // Button hover
                        'hover:bg-accent-2'
                      )}
                      onClick={(e: React.MouseEvent) => e.stopPropagation()}
                      aria-label="More options"
                    >
                      <MoreVertical className="size-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent>More options</TooltipContent>
                <DropdownMenuContent
                  align="end"
                  onClick={(e: React.MouseEvent) => e.stopPropagation()}
                >
                  {onRename && (
                    <DropdownMenuItem
                      onSelect={() => {
                        if (sessionId) {
                          onRename(sessionId, title)
                        }
                      }}
                    >
                      <Pencil className="size-4" />
                      Rename
                    </DropdownMenuItem>
                  )}
                  {onDelete && (
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onSelect={() => {
                        if (sessionId) {
                          onDelete(sessionId, title)
                        }
                      }}
                    >
                      <Trash2 className="size-4" />
                      Delete
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </Tooltip>
          )}
        </div>
      </div>
    </Card>
  )
}
