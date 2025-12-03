/**
 * Dashboard Component
 *
 * Main dashboard view with session grid.
 */
import { cn } from '@/lib/utils'
import { SessionCard } from '@/components/session/SessionCard'
import { RenameDialog, DeleteDialog, useSessionDialogs } from '@/components/session/SessionDialogs'
import type { UISession } from '@/types'
import { isDraftSession } from '@/lib/constants'

interface DashboardProps {
  sessions: UISession[]
  onSessionClick?: (id: number) => void
}

export function Dashboard({ sessions, onSessionClick }: DashboardProps) {
  const dialogs = useSessionDialogs()

  if (sessions.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted-foreground text-lg">Create a new session to start</p>
      </div>
    )
  }

  return (
    <>
      <div className="flex-1 overflow-auto px-8 pt-9 pb-9">
        <div
          className={cn(
            // Responsive grid: 1 col on mobile, up to 4 cols on wide screens
            'mx-auto grid w-fit auto-rows-[180px] grid-cols-1 gap-6',
            'md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4',
            '*:w-[340px]'
          )}
        >
          {sessions.map((session) => (
            <SessionCard
              key={session.id}
              sessionId={session.id}
              title={session.title}
              status={session.status}
              timestamp={session.updatedAt}
              variant="dashboard"
              onClick={() => onSessionClick?.(session.id)}
              onRename={isDraftSession(session.id) ? undefined : dialogs.openRename}
              onDelete={dialogs.openDelete}
            />
          ))}
        </div>
      </div>

      <RenameDialog {...dialogs.renameProps} />
      <DeleteDialog {...dialogs.deleteProps} />
    </>
  )
}
