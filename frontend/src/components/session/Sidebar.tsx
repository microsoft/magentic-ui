/**
 * Sidebar Component
 *
 * Left sidebar displaying session history list.
 */
import { SessionCard } from '@/components/session/SessionCard'
import { RenameDialog, DeleteDialog, useSessionDialogs } from '@/components/session/SessionDialogs'
import { isDraftSession } from '@/lib/constants'
import type { UISession } from '@/types'

export interface SidebarProps {
  sessions: UISession[]
  selectedSessionId?: number
  onSessionSelect?: (id: number) => void
  /** Called after a session is successfully deleted */
  onSessionDeleted?: (sessionId: number) => void
}

export function Sidebar({
  sessions,
  selectedSessionId,
  onSessionSelect,
  onSessionDeleted,
}: SidebarProps) {
  const dialogs = useSessionDialogs(onSessionDeleted)

  // Render content based on state: empty → list
  const renderContent = () => {
    if (sessions.length === 0) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-muted-foreground text-lg">Create a new session to start</p>
        </div>
      )
    }

    return (
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex flex-col gap-3">
          {sessions.map((session) => (
            <SessionCard
              key={session.id}
              sessionId={session.id}
              title={session.title}
              status={session.status}
              timestamp={session.updatedAt}
              variant="sidebar"
              selected={selectedSessionId === session.id}
              onClick={() => onSessionSelect?.(session.id)}
              onRename={isDraftSession(session.id) ? undefined : dialogs.openRename}
              onDelete={dialogs.openDelete}
            />
          ))}
        </div>
      </div>
    )
  }

  return (
    <>
      <aside
        aria-label="Session history"
        className="border-sidebar-border bg-sidebar flex h-full w-[340px] shrink-0 flex-col border-r"
      >
        {renderContent()}
      </aside>

      <RenameDialog {...dialogs.renameProps} />
      <DeleteDialog {...dialogs.deleteProps} />
    </>
  )
}
