/**
 * PlaybackButtons Component
 *
 * Step back / Step forward button pair used in history mode.
 * The Live toggle is now handled by a Switch in PlaybackControlsRow.
 */

import type { ReactNode } from 'react'
import { StepBack, StepForward } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

// =============================================================================
// Types
// =============================================================================

interface PlaybackButtonsProps {
  /** Use smaller buttons (h-8/size-8) for compact layouts like BrowserEmbed */
  compact?: boolean
  /** Whether Prev button can be clicked */
  canStepBack: boolean
  /** Whether Next button can be clicked */
  canStepForward: boolean
  /** Handler for Prev button */
  onStepBack: () => void
  /** Handler for Next button */
  onStepForward: () => void
  /** Tooltip text for Next button */
  nextTooltip: string
}

// =============================================================================
// Helpers
// =============================================================================

/** Icon button with conditional tooltip — tooltip hidden when disabled */
function StepButton({
  compact,
  enabled,
  onClick,
  icon,
  label,
  tooltip,
}: {
  compact?: boolean
  enabled: boolean
  onClick: () => void
  icon: ReactNode
  label: string
  tooltip: string
}) {
  const btn = (
    <Button
      variant="secondary"
      size="icon"
      className={cn(compact ? 'size-8' : 'size-9')}
      disabled={!enabled}
      onClick={enabled ? onClick : undefined}
      aria-label={label}
    >
      {icon}
    </Button>
  )

  if (!enabled) return btn

  return (
    <Tooltip>
      <TooltipTrigger asChild>{btn}</TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  )
}

// =============================================================================
// Component
// =============================================================================

export function PlaybackButtons({
  compact,
  canStepBack,
  canStepForward,
  onStepBack,
  onStepForward,
  nextTooltip,
}: PlaybackButtonsProps) {
  return (
    <div className="flex items-center gap-2">
      <StepButton
        compact={compact}
        enabled={canStepBack}
        onClick={onStepBack}
        icon={<StepBack className="size-4" />}
        label="Previous action"
        tooltip="Previous action"
      />

      <StepButton
        compact={compact}
        enabled={canStepForward}
        onClick={onStepForward}
        icon={<StepForward className="size-4" />}
        label="Next action"
        tooltip={nextTooltip}
      />
    </div>
  )
}
