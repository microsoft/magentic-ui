/**
 * Reasoning Placeholder
 *
 * Disabled (non-interactive) reasoning card with a shimmer "Thinking…"
 * label. Rendered in the chat list while the model is streaming back
 * its reply but hasn't finished, so the user has a visible signal that
 * something is happening. Replaced by the real ReasoningMessage when
 * the LLM call completes and the reasoning content arrives.
 */

import { Brain } from 'lucide-react'
import { CollapsibleHeader } from './CollapsibleHeader'

export function ReasoningPlaceholder() {
  return (
    <div className="flex w-full flex-col">
      <CollapsibleHeader
        icon={<Brain className="size-4 shrink-0" />}
        label="Thinking…"
        isExpanded={false}
        disabled
        isActive
      />
    </div>
  )
}
