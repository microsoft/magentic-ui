/**
 * Message list utility functions
 *
 * Pure functions for message pairing and grouping logic,
 * extracted from MessageList.tsx for testing.
 */

import {
  type ParsedMessage,
  type SessionStatus,
  isParsedInternalMessage,
  isCuaBrowserMessage,
} from '@/types'

import { exceedsChatGap } from '@/lib/timeFormat'

import { type CuaAction, type ToolArgs } from './messages'

// =============================================================================
// Types - Render Items
// =============================================================================

/** Result from collectScreenshotActions */
export interface ScreenshotActionsResult {
  /** CUA actions that have screenshots (for progress bar / playback) */
  completedActions: CuaAction[]
  /** The most recent action that doesn't have a screenshot yet (for live display) */
  pendingAction: CuaAction | null
  /** Whether there are non-CUA messages after the last CUA action (hides live action info) */
  hasMessageAfterLastCua: boolean
}

/** Union type for all renderable items */
export type RenderItem =
  | {
      kind: 'message'
      message: ParsedMessage
      codeResultContent?: string
      toolResultContent?: string
    }
  | {
      kind: 'cua-group'
      actions: CuaAction[]
      groupId: string
      canUseProgressiveTense: boolean
      /** ISO timestamp of the first action in the group; used for chat timestamp separators. */
      firstTimestamp?: string
    }
  | { kind: 'cua-placeholder'; groupId: string }
  | { kind: 'browser-embed'; groupId: string }
  | {
      /** Inline timestamp divider rendered between messages when the gap exceeds `CHAT_TIMESTAMP_GAP_MS`. */
      kind: 'timestamp'
      id: string
      iso: string
    }

// =============================================================================
// Message Pairing Logic
//
// Two functions process messages with overlapping logic:
// - collectScreenshotActions: lightweight, only extracts screenshot actions (for BrowserExpanded)
// - computeRenderItems: full processing with grouping/merging (for MessageList)
//
// Trade-off: Some duplicate traversal, but keeps data flow simple.
// Merging them would require passing screenshotActions through multiple component layers.
// =============================================================================

/**
 * Collect CUA actions with screenshots for BrowserExpanded playback bar.
 * @param messages - Parsed messages to process
 */
export function collectScreenshotActions(messages: ParsedMessage[]): ScreenshotActionsResult {
  const filteredMessages = messages.filter((msg) => !isParsedInternalMessage(msg))
  const completedActions: CuaAction[] = []
  let pendingAction: CuaAction | null = null
  let lastCuaIndex = -1 // Track last CUA action (browser-tool or screenshot) index

  for (let i = 0; i < filteredMessages.length; i++) {
    const msg = filteredMessages[i]

    // Browser tool message: create pending action
    if (isCuaBrowserMessage(msg)) {
      // If there was a pending action without screenshot, discard it
      pendingAction = {
        messageId: msg.id,
        rawContent: msg.toolArgs.thoughts ?? '',
        tool: msg.tool,
        toolArgs: msg.toolArgs as ToolArgs,
        isComplete: false,
      }
      lastCuaIndex = i
      continue
    }

    // Screenshot message: associate with pending action
    if (msg.kind === 'screenshot' && pendingAction) {
      if (msg.imageUrl) {
        pendingAction.screenshotUrl = msg.imageUrl
        pendingAction.isComplete = true
      }
      if (msg.actionResult) {
        pendingAction.actionResult = msg.actionResult
      }
      // Only add if we have a screenshot URL
      if (pendingAction.screenshotUrl) {
        completedActions.push(pendingAction)
      }
      pendingAction = null
      lastCuaIndex = i
    }
  }

  // Check if there are non-internal messages after the last CUA action
  const hasMessageAfterLastCua = lastCuaIndex >= 0 && lastCuaIndex < filteredMessages.length - 1

  return { completedActions, pendingAction, hasMessageAfterLastCua }
}

/**
 * Check if two adjacent messages should be merged.
 * Returns true if current is code-execution and next is tool-result with execute_code tool.
 */
export function shouldMerge(current: ParsedMessage, next: ParsedMessage): boolean {
  if (current.kind !== 'code-execution') return false
  return next.kind === 'tool-result' && next.toolName === 'execute_code'
}

