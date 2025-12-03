/**
 * PlaybackControlsRow Component
 *
 * Unified controls row used by both BrowserEmbed and BrowserExpanded.
 *
 * Layout depends on mode:
 * - Live (VNC connected):  [LIVE toggle (ON)] ............. [Control button]
 * - History:               [LIVE toggle (OFF)] | [ProgressBar] [StepBack] [StepForward]
 * - VNC only (no history): [LIVE toggle (disabled, ON)] ... [Control button]
 * - History only (no VNC): [LIVE toggle (disabled, OFF)] | [ProgressBar] [StepBack] [StepForward]
 *
 * The LIVE toggle is always visible when this component renders. It is disabled
 * when there is nothing to toggle between (no VNC, or no screenshot history).
 * Parent components gate rendering on isVncConnected || hasHistory.
 */

import { MousePointer2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ProgressBar } from './ProgressBar'
import { PlaybackButtons } from './PlaybackButtons'
import { cn } from '@/lib/utils'

// =============================================================================
// Types
// =============================================================================

interface PlaybackControlsRowProps {
  /** Additional classes (e.g. padding) */
  className?: string
  /** Use smaller buttons (h-8) for compact layouts like BrowserEmbed */
  compact?: boolean

  // -- VNC state --
  /** Whether VNC is connected (determines if LIVE toggle is interactive) */
  isVncConnected: boolean

  // -- Control button (live mode only) --
  /** Called when Control button is clicked; omit to hide the button entirely */
  onControlClick?: () => void

  // -- Playback state --
  /** Whether display is in live mode (pre-computed by usePlaybackControls) */
  displayIsLive: boolean
  /** Set live mode on/off (matches Switch onCheckedChange signature) */
  onSetLive: (isLive: boolean) => void

  // -- ProgressBar (history mode only) --
  /** Total number of screenshots */
  total: number
  /** Current screenshot index (clamped) */
  validCurrentIndex: number
  /** Called when user clicks/drags to a screenshot index */
  onIndexChange: (index: number) => void

  // -- PlaybackButtons (history mode only) --
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
// Component
// =============================================================================

export function PlaybackControlsRow({
  className,
  compact,
  isVncConnected,
  onControlClick,
  displayIsLive,
  onSetLive,
  total,
  validCurrentIndex,
  onIndexChange,
  canStepBack,
  canStepForward,
  onStepBack,
  onStepForward,
  nextTooltip,
}: PlaybackControlsRowProps) {
  // Toggle is interactive only when VNC is connected and there's history to switch between
  const canToggle = isVncConnected && total > 0

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* LIVE toggle — always visible, disabled when not interactive */}
      <div className="flex shrink-0 flex-col items-center gap-0.5">
        <span
          className={cn(
            'text-[10px] leading-4 font-bold tracking-[0.2em]',
            canToggle ? 'text-secondary-foreground' : 'text-muted-foreground'
          )}
        >
          LIVE
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <Switch
              checked={displayIsLive}
              onCheckedChange={onSetLive}
              disabled={!canToggle}
              aria-label="Toggle live view"
            />
          </TooltipTrigger>
          <TooltipContent>
            {!canToggle
              ? displayIsLive
                ? 'Live view (no history yet)'
                : 'No live connection'
              : displayIsLive
                ? 'Switch to history view'
                : 'Switch to live view'}
          </TooltipContent>
        </Tooltip>
      </div>

      {/* Live mode: Control button on far right */}
      {displayIsLive && (
        <>
          {/* Spacer to push Control to the right */}
          <div className="flex-1" />

          {/* Control button */}
          {onControlClick && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  className={cn('shrink-0 gap-1.5 px-3 text-sm', compact && 'h-8')}
                  onClick={onControlClick}
                >
                  <MousePointer2 className="size-3.5" />
                  Control
                </Button>
              </TooltipTrigger>
              <TooltipContent>Take control of the browser</TooltipContent>
            </Tooltip>
          )}
        </>
      )}

      {/* History mode: separator + progress bar + step buttons */}
      {!displayIsLive && (
        <>
          {/* Vertical separator between toggle and progress bar */}
          <div className="bg-border w-px shrink-0 self-stretch" />

          <ProgressBar
            total={total}
            currentIndex={validCurrentIndex}
            onIndexChange={onIndexChange}
          />

          <PlaybackButtons
            compact={compact}
            canStepBack={canStepBack}
            canStepForward={canStepForward}
            onStepBack={onStepBack}
            onStepForward={onStepForward}
            nextTooltip={nextTooltip}
          />
        </>
      )}
    </div>
  )
}
