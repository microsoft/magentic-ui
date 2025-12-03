/**
 * Message Renderer
 *
 * Central component for rendering individual message types.
 * Uses ParsedMessage with discriminated union by 'kind'.
 *
 * Handles: user, text, summary, error, code-execution, tool-result, orchestrator-tool,
 *          cua-non-browser, reasoning, system-status, input-request, final-answer
 *
 * Does NOT handle (processed elsewhere):
 * - cua-browser, screenshot: grouped into CuaMessage in messageListUtils
 * - browser-address, internal: filtered out in messageListUtils
 */

import { memo } from 'react'
import { Markdown } from '@/components/common'
import { FileChip, FolderChip } from '@/components/common'
import {
  CodeExecutionMessage,
  OrchestratorToolMessage,
  ToolResultMessage,
  FinalAnswerMessage,
  ReasoningMessage,
  SystemStatusMessage,
  InputRequestMessage,
  ErrorMessage,
  FileMessage,
  MemorizedFactMessage,
} from './messages'
import { type ParsedMessage } from '@/types'
import { isPreviewable, openFileOrDownload, triggerFileDownload } from '@/lib/fileUtils'
import type { FileInfo } from '@/types'

// =============================================================================
// Props
// =============================================================================

export interface MessageRendererProps {
  /** Parsed message with kind discriminant */
  message: ParsedMessage
  /** Session ID for state tracking */
  sessionId: number
  /** Reference for scroll tracking */
  ref?: React.Ref<HTMLDivElement>
  /** Code result content (for merging code-execution with tool-result) */
  codeResultContent?: string
  /** Tool result content (for merging orchestrator-tool with tool-result) */
  toolResultContent?: string
  /** Called when user clicks a file chip to preview */
  onFilePreview?: (file: FileInfo) => void
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * Renders a message based on its kind.
 * Handles: user, text, code execution, final answer, summary, error, etc.
 *
 * Wrapped in React.memo for performance optimization with large message lists.
 * Since old messages' object references don't change (store uses shallow copy),
 * memo can skip re-rendering unchanged messages when new messages arrive.
 */
export const MessageRenderer = memo(function MessageRenderer({
  message,
  sessionId,
  ref,
  codeResultContent,
  toolResultContent,
  onFilePreview,
}: MessageRendererProps) {
  // User messages always use UserMessageBubble
  if (message.kind === 'user') {
    return (
      <div ref={ref} className="flex w-full flex-col items-end gap-2">
        <div className="flex w-full justify-end pl-16">
          <div className="bg-secondary rounded-lg px-4 py-3 shadow-sm">
            <div className="text-secondary-foreground text-base leading-6">
              <TextContent content={message.content} />
            </div>
          </div>
        </div>
        {/* File/folder chips below user message (right-aligned, tight spacing) */}
        {(!!message.mountedFolder ||
          (message.attachedFiles && message.attachedFiles.length > 0)) && (
          <div className="flex w-full flex-wrap justify-end gap-2">
            {message.attachedFiles?.map((file, i) => (
              <FileChip
                key={`${file.name}-${i}`}
                name={file.name}
                extension={file.extension}
                context="chat"
                tooltip={isPreviewable(file.name) ? 'Preview' : 'Download'}
                {...(file.uploadStatus ? { status: file.uploadStatus } : {})}
                onClick={() => openFileOrDownload(file, onFilePreview)}
                onDownload={() => triggerFileDownload(file)}
              />
            ))}

            {message.mountedFolder && (
              <FolderChip name={message.mountedFolder.name} path={message.mountedFolder.path} />
            )}
          </div>
        )}
      </div>
    )
  }

  // Assistant messages - render based on kind
  const content = renderMessageContent(
    message,
    sessionId,
    codeResultContent,
    toolResultContent,
    onFilePreview
  )

  // Don't render container if content is null/empty (e.g., non-browser-tool with empty thoughts)
  if (!content) return null

  return <AssistantMessageContainer ref={ref}>{content}</AssistantMessageContainer>
})

// =============================================================================
// Content Rendering by Kind
// =============================================================================

function renderMessageContent(
  message: ParsedMessage,
  sessionId: number,
  codeResultContent?: string,
  toolResultContent?: string,
  onFilePreview?: (file: FileInfo) => void
): React.ReactNode {
  switch (message.kind) {
    case 'code-execution':
      return (
        <CodeExecutionMessage
          groupId={message.id}
          sessionId={sessionId}
          codeContent={message.code}
          language={message.language}
          resultContent={codeResultContent}
        />
      )

    case 'tool-result':
      // Standalone tool result (not paired with code-execution)
      return (
        <ToolResultMessage
          groupId={message.id}
          sessionId={sessionId}
          toolName={message.toolName}
          resultContent={message.result}
        />
      )

    case 'final-answer':
      return <FinalAnswerMessage content={message.content} />

    case 'system-status':
      if (!message.content) return null
      return <SystemStatusMessage status={message.status} content={message.content} />

    case 'input-request':
      // Approval cards render even without content (tool/reason metadata suffice)
      if (!message.content && message.inputType !== 'approval') return null
      return (
        <InputRequestMessage
          content={message.content}
          inputType={message.inputType}
          sessionId={sessionId}
          messageId={message.id}
          tool={message.tool}
          toolArgs={message.toolArgs}
          category={message.category}
          reason={message.reason}
        />
      )

    case 'summary':
    case 'text':
      if (!message.content) return null
      return <TextContent content={message.content} />

    case 'error':
      return <ErrorMessage content={message.content} />

    case 'reasoning':
      return (
        <ReasoningMessage
          groupId={message.id}
          sessionId={sessionId}
          content={message.content}
          thinkingSeconds={message.thinkingSeconds}
        />
      )

    case 'cua-non-browser':
      // pause_and_memorize_fact: collapsible header "Memorized a fact" with the fact in the body.
      if (message.tool === 'pause_and_memorize_fact') {
        if (!message.toolArgs.fact) return null
        return (
          <MemorizedFactMessage
            groupId={message.id}
            sessionId={sessionId}
            fact={message.toolArgs.fact}
          />
        )
      }
      // read_page_answer_question / run_command are folded into the CUA group.
      // Other non-browser tools (e.g., terminate) display their thoughts here.
      if (!message.toolArgs.thoughts) return null
      return <TextContent content={message.toolArgs.thoughts} />

    case 'orchestrator-tool':
      return (
        <OrchestratorToolMessage
          tool={message.tool}
          toolArgs={message.toolArgs}
          resultContent={toolResultContent}
          groupId={message.id}
          sessionId={sessionId}
          approvalStatus={message.approvalStatus}
        />
      )

    case 'file':
      return (
        <FileMessage
          files={message.files}
          summary={message.summary}
          uploadedFiles={message.uploadedFiles}
          onFilePreview={onFilePreview}
        />
      )

    // Internal messages (internal, browser-address) are filtered in messageListUtils
    // Screenshot and cua-browser are handled in CUA groups
    default:
      return null
  }
}

// =============================================================================
// Content Components
// =============================================================================

/** Text/Markdown content - returns null for empty content */
function TextContent({ content }: { content: string }) {
  if (!content) return null
  return <Markdown>{content}</Markdown>
}

// =============================================================================
// Layout Containers
// =============================================================================

interface ContainerProps {
  children: React.ReactNode
  ref?: React.Ref<HTMLDivElement>
}

/** Assistant message container - left-aligned, flat style */
function AssistantMessageContainer({ children, ref }: ContainerProps) {
  return (
    <div ref={ref} className="flex w-full">
      <div className="min-w-0 pr-16">
        <div className="text-foreground text-base leading-6">{children}</div>
      </div>
    </div>
  )
}
