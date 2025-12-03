/**
 * Code Execution Message Component
 *
 * Displays code execution requests (code_to_execute) with optional results (tool_result).
 * Code and language are pre-parsed by lib/messages/parser.ts.
 *
 * Display:
 * - Without result: "Executing code" (in progress)
 * - With result: "Executed code" (completed)
 *
 * TODO: Investigate whether this component and the code-execution / codeResultContent
 * merge logic (in messageListUtils.shouldMerge) are still triggered by OmniAgent.
 */

import { Code } from 'lucide-react'
import { Markdown } from '@/components/common'
import { CodeBlock } from './CodeBlock'
import { CollapsibleHeader } from './CollapsibleHeader'
import { useCollapsibleGroup } from '@/hooks'

export interface CodeExecutionMessageProps {
  groupId: string
  sessionId: number
  /** Clean code (fence wrapper already stripped by parser) */
  codeContent: string
  /** Language from code fence (e.g. 'python') */
  language: string
  /** Clean result text (prefix already stripped by parser) */
  resultContent?: string
}

/**
 * Renders a code execution message showing code and optional result.
 * - Without result: "Executing code" (in progress)
 * - With result: "Executed code" (completed)
 */
export function CodeExecutionMessage({
  groupId,
  sessionId,
  codeContent,
  language,
  resultContent,
}: CodeExecutionMessageProps) {
  const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'toolCall')
  const displayName = resultContent ? 'Executed code' : 'Executing code'

  return (
    <div className="flex w-full flex-col">
      <CollapsibleHeader
        icon={<Code className="size-4 shrink-0" />}
        label={displayName}
        isExpanded={isExpanded}
        onToggle={toggle}
        isActive={resultContent === undefined}
      />

      {isExpanded && (
        <div className="flex flex-col gap-4 pt-4 pl-6 text-sm leading-5">
          {codeContent && <CodeBlock language={language}>{codeContent}</CodeBlock>}
          {resultContent && <Markdown>{resultContent}</Markdown>}
        </div>
      )}
    </div>
  )
}
