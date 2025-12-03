/**
 * Message Parser
 *
 * Converts raw backend messages to strongly-typed ParsedMessage variants.
 * All message parsing logic is centralized here.
 */

import type { Message, ServerRunStatus } from '@/types/api'
import type {
  ParsedMessage,
  ParsedUserMessage,
  ParsedCuaBrowserMessage,
  ParsedCuaNonBrowserMessage,
  ParsedScreenshotMessage,
  ParsedCodeExecutionMessage,
  ParsedOrchestratorToolMessage,
  ParsedToolResultMessage,
  ParsedFinalAnswerMessage,
  ParsedSummaryMessage,
  ParsedBrowserAddressMessage,
  ParsedInternalMessage,
  ParsedErrorMessage,
  ParsedSystemStatusMessage,
  ParsedInputRequestMessage,
  ParsedApprovalResponseMessage,
  ParsedContinuationResponseMessage,
  ParsedReasoningMessage,
  ParsedFileMessage,
  ParsedTextMessage,
  BrowserToolArgs,
  NonBrowserToolArgs,
} from '@/types/message'
import type { FolderInfo } from '@/types/folder'
import {
  CUA_AGENT_SOURCE,
  ORCHESTRATOR_AGENT_SOURCE,
  isBrowserTool,
  isNonBrowserTool,
  shouldDemoteCuaFinalAnswer,
  type AgentMode,
  type BrowserTool,
  type NonBrowserTool,
} from './constants'
import { extractText, extractImageUrl, unwrapUserContent } from './utils'
import { parseFileInfoFromMetadata } from '@/lib/fileUtils'

// Auto-incrementing fallback ID for messages without a backend id.
// Module-level ensures uniqueness across all parseMessage calls.
let parseAutoId = 0

// =============================================================================
// Metadata Types (internal)
// =============================================================================

interface ToolCallMetadata {
  type: 'tool_call'
  tool: string
  tool_args: Record<string, unknown>
  source?: string
  tool_call_id?: string
  approval_status?: string
}

interface BrowserAddressMetadata {
  type: 'browser_address'
  novnc_port?: string
  playwright_port?: string
}

type MessageMetadata =
  | ToolCallMetadata
  | BrowserAddressMetadata
  | { type: 'browser_screenshot' }
  | { type: 'code_to_execute' }
  | { type: 'tool_result'; tool?: string; tool_call_id?: string }
  | { type: 'final_answer' }
  | { type: 'reasoning' }
  | { type: 'text' }
  | { type: 'debugging' }
  | { type: 'error' }
  | { type: 'file'; files?: string; summary?: boolean; uploaded_files?: string }
  | { type?: undefined; [key: string]: unknown }

/**
 * Tools whose tool_call and tool_result are routed to `internal` (hidden from
 * the chat). These tools have dedicated UI handled by other paths
 * (e.g., `request_user_input` is rendered as an InputRequest, not a tool call),
 * so the raw call and the echoed response would only appear as duplicates.
 */
const HIDDEN_TOOLS = new Set<string>(['request_user_input'])

// =============================================================================
// Content Parsing Helpers
// =============================================================================

/**
 * Extract code and language from code_to_execute content.
 * Formats:
 * - "[OmniAgent] Executing code:\n```python\n...\n```"
 * - "Executing code:\n```python\n...\n```"
 */
function parseCodeExecuteContent(rawText: string): { code: string; language: string } {
  const codeMatch = rawText.match(/```(\w+)?\n([\s\S]*?)```/)
  if (codeMatch) {
    return {
      language: codeMatch[1] || 'python',
      code: codeMatch[2]?.trim() ?? '',
    }
  }
  return { code: rawText, language: 'python' }
}

// =============================================================================
// Parser
// =============================================================================

/**
 * Parse a raw backend message into a strongly-typed ParsedMessage.
 * @param previousTimestamp - ISO timestamp of the previous message, used to compute thinking duration for reasoning messages.
 * @param agentMode - Agent mode persisted on the run row by the backend at
 *   run-start. Used to decide whether the web_surfer's ``final_answer`` is
 *   the real, user-facing answer (FARA-only mode) or an intermediate hand-off
 *   to OmniAgent. When null/undefined (legacy runs predating the column),
 *   we keep CUA's ``final_answer`` as a real ``final-answer`` so no
 *   information is hidden — the cost is that legacy OmniAgent runs may
 *   show one extra "intermediate" final answer card.
 */
