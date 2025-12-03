/**
 * DescriptionOverlay Component
 *
 * Semi-transparent floating overlay inside the Embedded browser viewer area.
 * Shows CUA action thoughts and result text over the browser/screenshot.
 *
 * Truncated content is click-to-expand with a tooltip hint, mirroring the
 * behavior in `ActionDescription` (expanded view) — both share
 * `ExpandableActionText`.
 */

import { cn } from '@/lib/utils'
import { ExpandableActionText } from './ExpandableActionText'

// =============================================================================
// Types
// =============================================================================

interface DescriptionOverlayProps {
  /** Current action planned thought */
  thoughts?: string
  /** Current action result text */
  actionResult?: string
  /** Whether there's any action description content */
  hasContent: boolean
}

// =============================================================================
// Component
// =============================================================================

export function DescriptionOverlay({
  thoughts,
  actionResult,
  hasContent,
}: DescriptionOverlayProps) {
  if (!hasContent) return null

  return (
    <div
      className={cn(
        // Position: bottom of viewer area with 8px margin
        'absolute inset-x-2 bottom-2',
        // Appearance: frosted glass with accent for contrast (neutral-200/800)
        'bg-accent/75 rounded-xl p-2 backdrop-blur-md',
        // Prevent click-through to VNC canvas
        'pointer-events-auto'
      )}
    >
      <ExpandableActionText
        thoughts={thoughts}
        actionResult={actionResult}
        textClassName="text-card-foreground"
      />
    </div>
  )
}
