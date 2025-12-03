/**
 * Parsed Message Types
 *
 * Strongly-typed message types with discriminated union by 'kind'.
 * Components use the parsed fields directly, NOT raw.config.
 *
 * See lib/messages/parser.ts for the parsing logic.
 */

import type { Message, ServerRunStatus } from './api'
import type { BrowserTool, NonBrowserTool } from '@/lib/messages/constants'
import type { FileInfo } from './file'
import type { FolderInfo } from './folder'

// =============================================================================
// Tool Arguments
// =============================================================================

/**
 * Arguments for browser tools from metadata.tool_args
 */
export interface BrowserToolArgs {
  action?: string
  url?: string
  query?: string
  text?: string
  coordinate?: [number, number]
  pixels?: number
  keys?: string[]
  time?: number
  press_enter?: boolean
  delete_existing_text?: boolean
  /**
   * Agent's reasoning about the planned action (future tense).
   * Describes what the agent intends to do.
   * - thoughts: "I will click the search button" (before action)
   * - screenshot.actionResult: "Clicked the search button" (after action)
   */
  thoughts: string
}

/**
 * Arguments for non-browser tools from metadata.tool_args
 */
export interface NonBrowserToolArgs {
  action?: string
  fact?: string
  status?: 'success' | 'failure'
  time?: number
  question?: string
  command?: string
  thoughts: string
}

// =============================================================================
// Base Message Interface
// =============================================================================

/**
 * Common fields for all parsed message types
 */
interface ParsedMessageBase {
  /** Stable ID for React keys */
  id: string
  /** ISO timestamp */
  timestamp: string
  /** Agent source (user, web_surfer, omni_agent, etc.) */
  source: string
  /**
   * Original message from API.
   * @internal UI components should NOT access this field.
   * Use the parsed fields (content, tool, toolArgs, etc.) instead.
   * This is stored only for debugging and edge cases.
   */
  raw: Message
}

// =============================================================================
// Message Type Variants
// =============================================================================

/** User message */
export interface ParsedUserMessage extends ParsedMessageBase {
  kind: 'user'
  content: string
  /** Files attached to this message (from metadata.attached_files) */
  attachedFiles?: FileInfo[]
  /** Mounted folder used for this start message (from metadata.mounted_folder) */
  mountedFolder?: FolderInfo
}

/** CUA browser action (from web_surfer/Fara) */
export interface ParsedCuaBrowserMessage extends ParsedMessageBase {
  kind: 'cua-browser'
  tool: BrowserTool
  toolArgs: BrowserToolArgs
}

/** CUA tool with text/session-control result (no screenshot). See NON_BROWSER_TOOLS. */
export interface ParsedCuaNonBrowserMessage extends ParsedMessageBase {
  kind: 'cua-non-browser'
  tool: NonBrowserTool
  toolArgs: NonBrowserToolArgs
}

/** Screenshot */
export interface ParsedScreenshotMessage extends ParsedMessageBase {
  kind: 'screenshot'
  imageUrl: string
  /**
   * Description of the completed action (past tense).
   * Complements toolArgs.thoughts which describes the planned action (future tense).
   * - thoughts: "I will click the search button" (before action)
   * - actionResult: "Clicked the search button" (after action)
   */
  actionResult?: string
}

/** Code execution request */
export interface ParsedCodeExecutionMessage extends ParsedMessageBase {
  kind: 'code-execution'
  /** Clean code extracted from content (code fence wrapper stripped) */
  code: string
  /** Language from code fence (e.g. 'python') */
  language: string
}

/**
 * Orchestrator tool call from OmniAgent (metadata.type === 'tool_call', source !== 'web_surfer').
 * Covers: bash, create, open, edit, insert, goto, scroll_down, scroll_up,
 * search_dir, search_file, find_file, delegate_cua, and any future tools.
 */
export interface ParsedOrchestratorToolMessage extends ParsedMessageBase {
  kind: 'orchestrator-tool'
  /** Tool name (e.g. 'delegate_cua', 'bash', 'edit') */
  tool: string
  /** Structured arguments from metadata.tool_args */
  toolArgs: Record<string, unknown>
  /** Unique ID linking tool_call to its tool_result (introduced for approval tracking) */
  toolCallId?: string
  /** How this tool call was approved: 'user' | 'auto_session' | 'auto_policy' | undefined */
  approvalStatus?: string
}

/**
 * Tool result from OmniAgent (metadata.type === 'tool_result').
 * Covers all orchestrator tools. Adjacent results are merged with orchestrator-tool
 * in messageListUtils; non-adjacent results render as standalone ToolResultMessage.
 */
export interface ParsedToolResultMessage extends ParsedMessageBase {
  kind: 'tool-result'
  /** Tool name extracted from content (e.g. 'delegate_cua', 'bash') */
  toolName: string | undefined
  /** Clean result text with prefix stripped */
  result: string
  /** Unique ID linking this result to its tool_call */
  toolCallId?: string
}

/** Final answer from agent */
export interface ParsedFinalAnswerMessage extends ParsedMessageBase {
  kind: 'final-answer'
  content: string
}

/**
 * Summary message from web_surfer after browser operations (FARA mode).
 * Backend: metadata.type === 'text'
 */
