/**
 * Tool Result Message Component
 *
 * Displays standalone tool results from OmniAgent (not merged with orchestrator-tool).
 * This is used for non-adjacent tool results, e.g., delegate_cua results that arrive
 * after CUA browser messages in between.
 *
 * Uses centralized labels and icons from constants.ts.
 */

import { Markdown } from '@/components/common'
import { CollapsibleHeader } from './CollapsibleHeader'
import { PreBlock } from './PreBlock'
import { useCollapsibleGroup } from '@/hooks'
import { getOrchestratorToolLabel, getOrchestratorToolIcon } from '@/lib/messages/constants'

// =============================================================================
// Component
// =============================================================================

export interface ToolResultMessageProps {
  groupId: string
  sessionId: number
  toolName: string | undefined
  resultContent: string
}

/**
 * Renders a standalone tool result with collapsible header.
 * The header label changes based on the tool that produced the result.
 */
export function ToolResultMessage({
  groupId,
  sessionId,
  toolName,
  resultContent,
}: ToolResultMessageProps) {
  const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'toolCall')
  const label = getOrchestratorToolLabel(toolName, false)
  const icon = getOrchestratorToolIcon(toolName)

  return (
    <div className="flex w-full flex-col">
      <CollapsibleHeader icon={icon} label={label} isExpanded={isExpanded} onToggle={toggle} />

      {isExpanded && resultContent && (
        <div className="pt-3 pl-6 text-sm leading-5">
          {toolName === 'delegate_cua' ? (
            <Markdown>{resultContent}</Markdown>
          ) : (
            <PreBlock>{resultContent}</PreBlock>
          )}
        </div>
      )}
    </div>
  )
}