/**
 * Check if an orchestrator-tool message should merge with the next tool-result.
 * Only merges when adjacent — delegate_cua results typically arrive after CUA messages,
 * so they won't merge and will render as standalone ToolResultMessage.
 */
export function shouldMergeOrchestratorTool(current: ParsedMessage, next: ParsedMessage): boolean {
  if (current.kind !== 'orchestrator-tool') return false
  if (next.kind !== 'tool-result') return false
  return !!current.toolCallId && current.toolCallId === next.toolCallId
}

/**
 * Compute render items for MessageList, with CUA grouping and browser embed.
 * @param messages - Parsed messages to process
 * @param novncUrl - noVNC WebSocket URL (enables live VNC if provided)
 * @param hasScreenshots - Whether screenshot actions exist (enables screenshot-only browser embed)
 */
export function computeRenderItems(
  messages: ParsedMessage[],
  novncUrl: string | null | undefined,
  hasScreenshots = false
): RenderItem[] {
  // Always filter out internal messages (they're logged to console instead)
  // Also filter out approved approval-type input-request messages
  const approvedInputRequestIds = new Set<string>()
  let lastApprovalRequestId: string | null = null
  for (const msg of messages) {
    if (msg.kind === 'input-request' && (msg as { inputType?: string }).inputType === 'approval') {
      lastApprovalRequestId = msg.id
    } else if (
      msg.kind === 'approval-response' &&
      (msg as { decision: string }).decision === 'approve' &&
      lastApprovalRequestId
    ) {
      approvedInputRequestIds.add(lastApprovalRequestId)
      lastApprovalRequestId = null
    } else if (msg.kind !== 'system-status') {
      lastApprovalRequestId = null
    }
  }

  // Hide settled "Continue" continuation cards (and their bracketing
  // awaiting_input / active system-status frames) so consecutive CUA
  // actions stay in one browser group across the continuation. Stop
  // cards remain visible.
  const settledContinuationIds = new Set<string>()
  let lastAwaitingInputId: string | null = null
  let pendingContinuationRequestId: string | null = null
  let pendingContinuationAwaitingInputId: string | null = null
  let collectNextActiveFrame = false
  for (const msg of messages) {
    if (msg.kind === 'system-status') {
      const status = (msg as { status?: string }).status
      if (collectNextActiveFrame && status === 'active') {
        settledContinuationIds.add(msg.id)
        collectNextActiveFrame = false
        continue
      }
      lastAwaitingInputId = status === 'awaiting_input' ? msg.id : null
      continue
    }
    if (
      msg.kind === 'input-request' &&
      (msg as { inputType?: string }).inputType === 'continuation'
    ) {
      pendingContinuationRequestId = msg.id
      pendingContinuationAwaitingInputId = lastAwaitingInputId
      lastAwaitingInputId = null
      collectNextActiveFrame = false
      continue
    }
    if (msg.kind === 'continuation-response' && pendingContinuationRequestId) {
      if (msg.decision === 'continue') {
        settledContinuationIds.add(pendingContinuationRequestId)
        if (pendingContinuationAwaitingInputId) {
          settledContinuationIds.add(pendingContinuationAwaitingInputId)
        }
        collectNextActiveFrame = true
      }
      pendingContinuationRequestId = null
      pendingContinuationAwaitingInputId = null
      lastAwaitingInputId = null
      continue
    }
    lastAwaitingInputId = null
    pendingContinuationRequestId = null
    pendingContinuationAwaitingInputId = null
    collectNextActiveFrame = false
  }

  const filteredMessages = messages.filter(
    (msg) =>
      !isParsedInternalMessage(msg) &&
      !approvedInputRequestIds.has(msg.id) &&
      !settledContinuationIds.has(msg.id)
  )

  const items: RenderItem[] = []
  let currentCuaGroup: CuaAction[] = []
  let cuaGroupStartId: string | null = null
  /** Timestamp of the first message that started the current CUA group. */
  let cuaGroupStartTimestamp: string | null = null
  /** Track items index of the last CUA group for browser embed placement */
  let lastCuaGroupItemIndex = -1
  /** Track seen file URLs to deduplicate file messages (show each file only once) */
  const seenFileUrls = new Set<string>()
  /**
   * Map tool_call_id → tool name from orchestrator-tool messages so standalone
   * tool-results (e.g., delegate_cua, when CUA messages prevent merging) can
   * recover their tool name from the originating tool_call rather than falling
   * back to a generic "Running tool" label.
   */
  const toolCallIdToName = new Map<string, string>()
  for (const msg of filteredMessages) {
    if (msg.kind === 'orchestrator-tool' && msg.toolCallId) {
      toolCallIdToName.set(msg.toolCallId, msg.tool)
    }
  }

  const flushCuaGroup = () => {
    if (currentCuaGroup.length > 0) {
      lastCuaGroupItemIndex = items.length
      items.push({
        kind: 'cua-group',
        actions: [...currentCuaGroup],
        groupId: `cua-${cuaGroupStartId}`,
        canUseProgressiveTense: false, // Will be updated after all items are processed
        firstTimestamp: cuaGroupStartTimestamp ?? undefined,
      })

      currentCuaGroup = []
      cuaGroupStartId = null
      cuaGroupStartTimestamp = null
    }
  }

  for (let i = 0; i < filteredMessages.length; i++) {
    const current = filteredMessages[i]
    const next = filteredMessages[i + 1]

    // Handle CUA actions (browser tools, plus read_page_answer_question / run_command).
    // pause_and_memorize_fact, terminate, and stop render standalone outside the group.
    const isInlineNonBrowser =
      current.kind === 'cua-non-browser' &&
      (current.tool === 'read_page_answer_question' || current.tool === 'run_command')
    if (isCuaBrowserMessage(current) || isInlineNonBrowser) {
      // Mark previous action as complete when a new action arrives
      if (currentCuaGroup.length > 0) {
        currentCuaGroup[currentCuaGroup.length - 1].isComplete = true
      } else {
        cuaGroupStartId = current.id
        cuaGroupStartTimestamp = current.timestamp
      }

      currentCuaGroup.push({
        messageId: current.id,
        rawContent: current.toolArgs.thoughts ?? '',
        tool: current.tool,
        toolArgs: current.toolArgs as ToolArgs,
        // Inline non-browser actions never produce a screenshot — mark complete so they don't block tense
        isComplete: isInlineNonBrowser,
      })
      continue
    }

    // Non-CUA message (including screenshot): mark last action as complete
    if (currentCuaGroup.length > 0) {
      currentCuaGroup[currentCuaGroup.length - 1].isComplete = true

      // If it's a screenshot, associate its URL and actionResult with the previous action
      if (current.kind === 'screenshot') {
        if (current.imageUrl) {
          currentCuaGroup[currentCuaGroup.length - 1].screenshotUrl = current.imageUrl
        }
        // actionResult is the completed action description (past tense) from screenshot message
        if (current.actionResult) {
          currentCuaGroup[currentCuaGroup.length - 1].actionResult = current.actionResult
        }
      }

      // Errors during a CUA flow: fold in as inline action rows so they don't
      // break the visual grouping with a separate styled error block.
      // Carry the last real action's tool info so consecutive retry errors
      // still show "Error Visiting ..." instead of just "Error".
      if (current.kind === 'error' && current.content) {
        const failed = [...currentCuaGroup].reverse().find((a) => a.tool)
        currentCuaGroup.push({
          messageId: current.id,
          rawContent: current.content,
          tool: failed?.tool,
          toolArgs: failed?.toolArgs,
          isComplete: true,
          errorContent: current.content,
        })
        continue
      }
    }

    // Screenshot is part of CUA group, don't flush
    if (current.kind === 'screenshot') {
      continue
    }

    // Other non-CUA messages end the CUA group
    flushCuaGroup()

    // Handle orchestrator-tool messages (OmniAgent tool_call)
    // Always render. If adjacent tool-result matches, merge into one item.
    if (current.kind === 'orchestrator-tool') {
      if (next && shouldMergeOrchestratorTool(current, next)) {
        const resultContent = next.kind === 'tool-result' ? next.result : ''
        items.push({
          kind: 'message',
          message: current,
          toolResultContent: resultContent,
        })
        i++ // Skip the tool-result message
      } else {
        items.push({ kind: 'message', message: current })
      }
      continue
    }

    // Handle code execution merging
    if (next && shouldMerge(current, next)) {
      // Get result content from tool-result message
      const resultContent = next.kind === 'tool-result' ? next.result : ''
      items.push({
        kind: 'message',
        message: current,
        codeResultContent: resultContent,
      })
      i++ // Skip the tool-result message
      continue
    }

    // Standalone tool result (e.g., non-adjacent OmniAgent results like delegate_cua)
    // Don't skip — let MessageRenderer display it
    if (current.kind === 'tool-result') {
      // If the parser couldn't extract a tool name from the content, recover it
      // from the matching orchestrator-tool via tool_call_id.
      let resolved = current
      if (!current.toolName && current.toolCallId) {
        const lookupName = toolCallIdToName.get(current.toolCallId)
        if (lookupName) {
          resolved = { ...current, toolName: lookupName }
        }
      }
      items.push({ kind: 'message', message: resolved })
      continue
    }

    // File messages: deduplicate by URL — only show each file the first time
    // it appears. The end-of-run summary (`message.summary === true`) is
    // exempt from this dedup so its "Files the agent created or modified"
    // list is shown beneath the final answer even though every file has
    // been seen earlier.
    if (current.kind === 'file') {
      if (current.summary) {
        items.push({ kind: 'message', message: current })
        continue
      }
      const newFiles = current.files.filter((f) => !seenFileUrls.has(f.url))
      newFiles.forEach((f) => seenFileUrls.add(f.url))
      if (newFiles.length > 0) {
        // Create a new message with only unseen files
        const deduped =
          newFiles.length === current.files.length ? current : { ...current, files: newFiles }
        items.push({ kind: 'message', message: deduped })
      }
      // Skip if all files were already seen
      continue
    }

    // Regular message
    items.push({ kind: 'message', message: current })
  }

  // Flush any remaining CUA group
  flushCuaGroup()

  // Remove delegate_cua placeholder once CUA groups exist (CUA group replaces it)
  if (lastCuaGroupItemIndex >= 0) {
    for (let i = items.length - 1; i >= 0; i--) {
      const item = items[i]
      if (
        item.kind === 'message' &&
        item.message.kind === 'orchestrator-tool' &&
        item.message.tool === 'delegate_cua' &&
        item.toolResultContent === undefined
      ) {
        items.splice(i, 1)
        if (i <= lastCuaGroupItemIndex) {
          lastCuaGroupItemIndex--
        }
      }
    }
  }

  // Update canUseProgressiveTense for the last CUA group (regardless of browser embed)
  let lastCuaGroupIndex = -1
  for (let i = items.length - 1; i >= 0; i--) {
    if (items[i].kind === 'cua-group') {
      lastCuaGroupIndex = i
      break
    }
  }

  if (lastCuaGroupIndex >= 0) {
    const lastCuaGroup = items[lastCuaGroupIndex]
    if (lastCuaGroup.kind === 'cua-group') {
      // Only allow progressive tense if there are no message items after it
      const hasMessageAfter = items.slice(lastCuaGroupIndex + 1).some((it) => it.kind === 'message')
      lastCuaGroup.canUseProgressiveTense = !hasMessageAfter
    }
  }

  if (novncUrl || hasScreenshots) {
    // Stable groupId prevents VNC reconnection when CUA groups change.
    const groupId = 'browser-embed'

    if (lastCuaGroupItemIndex >= 0) {
      items.splice(lastCuaGroupItemIndex + 1, 0, {
        kind: 'browser-embed',
        groupId,
      })
    } else {
      const lastItem = items[items.length - 1]
      const hasDelegateCuaPlaceholder =
        lastItem?.kind === 'message' &&
        lastItem.message.kind === 'orchestrator-tool' &&
        lastItem.message.tool === 'delegate_cua'

      if (hasDelegateCuaPlaceholder) {
        // delegate_cua already signals browsing intent; embed under it.
        items.push({
          kind: 'browser-embed',
          groupId,
        })
      } else if (hasScreenshots) {
        items.push({
          kind: 'cua-placeholder',
          groupId: 'cua-placeholder',
        })
        items.push({
          kind: 'browser-embed',
          groupId,
        })
      }
      // A live browser with no CUA action yet (websurfer_only at launch):
      // defer the embed until the first tool call forms a cua-group, so the
      // bottom status indicator stays visible.
    }
  }

  return items
}

