/**
 * ConnectionStatusBanner — shown below the page header when the backend
 * is unreachable. Mounted on each page that has a Header (and mirrored
 * inside SettingsDialog since dialog overlays dim it).
 */
import { CircleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useConnectionIssue } from '@/hooks'
import { CONNECTION_STATUS_COPY } from '@/lib/connectionStatus'

export function ConnectionStatusBanner() {
  const issue = useConnectionIssue()
  if (!issue) return null

  return (
    <div
      role="alert"
      className={cn(
        'bg-destructive-subtle border-destructive-border/40 text-destructive',
        'flex w-full shrink-0 items-center gap-2 border-y px-4 py-2 text-sm'
      )}
    >
      <CircleAlert className="size-4 shrink-0" />
      <p>
        <span className="font-bold">{CONNECTION_STATUS_COPY.label}</span>{' '}
        {CONNECTION_STATUS_COPY.message}
      </p>
    </div>
  )
}
