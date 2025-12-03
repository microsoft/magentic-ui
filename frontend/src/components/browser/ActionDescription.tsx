/**
 * Action Description Component
 *
 * Displays CUA action thoughts and result inside the expanded browser view.
 *
 * Layout responsibilities live here:
 * - Container has a minimum height (no shrink jitter); grows when content expands
 * - Bottom-anchored so the text stays right above the toolbar; expanded content
 *   grows upward.
 *
 * Per-block interaction (click-to-expand, tooltip hint, etc.) lives in
 * `ExpandableActionText`, which is shared with `DescriptionOverlay`.
 */

import { ExpandableActionText } from './ExpandableActionText'

// =============================================================================
// Types
// =============================================================================

interface ActionDescriptionProps {
  thoughts?: string
  actionResult?: string
}

// =============================================================================
// Component
// =============================================================================

export function ActionDescription({ thoughts, actionResult }: ActionDescriptionProps) {
  return (
    <div className="flex min-h-[68px] flex-col justify-end">
      <ExpandableActionText
        thoughts={thoughts}
        actionResult={actionResult}
        textClassName="text-foreground"
      />
    </div>
  )
}