/**
 * Pick the representative ISO timestamp for a render item, used to decide
 * whether a timestamp separator is needed before it.
 *
 * - `message` → the message's own timestamp.
 * - `cua-group` → the first action's source-message timestamp (the group is
 *   atomic and never split internally).
 * - `cua-placeholder` / `browser-embed` / `timestamp` → no anchor; these never
 *   trigger a separator on their own.
 */
function timestampOfItem(item: RenderItem): string | undefined {
  if (item.kind === 'message') return item.message.timestamp
  if (item.kind === 'cua-group') return item.firstTimestamp
  return undefined
}

/**
 * Insert inline timestamp separators between render items when the gap exceeds
 * `CHAT_TIMESTAMP_GAP_MS`. Always inserts a leading separator above the first
 * item that has a timestamp, so every chat opens with a time anchor.
 *
 * Operates at the RenderItem layer so CUA groups stay atomic.
 */
export function insertTimestampSeparators(items: RenderItem[]): RenderItem[] {
  const out: RenderItem[] = []
  let lastIso: string | undefined
  let leadingInserted = false

  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    const iso = timestampOfItem(item)

    if (iso) {
      if (!leadingInserted) {
        // Always anchor the first timestamped item with a leading separator.
        out.push({ kind: 'timestamp', id: `ts-lead-${iso}`, iso })
        leadingInserted = true
      } else if (exceedsChatGap(lastIso, iso)) {
        out.push({ kind: 'timestamp', id: `ts-${i}-${iso}`, iso })
      }
      lastIso = iso
    }

    out.push(item)
  }

  return out
}

