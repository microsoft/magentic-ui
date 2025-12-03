/**
 * Renders the agent's input request as one of three card variants:
 * `text_input`, `approval`, or `continuation`.
 */

import { useCallback, useMemo, useState } from 'react'
import { Check, ChevronDown, X } from 'lucide-react'
import { Markdown } from '@/components/common'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useWebSocketManager } from '@/hooks'
import { useChatStore } from '@/stores/chatStore'
import { HeaderedMessage } from './HeaderedMessage'

// =============================================================================
// Types
// =============================================================================

export interface InputRequestMessageProps {
  /** Message content from agent */
  content: string
  /** Input type: 'text_input' or 'approval' */
  inputType?: string
  /** Session ID for sending responses */
  sessionId?: number
  /** Unique message ID for persisting approval decision */
  messageId?: string
  /** Approval-specific fields */
  tool?: string
  toolArgs?: Record<string, unknown>
  category?: string
  reason?: string
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders input request message.
 * Returns null when content is empty (hides entire message).
 */
export function InputRequestMessage({
  content,
  inputType,
  sessionId,
  messageId,
  tool,
  toolArgs,
  reason,
}: InputRequestMessageProps) {
  // Approval card renders even without content (tool/reason are sufficient)
  if (inputType === 'approval' && sessionId != null) {
    return (
      <ApprovalCard
        sessionId={sessionId}
        messageId={messageId}
        tool={tool}
        toolArgs={toolArgs}
        reason={reason}
      />
    )
  }

  // Continuation card: Continue / Stop buttons + the agent's prompt text
  if (inputType === 'continuation' && sessionId != null) {
    return <ContinuationCard sessionId={sessionId} messageId={messageId} content={content} />
  }

  // Hide text input message when backend sends empty content
  if (!content) return null

  // Text input request
  return (
    <HeaderedMessage header="Input Request" headerClassName="text-status-waiting-input">
      <Markdown>{content}</Markdown>
    </HeaderedMessage>
  )
}

// =============================================================================
// Approval Card
// =============================================================================

interface ApprovalCardProps {
  sessionId: number
  messageId?: string
  tool?: string
  toolArgs?: Record<string, unknown>
  reason?: string
}

function ApprovalCard({ sessionId, messageId, tool, toolArgs, reason }: ApprovalCardProps) {
  const [responded, setResponded] = useState<'approve' | 'deny' | null>(null)
  const { sendApprovalResponse } = useWebSocketManager()
  const getSessionState = useChatStore((s) => s.getSessionState)
  const setAutoApprove = useChatStore((s) => s.setAutoApprove)
  const sessionState = getSessionState(sessionId)
  const runId = sessionState.runId ?? ''

  // Check messages for a persisted approval_response after this card
  const persistedDecision = useMemo(() => {
    if (!messageId) return null
    const messages = sessionState.messages
    const myIndex = messages.findIndex((m) => m.id === messageId)
    if (myIndex === -1) return null
    // Look at subsequent messages for an approval-response
    for (let i = myIndex + 1; i < messages.length; i++) {
      const m = messages[i]
      if (m.kind === 'approval-response') {
        return m.decision
      }
      // Skip system-status messages (they sit between request and response)
      if (m.kind !== 'system-status') break
    }
    return null
  }, [messageId, sessionState.messages])

  const decision = responded ?? persistedDecision

  const handleResponse = useCallback(
    async (d: 'approve' | 'deny') => {
      if (decision || !runId) return
      const success = await sendApprovalResponse(runId, sessionId, d, 'user')
      if (success) {
        setResponded(d)
      }
    },
    [decision, runId, sessionId, sendApprovalResponse]
  )

  const handleAutoApproveAndRespond = useCallback(
    async (scope: { scope: 'all' } | { scope: 'tool'; tool: string }) => {
      if (decision || !runId) return
      setAutoApprove(sessionId, scope)
      const success = await sendApprovalResponse(runId, sessionId, 'approve', 'user')
      if (success) {
        setResponded('approve')
      }
    },
    [decision, runId, sessionId, sendApprovalResponse, setAutoApprove]
  )

  // Approved: hide card entirely
  if (decision === 'approve') return null

  // Format the command for display
  const commandDisplay =
    tool === 'bash'
      ? String(toolArgs?.command ?? '')
      : tool
        ? `${tool}(${Object.entries(toolArgs ?? {})
            .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
            .join(', ')})`
        : ''

  return (
    <div className="border-border bg-muted rounded-xl border p-4 shadow-sm">
      {/* Title */}
      <div className="text-status-waiting-input mb-3 text-lg leading-7 font-bold">
        Approval Required
      </div>

      {/* Description */}
      <p className="text-foreground-secondary mb-2 text-sm">
        {tool === 'bash'
          ? 'The following bash command needs your approval before it can be executed:'
          : 'The following action needs your approval before it can be executed:'}
      </p>

      {/* Command */}
      {commandDisplay && (
        <div className="border-border bg-background text-foreground-alt mb-3 rounded-md border p-2.5 font-mono text-xs leading-relaxed">
          {commandDisplay}
        </div>
      )}

      {/* Reason + hint */}
      <p className="text-foreground-tertiary mb-3 text-xs">
        {reason && (
          <>
            <span className="font-bold">Reason:</span> {reason}
            <br />
          </>
        )}
        You may approve, deny, or send a message with an alternative suggestion.
      </p>

      {/* Action / Result */}
      {decision === 'deny' ? (
        <div className="text-destructive text-sm font-medium">
          {tool === 'bash' ? 'You denied the command.' : 'You denied the action.'}
        </div>
      ) : decision === 'alternative' ? (
        <div className="text-muted-foreground text-sm font-medium">
          You suggested an alternative.
        </div>
      ) : (
        <div className="flex justify-end gap-2">
          <Button variant="destructive" onClick={() => handleResponse('deny')}>
            <X className="h-3.5 w-3.5" />
            Deny
          </Button>
          {/* Split button: Approve + dropdown for auto-approve options */}
          <div className="flex gap-px">
            <Button
              variant="default"
              className="rounded-r-none"
              onClick={() => handleResponse('approve')}
            >
              <Check className="h-3.5 w-3.5" />
              Approve
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="default" className="rounded-l-none pr-2.5 pl-2">
                  <ChevronDown className="h-4 w-4" />
                  <span className="sr-only">Auto-approve options</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {tool && (
                  <DropdownMenuItem
                    onClick={() => handleAutoApproveAndRespond({ scope: 'tool', tool })}
                  >
                    Always approve <span className="font-bold">{tool}</span> in this session
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => handleAutoApproveAndRespond({ scope: 'all' })}>
                  Always approve all tools in this session
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Continuation Card
// =============================================================================

interface ContinuationCardProps {
  sessionId: number
  messageId?: string
  content: string
}

/** Continue/Stop card shown when an agent hits its per-batch `max_rounds` cap. */
function ContinuationCard({ sessionId, messageId, content }: ContinuationCardProps) {
  const [responded, setResponded] = useState<'continue' | 'stop' | null>(null)
  const { sendContinuationResponse } = useWebSocketManager()
  const getSessionState = useChatStore((s) => s.getSessionState)
  const sessionState = getSessionState(sessionId)
  const runId = sessionState.runId ?? ''

  const persistedDecision = useMemo<'continue' | 'stop' | null>(() => {
    if (!messageId) return null
    const messages = sessionState.messages
    const myIndex = messages.findIndex((m) => m.id === messageId)
    if (myIndex === -1) return null
    for (let i = myIndex + 1; i < messages.length; i++) {
      const m = messages[i]
      if (m.kind === 'continuation-response') {
        return m.decision
      }
      if (m.kind !== 'system-status') break
    }
    return null
  }, [messageId, sessionState.messages])

  const decision = responded ?? persistedDecision

  const handleResponse = useCallback(
    async (choice: 'continue' | 'stop') => {
      if (decision || !runId) return
      const success = await sendContinuationResponse(runId, sessionId, choice)
      if (success) setResponded(choice)
    },
    [decision, runId, sessionId, sendContinuationResponse]
  )

  // Continue: hide entirely (matches Approve behavior).
  if (decision === 'continue') return null

  return (
    <div className="border-border bg-muted rounded-xl border p-4 shadow-sm">
      <div className="text-status-waiting-input mb-3 text-lg leading-7 font-bold">Keep going?</div>
      {content && (
        <div className="text-foreground-secondary mb-3 text-sm">
          <Markdown>{content}</Markdown>
        </div>
      )}

      {/* Action / Result */}
      {decision === 'stop' ? (
        <div className="text-destructive text-sm font-medium">You stopped here.</div>
      ) : (
        <div className="flex justify-end gap-2">
          <Button variant="destructive" onClick={() => handleResponse('stop')}>
            <X className="h-3.5 w-3.5" />
            Stop
          </Button>
          <Button variant="default" onClick={() => handleResponse('continue')}>
            <Check className="h-3.5 w-3.5" />
            Continue
          </Button>
        </div>
      )}
    </div>
  )
}
