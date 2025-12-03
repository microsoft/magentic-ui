/**
 * Reasoning Message Component
 *
 * Displays the agent's internal thought process in a collapsible section.
 * Header shows "Thought for Xs" (with duration) or "Thought" (without).
 * Defaults to collapsed, controlled by verbose mode.
 */

import { Brain } from 'lucide-react'
import { Markdown } from '@/components/common'
import { CollapsibleHeader } from './CollapsibleHeader'
import { useCollapsibleGroup } from '@/hooks'

// =============================================================================
// Component
// =============================================================================

export interface ReasoningMessageProps {
  groupId: string
  sessionId: number
  content: string
  /** Seconds the agent spent thinking, or null if unknown */
  thinkingSeconds: number | null
}

/**
 * Renders agent reasoning in a collapsible section.
 * Shows "Thought for Xs" header with Brain icon.
 */
export function ReasoningMessage({
  groupId,
  sessionId,
  content,
  thinkingSeconds,
}: ReasoningMessageProps) {
  const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'reasoning')

  const label =
    thinkingSeconds != null && thinkingSeconds > 0 ? `Thought for ${thinkingSeconds}s` : 'Thought'

  return (
    <div className="flex w-full flex-col">
      <CollapsibleHeader
        icon={<Brain className="size-4 shrink-0" />}
        label={label}
        isExpanded={isExpanded}
        onToggle={toggle}
      />

      {isExpanded && content && (
        <div className="pt-4 pl-6 text-sm leading-5">
          <Markdown>{content}</Markdown>
        </div>
      )}
    </div>
  )
}