/**
 * Check if the session status indicator should be hidden.
 *
 * Hidden when the last message already conveys the same information:
 * - Active: shimmer headers show activity
 * - Completed: last message is final-answer
 * - Awaiting input: last message is input-request with content
 * - Error: last message is error/system-status(error) with content
 */
export function shouldHideStatusIndicator(
  renderItems: RenderItem[],
  sessionStatus: SessionStatus | undefined
): boolean {
  if (sessionStatus === 'active') {
    // These indicators are always near the tail — check from the end, skip
    // structural items that are not real messages (browser-embed, timestamp).
    for (let i = renderItems.length - 1; i >= 0; i--) {
      const item = renderItems[i]
      if (item.kind === 'browser-embed' || item.kind === 'timestamp') continue
      return (
        item.kind === 'cua-placeholder' ||
        (item.kind === 'cua-group' && item.canUseProgressiveTense) ||
        (item.kind === 'message' &&
          ((item.message.kind === 'orchestrator-tool' && item.toolResultContent === undefined) ||
            (item.message.kind === 'code-execution' && item.codeResultContent === undefined)))
      )
    }
    return false
  }

  // Find last message item for terminal-state checks
  let lastMsg: ParsedMessage | undefined
  for (let i = renderItems.length - 1; i >= 0; i--) {
    const item = renderItems[i]
    if (item.kind === 'message') {
      lastMsg = item.message
      break
    }
  }
  if (!lastMsg) return false

  if (sessionStatus === 'completed') {
    return (
      lastMsg.kind === 'final-answer' ||
      (lastMsg.kind === 'system-status' && lastMsg.status === 'complete' && !!lastMsg.content)
    )
  }
  if (sessionStatus === 'awaiting-input') {
    return (
      lastMsg.kind === 'input-request' && (!!lastMsg.content || lastMsg.inputType === 'approval')
    )
  }
  if (sessionStatus === 'error') {
    return (
      (lastMsg.kind === 'error' ||
        (lastMsg.kind === 'system-status' && lastMsg.status === 'error')) &&
      !!lastMsg.content
    )
  }

  return false
}