export function parseMessage(
  msg: Message,
  previousTimestamp?: string,
  agentMode?: AgentMode | null
): ParsedMessage {
  const { config, created_at } = msg
  const { source, content, metadata } = config
  const rawMeta = metadata as Record<string, unknown> | undefined

  // Base fields shared by all variants
  const base = {
    id: String(msg.id ?? `auto-${++parseAutoId}`),
    timestamp: created_at,
    source,
    raw: msg,
  }

  // --- Protocol messages (not content messages) ---

  // System status (complete, error, stopped, paused, awaiting_input, etc.)
  if (rawMeta?.type === 'system' && typeof rawMeta.status === 'string') {
    const text = extractText(content)
    const status = rawMeta.status as ServerRunStatus
    return { ...base, kind: 'system-status', status, content: text } as ParsedSystemStatusMessage
  }

  // Approval response (hidden marker for tracking approval card state)
  if (rawMeta?.type === 'approval_response') {
    const raw = String(rawMeta.decision ?? 'deny')
    const decision = raw === 'approve' ? 'approve' : raw === 'alternative' ? 'alternative' : 'deny'
    return { ...base, kind: 'approval-response', decision } as ParsedApprovalResponseMessage
  }

  // Continuation response (hidden marker)
  if (rawMeta?.type === 'continuation_response') {
    const raw = String(rawMeta.decision ?? 'stop')
    const decision = raw === 'continue' ? 'continue' : 'stop'
    return {
      ...base,
      kind: 'continuation-response',
      decision,
    } as ParsedContinuationResponseMessage
  }

  // Input request (agent waiting for user input)
  if (rawMeta?.type === 'input_request') {
    const text = extractText(content)
    const inputType = String(rawMeta.input_type ?? 'text_input')
    const parsed: ParsedInputRequestMessage = {
      ...base,
      kind: 'input-request',
      inputType,
      content: text,
    }
    // Attach approval metadata when present
    if (inputType === 'approval') {
      if (typeof rawMeta.tool === 'string') parsed.tool = rawMeta.tool
      if (rawMeta.tool_args && typeof rawMeta.tool_args === 'object')
        parsed.toolArgs = rawMeta.tool_args as Record<string, unknown>
      if (typeof rawMeta.category === 'string') parsed.category = rawMeta.category
      if (typeof rawMeta.reason === 'string') parsed.reason = rawMeta.reason
    }
    return parsed
  }

  // --- Content messages (use typed metadata) ---

  const meta = rawMeta as MessageMetadata | undefined
  const metaType = meta?.type

  // User message
  if (source === 'user' || source === 'user_proxy') {
    const textContent = typeof content === 'string' ? unwrapUserContent(content) : ''
    // Parse attached files from metadata (set by backend's construct_task)
    let attachedFiles: import('@/types/file').FileInfo[] | undefined
    if (typeof rawMeta?.attached_files === 'string') {
      const parsed = parseFileInfoFromMetadata(rawMeta.attached_files as string)
      if (parsed.length > 0) attachedFiles = parsed
    }

    let mountedFolder: FolderInfo | undefined
    if (rawMeta?.mounted_folder && typeof rawMeta.mounted_folder === 'object') {
      const folder = rawMeta.mounted_folder as Record<string, unknown>
      if (typeof folder.name === 'string' && typeof folder.path === 'string') {
        mountedFolder = { name: folder.name, path: folder.path }
      }
    }

    return {
      ...base,
      kind: 'user',
      content: textContent,
      attachedFiles,
      mountedFolder,
    } as ParsedUserMessage
  }

  // Tool call — route by source
  if (metaType === 'tool_call' && meta && 'tool' in meta && 'tool_args' in meta) {
    const tool = meta.tool
    const toolArgs = meta.tool_args as Record<string, unknown>

    // CUA tools from web_surfer (Fara)
    if (source === CUA_AGENT_SOURCE) {
      // Hidden tools — handled by InputRequest UI flow, not chat history
      if (tool === 'ask_user_question') {
        return { ...base, kind: 'internal', content: extractText(content) } as ParsedInternalMessage
      }

      if (isBrowserTool(tool)) {
        return {
          ...base,
          kind: 'cua-browser',
          tool: tool as BrowserTool,
          toolArgs: {
            action: toolArgs.action as string | undefined,
            url: toolArgs.url as string | undefined,
            query: toolArgs.query as string | undefined,
            text: toolArgs.text as string | undefined,
            coordinate: toolArgs.coordinate as [number, number] | undefined,
            pixels: toolArgs.pixels as number | undefined,
            keys: toolArgs.keys as string[] | undefined,
            time: toolArgs.time as number | undefined,
            press_enter: toolArgs.press_enter as boolean | undefined,
            delete_existing_text: toolArgs.delete_existing_text as boolean | undefined,
            thoughts: (toolArgs.thoughts as string) ?? '',
          } as BrowserToolArgs,
        } as ParsedCuaBrowserMessage
      }

      if (isNonBrowserTool(tool)) {
        return {
          ...base,
          kind: 'cua-non-browser',
          tool: tool as NonBrowserTool,
          toolArgs: {
            action: toolArgs.action as string | undefined,
            fact: toolArgs.fact as string | undefined,
            status: toolArgs.status as 'success' | 'failure' | undefined,
            time: toolArgs.time as number | undefined,
            question: toolArgs.question as string | undefined,
            command: toolArgs.command as string | undefined,
            thoughts: (toolArgs.thoughts as string) ?? '',
          } as NonBrowserToolArgs,
        } as ParsedCuaNonBrowserMessage
      }

      // Unknown CUA tool — treat as text
      return { ...base, kind: 'text', content: extractText(content) } as ParsedTextMessage
    }

    // Orchestrator tools from OmniAgent
    if (source === ORCHESTRATOR_AGENT_SOURCE) {
      // Hidden tools — their UI is handled by other message types
      if (HIDDEN_TOOLS.has(tool)) {
        return { ...base, kind: 'internal', content: extractText(content) } as ParsedInternalMessage
      }
      const toolCallId = typeof meta?.tool_call_id === 'string' ? meta.tool_call_id : undefined
      const approvalStatus =
        typeof meta?.approval_status === 'string' ? meta.approval_status : undefined
      return {
        ...base,
        kind: 'orchestrator-tool',
        tool,
        toolArgs,
        toolCallId,
        ...(approvalStatus && { approvalStatus }),
      } as ParsedOrchestratorToolMessage
    }

    // Unknown source tool_call — treat as text
    return { ...base, kind: 'text', content: extractText(content) } as ParsedTextMessage
  }

  // Screenshot
  if (metaType === 'browser_screenshot') {
    const imageUrl = Array.isArray(content) ? extractImageUrl(content) : null
    // actionResult: description of what was done (past tense), from backend's action_description
    const actionResult = extractText(content) || undefined
    return {
      ...base,
      kind: 'screenshot',
      imageUrl: imageUrl ?? '',
      actionResult: actionResult || undefined,
    } as ParsedScreenshotMessage
  }

  // Browser address
  if (metaType === 'browser_address' && meta && 'novnc_port' in meta) {
    return {
      ...base,
      kind: 'browser-address',
      novncPort: String((meta as BrowserAddressMetadata).novnc_port ?? ''),
      playwrightPort: (meta as BrowserAddressMetadata).playwright_port
        ? String((meta as BrowserAddressMetadata).playwright_port)
        : undefined,
    } as ParsedBrowserAddressMessage
  }

  // Code execution
  if (metaType === 'code_to_execute') {
    // Prefer metadata.code over content (which has wrapper text)
    const metaCode = rawMeta?.code as string | undefined
    if (metaCode) {
      return {
        ...base,
        kind: 'code-execution',
        code: metaCode,
        language: 'python',
      } as ParsedCodeExecutionMessage
    }
    const rawText = extractText(content)
    const { code, language } = parseCodeExecuteContent(rawText)
    return { ...base, kind: 'code-execution', code, language } as ParsedCodeExecutionMessage
  }

  // Tool result (OmniAgent tool results: bash, open, delegate_cua, etc.).
  // Tool name comes from metadata.tool when present. Messages without it
  // fall back to a tool_call_id reverse-lookup in computeRenderItems.
  if (metaType === 'tool_result') {
    const rawText = extractText(content)
    const toolName = typeof meta?.tool === 'string' ? meta.tool : undefined
    // Hidden tools (see HIDDEN_TOOLS) — their result is a duplicate of input
    // already shown via the InputRequest UI flow, so don't render it.
    if (toolName && HIDDEN_TOOLS.has(toolName)) {
      return { ...base, kind: 'internal', content: rawText } as ParsedInternalMessage
    }
    const toolCallId = typeof meta?.tool_call_id === 'string' ? meta.tool_call_id : undefined
    return {
      ...base,
      kind: 'tool-result',
      toolName,
      result: rawText,
      toolCallId,
    } as ParsedToolResultMessage
  }

  // File generated/edited
  if (metaType === 'file' && typeof rawMeta?.files === 'string') {
    const files = parseFileInfoFromMetadata(rawMeta.files as string)
    const uploaded =
      typeof rawMeta?.uploaded_files === 'string'
        ? parseFileInfoFromMetadata(rawMeta.uploaded_files as string)
        : []
    if (files.length > 0 || uploaded.length > 0) {
      const parsed: ParsedFileMessage = { ...base, kind: 'file', files }
      if (rawMeta?.summary === true) {
        parsed.summary = true
      }
      if (uploaded.length > 0) {
        parsed.uploadedFiles = uploaded
      }
      return parsed
    }
    // If parsing failed, fall through to text
  }

  // Final answer
  if (metaType === 'final_answer') {
    // In OmniAgent modes, the web_surfer's final_answer is intermediate —
    // OmniAgent emits the real one a few messages later. Demote it to
    // 'internal' so the UI doesn't render two final-answer cards.
    // Unknown agent_mode (legacy runs) keeps it as final-answer to avoid
    // hiding the only real answer in old FARA-only sessions; the trade-off
    // is one extra intermediate card on legacy OmniAgent sessions.
    if (source === CUA_AGENT_SOURCE && shouldDemoteCuaFinalAnswer(agentMode)) {
      return {
        ...base,
        kind: 'internal',
        content: extractText(content),
      } as ParsedInternalMessage
    }
    const text = extractText(content)
    return { ...base, kind: 'final-answer', content: text } as ParsedFinalAnswerMessage
  }

  // Reasoning (agent's internal thought process)
  if (metaType === 'reasoning') {
    const text = extractText(content)
    let thinkingSeconds: number | null = null
    if (previousTimestamp) {
      const diff = new Date(created_at).getTime() - new Date(previousTimestamp).getTime()
      if (diff > 0) thinkingSeconds = Math.round(diff / 1000)
    }
    return { ...base, kind: 'reasoning', content: text, thinkingSeconds } as ParsedReasoningMessage
  }

  // Summary text (metadata.type === 'text')
  if (metaType === 'text') {
    const text = extractText(content)
    return { ...base, kind: 'summary', content: text } as ParsedSummaryMessage
  }

  // Debugging (internal)
  if (metaType === 'debugging') {
    const text = extractText(content)
    return { ...base, kind: 'internal', content: text } as ParsedInternalMessage
  }

  // Error
  if (metaType === 'error') {
    const text = extractText(content)
    return { ...base, kind: 'error', content: text } as ParsedErrorMessage
  }

  // Default: text message
  return { ...base, kind: 'text', content: extractText(content) } as ParsedTextMessage
}

/**
 * Parse an array of raw messages to ParsedMessages.
 * Passes previous message timestamp to each call for reasoning duration calculation.
 *
 * @param agentMode - Mode persisted on the run row by the backend; forwarded
 *   to each ``parseMessage`` call. See ``parseMessage`` for null semantics.
 */
export function parseMessages(messages: Message[], agentMode?: AgentMode | null): ParsedMessage[] {
  return messages.map((msg, i) => {
    const prevTimestamp = i > 0 ? messages[i - 1].created_at : undefined
    return parseMessage(msg, prevTimestamp, agentMode)
  })
}
