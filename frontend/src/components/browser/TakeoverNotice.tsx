import { MousePointer2Off } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ControlState } from '@/types'

/**
 * TakeoverNotice Component
 *
 * Displays a notice when user is in takeover mode (controlling the browser).
 * - 'user-pending': Shows animated stripe with "Waiting for agent..." message
 * - 'user': Shows solid background with control message + Release Control button
 *
 * Only used in expanded/maximized view.
 */
interface TakeoverNoticeProps {
  /** Current control state (only 'user-pending' or 'user' should be passed) */
  controlState: ControlState
  /** Called when Release Control button is clicked */
  onControlClick?: () => void
}

export function TakeoverNotice({ controlState, onControlClick }: TakeoverNoticeProps) {
  const isPending = controlState === 'user-pending'

  return (
    <div
      className={cn(
        'flex w-full items-center gap-3 px-4 py-3',
        // min-h: py-3(12)*2 + 2-line text(~40px) = 64px to keep both states same height
        'min-h-16',
        isPending ? 'animate-stripe' : 'bg-primary/20'
      )}
    >
      <p className="text-foreground flex min-h-9 flex-1 items-center text-sm">
        {isPending
          ? 'Waiting for the agent to stop...'
          : "You are in control of the browser. The agent is paused and won't observe these actions."}
      </p>
      {!isPending && onControlClick && (
        <Button
          variant="destructive"
          className="shrink-0 gap-1.5 px-3 text-sm"
          onClick={onControlClick}
        >
          <MousePointer2Off className="size-3.5" />
          Release Control
        </Button>
      )}
    </div>
  )
}
