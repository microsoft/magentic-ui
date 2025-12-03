/**
 * Memorized Fact Message Component
 *
 * Renders a `pause_and_memorize_fact` action as a collapsible section,
 * mirroring the "Used web browser" header pattern. Header reads
 * "Memorized a fact"; expanded body shows the fact text.
 */

import { NotebookPen } from 'lucide-react'
import { CollapsibleHeader } from './CollapsibleHeader'
import { useCollapsibleGroup } from '@/hooks'

export interface MemorizedFactMessageProps {
  groupId: string
  sessionId: number
  fact: string
}

export function MemorizedFactMessage({ groupId, sessionId, fact }: MemorizedFactMessageProps) {
  const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'toolCall')

  return (
    <div className="flex w-full flex-col">
      <CollapsibleHeader
        icon={<NotebookPen className="size-4 shrink-0" />}
        label="Memorized a fact"
        isExpanded={isExpanded}
        onToggle={toggle}
      />

      {isExpanded && fact && (
        <div className="text-foreground pt-2 pl-6 text-sm break-words">{fact}</div>
      )}
    </div>
  )
}
