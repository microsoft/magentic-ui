/**
 * Orchestrator Tool Message Component
 *
 * Displays OmniAgent tool_call messages with collapsible args and optional result.
 * Always rendered in the message list (not just as a shimmer placeholder).
 *
 * Two states:
 * - Active (no resultContent): shimmer header with progressive tense, expandable args
 * - Complete (with resultContent): past tense header, expandable args + "Result" section
 */

import { CollapsibleHeader } from './CollapsibleHeader'
import { PreBlock } from './PreBlock'
import { useCollapsibleGroup } from '@/hooks'
import { getOrchestratorToolLabel, getOrchestratorToolIcon } from '@/lib/messages/constants'

// =============================================================================
// Tool Args Display
// =============================================================================

/** Check if a string value contains multiple lines */
function isMultiLine(value: unknown): boolean {
  return typeof value === 'string' && value.includes('\n')
}

function ToolArgsDisplay({ toolArgs }: { toolArgs: Record<string, unknown> }) {
  const entries = Object.entries(toolArgs)
  if (entries.length === 0) return null

  return (
    <div className="space-y-1">
      {entries.map(([key, value]) => {
        const strValue = String(value)
        if (isMultiLine(value)) {
          return (
            <div key={key}>
              <div className="text-muted-foreground mb-2 font-semibold">{key}:</div>
              <PreBlock>{strValue}</PreBlock>
            </div>
          )
        }
        return (
          <div key={key} className="flex gap-1.5">
            <span className="text-muted-foreground shrink-0 font-semibold">{key}:</span>
            <code className="bg-muted min-w-0 rounded px-1 py-0.5 font-mono text-xs wrap-break-word">
              {strValue}
            </code>
          </div>
        )
      })}
    </div>
  )
}

// =============================================================================
// Component
// =============================================================================

export interface OrchestratorToolMessageProps {
  tool: string
  toolArgs: Record<string, unknown>
  /** When provided, the tool has completed and this is the result content */
  resultContent?: string
  groupId: string
  sessionId: number
  /** How this tool call was approved: 'user' | 'auto_session' | 'auto_policy' | undefined */
  approvalStatus?: string
}

/**
 * Renders an orchestrator tool call with collapsible args and optional result.
 * - Active: shimmer header (progressive tense), expandable args
 * - Complete: static header (past tense), expandable args + result section
 */
export function OrchestratorToolMessage({
  tool,
  toolArgs,
  resultContent,
  groupId,
  sessionId,
  approvalStatus,
}: OrchestratorToolMessageProps) {
  const isComplete = resultContent !== undefined
  const label = getOrchestratorToolLabel(tool, !isComplete)
  const icon = getOrchestratorToolIcon(tool)
  const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'toolCall')
  // delegate_cua is a placeholder header — don't show its args (task param)
  const displayArgs = tool === 'delegate_cua' ? {} : toolArgs
  const hasContent = Object.keys(displayArgs).length > 0 || isComplete

  return (
    <div className="flex w-full flex-col">
      {hasContent ? (
        <CollapsibleHeader
          icon={icon}
          label={label}
          isExpanded={isExpanded}
          onToggle={toggle}
          isActive={!isComplete}
        />
      ) : (
        <CollapsibleHeader
          icon={icon}
          label={label}
          isExpanded={false}
          disabled
          isActive={!isComplete}
        />
      )}

      {isExpanded && hasContent && (
        <div className="space-y-3 pt-3 pl-6 text-sm leading-5">
          <ToolArgsDisplay toolArgs={displayArgs} />

          {approvalStatus && (
            <div className="text-muted-foreground text-xs font-bold tracking-wider uppercase">
              {approvalStatus === 'user' && '✓ Approved by user'}
              {approvalStatus === 'auto_session' && '✓ Auto-approved for the session'}
              {approvalStatus === 'auto_policy' && '✓ Auto-approved by policy'}
              {approvalStatus === 'auto_safe' && '✓ Safe action; no approval needed'}
            </div>
          )}

          {isComplete && resultContent && (
            <>
              <div className="text-muted-foreground text-xs font-bold tracking-wider uppercase">
                Result
              </div>
              <PreBlock>{resultContent}</PreBlock>
            </>
          )}
        </div>
      )}
    </div>
  )
}
