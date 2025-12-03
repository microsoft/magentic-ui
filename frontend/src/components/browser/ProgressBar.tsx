/**
 * ProgressBar Component
 *
 * Draggable progress bar for screenshot playback.
 *
 * Progress: 0% = first screenshot, 100% = last screenshot.
 * Only rendered in history mode (not live).
 */

import { useRef, useCallback, useEffect, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'

// Half the playhead diameter (size-4 = 16px → radius = 8px).
// The playhead's center moves within [PLAYHEAD_R, 100% − PLAYHEAD_R]
// so its circle never extends beyond the track edges.
const PLAYHEAD_R = 8

// =============================================================================
// Types
// =============================================================================

interface ProgressBarProps {
  /** Total number of screenshots */
  total: number
  /** Current screenshot index (clamped) */
  currentIndex: number
  /** Called when user clicks/drags to a screenshot index */
  onIndexChange: (index: number) => void
}

// =============================================================================
// Component
// =============================================================================

export function ProgressBar({ total, currentIndex, onIndexChange }: ProgressBarProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)
  const cleanupDrag = useRef<(() => void) | null>(null)

  // Clean up document-level drag listeners on unmount
  useEffect(() => {
    return () => cleanupDrag.current?.()
  }, [])

  // Calculate playhead position:
  // - Single screenshot → 100%
  // - Multiple screenshots: first = 0%, last = 100%
  const getProgress = (): number => {
    if (total <= 1) return 100
    return (currentIndex / (total - 1)) * 100
  }

  const progress = getProgress()

  // Convert click/drag position to screenshot index.
  const getIndexFromPosition = useCallback(
    (percentage: number): number => {
      if (total <= 1) return 0
      const rawIndex = (percentage / 100) * (total - 1)
      return Math.max(0, Math.min(total - 1, Math.round(rawIndex)))
    },
    [total]
  )

  const handlePositionChange = useCallback(
    (clientX: number) => {
      if (!trackRef.current || total === 0) return
      const rect = trackRef.current.getBoundingClientRect()
      // Map cursor position to the playhead's movable range
      const x = clientX - rect.left - PLAYHEAD_R
      const effectiveWidth = rect.width - PLAYHEAD_R * 2
      const percentage = Math.max(0, Math.min(100, (x / effectiveWidth) * 100))
      onIndexChange(getIndexFromPosition(percentage))
    },
    [onIndexChange, total, getIndexFromPosition]
  )

  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isDragging.current || total === 0) return
    handlePositionChange(e.clientX)
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (total === 0) return
    isDragging.current = true
    handlePositionChange(e.clientX)

    const handleMouseMove = (moveEvent: MouseEvent) => {
      handlePositionChange(moveEvent.clientX)
    }

    const handleMouseUp = () => {
      isDragging.current = false
      cleanupDrag.current = null
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    cleanupDrag.current = handleMouseUp
  }

  const isEmpty = total === 0
  const isInteractive = !isEmpty

  // Keyboard navigation for ARIA slider role
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (!isInteractive) return
      switch (e.key) {
        case 'ArrowLeft':
        case 'ArrowDown':
          e.preventDefault()
          onIndexChange(Math.max(0, currentIndex - 1))
          break
        case 'ArrowRight':
        case 'ArrowUp':
          e.preventDefault()
          onIndexChange(Math.min(total - 1, currentIndex + 1))
          break
        case 'Home':
          e.preventDefault()
          onIndexChange(0)
          break
        case 'End':
          e.preventDefault()
          onIndexChange(total - 1)
          break
      }
    },
    [isInteractive, currentIndex, total, onIndexChange]
  )

  return (
    <div
      ref={trackRef}
      className={cn(
        'relative flex flex-1 items-center py-[3px]',
        isInteractive
          ? 'focus-visible:ring-ring cursor-pointer rounded focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:outline-none'
          : 'cursor-default opacity-50'
      )}
      onClick={isInteractive ? handleTrackClick : undefined}
      onMouseDown={isInteractive ? handleMouseDown : undefined}
      onKeyDown={isInteractive ? handleKeyDown : undefined}
      role="slider"
      aria-label="Screenshot progress"
      aria-valuemin={1}
      aria-valuemax={total || 1}
      aria-valuenow={isEmpty ? 1 : currentIndex + 1}
      aria-disabled={!isInteractive}
      tabIndex={isInteractive ? 0 : -1}
    >
      {/* Track — full width; fill tracks playhead center position */}
      <div className="bg-accent-2 h-1.5 w-full overflow-hidden rounded-full">
        {/* Progress fill — width matches playhead center so they stay aligned */}
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-100',
            isEmpty ? 'bg-muted-foreground/30' : 'bg-primary'
          )}
          style={{
            width: `calc(${PLAYHEAD_R}px + (100% - ${PLAYHEAD_R * 2}px) * ${progress / 100})`,
          }}
        />
      </div>

      {/* Playhead — moves within [PLAYHEAD_R, 100% − PLAYHEAD_R] so it never overflows */}
      {!isEmpty && (
        <div
          className={cn(
            'absolute top-1/2 size-4 rounded-full',
            'bg-background border-primary border-2 shadow-sm',
            'transition-[left] duration-100'
          )}
          style={{
            left: `calc(${PLAYHEAD_R}px + (100% - ${PLAYHEAD_R * 2}px) * ${progress / 100})`,
            transform: 'translate(-50%, -50%)',
          }}
        />
      )}
    </div>
  )
}
