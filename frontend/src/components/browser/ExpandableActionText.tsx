/**
 * ExpandableActionText
 *
 * The "thoughts + actionResult" text block shown inside browser views.
 * Treats the two lines as a single interactive unit:
 * - thoughts: 2 lines max when collapsed (line-clamp-2)
 * - actionResult: 1 line max when collapsed (truncate)
 * - If either line is truncated, the whole block becomes clickable and shows a
 *   "Click to expand" hover hint
 * - Click anywhere → both expand together; click again → both collapse
 *
 * Truncation is detected via ResizeObserver, so the affordance auto-updates
 * as the surrounding container resizes.
 *
 * Used by both `ActionDescription` (expanded view) and `DescriptionOverlay`
 * (embedded overlay).
 */

import { useEffect, useRef, useState } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

// =============================================================================
// Helpers
// =============================================================================

/**
 * Detects whether a block-level element's content is visually truncated by CSS
 * (line-clamp or text-overflow). Re-checks on element resize and whenever
 * `text` changes (e.g. when switching to a different screenshot).
 *
 * Pass `enabled: false` to pause the ResizeObserver (e.g. while expanded). The
 * last measured value is preserved so the caller stays interactive on the same
 * render that toggles back to collapsed.
 */
function useIsTruncated(
  ref: React.RefObject<HTMLElement | null>,
  enabled: boolean,
  text: string | undefined
) {
  const [truncated, setTruncated] = useState(false)

  useEffect(() => {
    if (!enabled) return
    const el = ref.current
    if (!el) return

    const check = () => {
      const overflow = el.scrollHeight > el.clientHeight || el.scrollWidth > el.clientWidth
      setTruncated(overflow)
    }

    const observer = new ResizeObserver(check)
    observer.observe(el)
    // `check()` runs synchronously here so a `text` change immediately
    // overwrites any stale value from the previous render.
    check()

    return () => observer.disconnect()
  }, [ref, enabled, text])

  // When text becomes empty there is nothing to truncate. Returning `false &&`
  // here keeps the caller's `isInteractive` accurate without triggering an
  // extra effect-driven setState.
  return text ? truncated : false
}

// =============================================================================
// Component
// =============================================================================

interface ExpandableActionTextProps {
  thoughts?: string
  actionResult?: string
  /** Extra class names applied to each line (e.g. text color). */
  textClassName?: string
}

export function ExpandableActionText({
  thoughts,
  actionResult,
  textClassName,
}: ExpandableActionTextProps) {
  const thoughtsRef = useRef<HTMLParagraphElement>(null)
  const actionRef = useRef<HTMLParagraphElement>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  // Only detect truncation while collapsed; once expanded, the block stays
  // clickable so the user can collapse it again.
  const isThoughtsTruncated = useIsTruncated(thoughtsRef, !isExpanded, thoughts)
  const isActionTruncated = useIsTruncated(actionRef, !isExpanded, actionResult)
  const isInteractive = isThoughtsTruncated || isActionTruncated || isExpanded

  if (!thoughts && !actionResult) return null

  const toggle = () => setIsExpanded((v) => !v)

  // Single Tooltip wraps the whole block so any hover/click on either line
  // shows the same hint and toggles the same state. JSX tree stays stable
  // (Tooltip + TooltipTrigger + inner div + <p> refs all constant) so the
  // ResizeObserver-based detection keeps working across re-renders.
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          role={isInteractive ? 'button' : undefined}
          tabIndex={isInteractive ? 0 : undefined}
          aria-expanded={isInteractive ? isExpanded : undefined}
          onClick={isInteractive ? toggle : undefined}
          onKeyDown={
            isInteractive
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    toggle()
                  }
                }
              : undefined
          }
          className={cn(
            isInteractive &&
              'focus-visible:ring-ring cursor-pointer rounded-sm focus-visible:ring-2 focus-visible:outline-none'
          )}
        >
          {thoughts && (
            <p
              ref={thoughtsRef}
              className={cn('text-sm leading-5', !isExpanded && 'line-clamp-2', textClassName)}
            >
              {thoughts}
            </p>
          )}
          {actionResult && (
            <p
              ref={actionRef}
              className={cn(
                'text-sm leading-5 font-bold',
                !isExpanded && 'truncate',
                textClassName
              )}
            >
              {actionResult}
            </p>
          )}
        </div>
      </TooltipTrigger>
      {isInteractive && (
        <TooltipContent>{isExpanded ? 'Click to collapse' : 'Click to expand'}</TooltipContent>
      )}
    </Tooltip>
  )
}