export interface ParsedSummaryMessage extends ParsedMessageBase {
  kind: 'summary'
  content: string
}

/** Browser address (internal, hidden) */
export interface ParsedBrowserAddressMessage extends ParsedMessageBase {
  kind: 'browser-address'
  novncPort: string
  playwrightPort?: string
}

/** Internal/debugging (hidden) */
export interface ParsedInternalMessage extends ParsedMessageBase {
  kind: 'internal'
  content: string
}

/**
 * Agent runtime error message (metadata.type: 'error')
 *
 * Examples: tool call failures, page not initialized, etc.
 *
 * Note: Run status errors (system message with status: 'error') use ParsedSystemStatusMessage.
 */
export interface ParsedErrorMessage extends ParsedMessageBase {
  kind: 'error'
  content: string
}

/** System status message (run status changes sent via WebSocket) */
export interface ParsedSystemStatusMessage extends ParsedMessageBase {
  kind: 'system-status'
  status: ServerRunStatus
  content: string
}

/** Approval response (hidden from chat, used to track approval card state) */
export interface ParsedApprovalResponseMessage extends ParsedMessageBase {
  kind: 'approval-response'
  decision: 'approve' | 'deny' | 'alternative'
}

/** Hidden marker that records the user's Continue/Stop decision. */
export interface ParsedContinuationResponseMessage extends ParsedMessageBase {
  kind: 'continuation-response'
  decision: 'continue' | 'stop'
}

/** Input request message (agent waiting for user input) */
export interface ParsedInputRequestMessage extends ParsedMessageBase {
  kind: 'input-request'
  inputType: string
  content: string
  /** Approval-specific fields (present when inputType === 'approval') */
  tool?: string
  toolArgs?: Record<string, unknown>
  category?: string
  reason?: string
}

/**
 * Agent reasoning/thinking message (metadata.type === 'reasoning').
 * Shows the agent's internal thought process, displayed in a collapsible section.
 */
export interface ParsedReasoningMessage extends ParsedMessageBase {
  kind: 'reasoning'
  content: string
  /** Seconds the agent spent thinking (derived from timestamp diff with previous message) */
  thinkingSeconds: number | null
}

/**
 * Generic text message (fallback for messages without metadata.type).
 * Includes: omni_agent conversation messages.
 * Backend: no metadata.type or unknown type
 */
export interface ParsedTextMessage extends ParsedMessageBase {
  kind: 'text'
  content: string
}

/**
 * File generated/edited message (metadata.type === 'file').
 * Contains one or more files that the agent created or modified.
 */
export interface ParsedFileMessage extends ParsedMessageBase {
  kind: 'file'
  /** Parsed file info from metadata.files JSON */
  files: FileInfo[]
  /**
   * When true, this is the end-of-run aggregated list of all files created
   * or modified by the agent. Rendered with a "Files the agent created or
   * modified" header to summarize artifacts after the final answer.
   */
  summary?: boolean
  /**
   * Files the user uploaded for this run. Only set on summary messages.
   * Rendered as a separate "Files you uploaded" section above the
   * generated files for a complete overview.
   */
  uploadedFiles?: FileInfo[]
}

// =============================================================================
// Union Type
// =============================================================================

/**
 * Discriminated union of all parsed message types.
 * Use `kind` field for type narrowing.
 */
export type ParsedMessage =
  | ParsedUserMessage
  | ParsedCuaBrowserMessage
  | ParsedCuaNonBrowserMessage
  | ParsedScreenshotMessage
  | ParsedCodeExecutionMessage
  | ParsedOrchestratorToolMessage
  | ParsedToolResultMessage
  | ParsedFinalAnswerMessage
  | ParsedSummaryMessage
  | ParsedBrowserAddressMessage
  | ParsedInternalMessage
  | ParsedErrorMessage
  | ParsedSystemStatusMessage
  | ParsedInputRequestMessage
  | ParsedApprovalResponseMessage
  | ParsedContinuationResponseMessage
  | ParsedReasoningMessage
  | ParsedFileMessage
  | ParsedTextMessage

// =============================================================================
// Type Guards
// =============================================================================

/** Check if message is a user message */
export function isUserMessage(message: ParsedMessage): message is ParsedUserMessage {
  return message.kind === 'user'
}

/** Check if message is a CUA browser action */
export function isCuaBrowserMessage(message: ParsedMessage): message is ParsedCuaBrowserMessage {
  return message.kind === 'cua-browser'
}

/** Check if message is a screenshot */
export function isScreenshotMessage(message: ParsedMessage): message is ParsedScreenshotMessage {
  return message.kind === 'screenshot'
}

/** Check if message is internal (hidden from chat) */
export function isParsedInternalMessage(message: ParsedMessage): boolean {
  return (
    message.kind === 'internal' ||
    message.kind === 'browser-address' ||
    message.kind === 'approval-response' ||
    message.kind === 'continuation-response'
  )
}

/** Check if a parsed message is an optimistic (not yet confirmed by backend) user message */
export function isOptimisticMessage(message: ParsedMessage): boolean {
  return (
    message.kind === 'user' &&
    (message.raw.config.metadata as Record<string, unknown> | undefined)?._optimistic === true
  )
}
