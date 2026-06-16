/**
 * WebSocket Types
 *
 * Message formats for real-time communication between frontend and backend.
 */

import type { InputType, AgentMessageConfig } from './api'
import type { ServerRunStatus } from './state'
import type { UploadedFileRef } from './file'

// =============================================================================
// Connection Types
// =============================================================================

/**
 * Run info needed for WebSocket connection management
 */
export interface ActiveRun {
  runId: string
  sessionId: number
  sessionName: string
  status: ServerRunStatus
}

// =============================================================================
// Server -> Client Messages
// =============================================================================

/**
 * Server message type constants (matches backend connection.py)
 */
export const WS_SERVER_MESSAGE_TYPE = {
  SYSTEM: 'system',
  MESSAGE: 'message',
  MESSAGE_CHUNK: 'message_chunk',
  INPUT_REQUEST: 'input_request',
  FILE: 'file',
  AGENT_STATE: 'agent_state',
  PONG: 'pong',
} as const

/**
 * WebSocket message from server (discriminated union)
 */
export type WsServerMessage =
  | WsServerSystemMessage
  | WsServerAgentMessage
  | WsServerMessageChunk
  | WsServerInputRequestMessage
  | WsServerFileMessage
  | WsServerAgentStateMessage
  | WsServerPongMessage

/**
 * System status message
 * Single source of truth for status updates (paused/complete/error/stopped).
 * Optional content field contains additional info (error message, stop reason, etc.)
 *
 * Note: Backend also sends 'connected' as a WebSocket connection acknowledgement.
 * This is a connection event, not a run status - frontend should skip it.
 */
export interface WsServerSystemMessage {
  type: typeof WS_SERVER_MESSAGE_TYPE.SYSTEM
  status: ServerRunStatus | 'connected'
  /** Optional content (error message, stop reason, etc.) */
  content?: string
  /** Optional server-assigned UTC ISO timestamp. */
  timestamp?: string
}

/**
 * Agent message
 */
export interface WsServerAgentMessage {
  type: typeof WS_SERVER_MESSAGE_TYPE.MESSAGE
  data: AgentMessageConfig
  /**
   * Server-assigned UTC ISO timestamp. Optional because older backends may
   * omit it; the WS handler falls back to `Date.now()` when absent.
   */
  timestamp?: string
}

/**
 * Streaming message chunk
 */
export interface WsServerMessageChunk {
  type: typeof WS_SERVER_MESSAGE_TYPE.MESSAGE_CHUNK
  data: {
    id?: string
    content: string
    [key: string]: unknown
  }
  /** Optional server-assigned UTC ISO timestamp. */
  timestamp?: string
}

/**
 * Input request from backend
 * Indicates agent needs user input. Does NOT update status (system message does that).
 */
export interface WsServerInputRequestMessage {
  type: typeof WS_SERVER_MESSAGE_TYPE.INPUT_REQUEST
  input_type: InputType
  /** Message content to display (optional) */
  content?: string
  /** Approval-specific fields (present when input_type === 'approval') */
  tool?: string
  tool_args?: Record<string, unknown>
  category?: string
  reason?: string
  /** Optional server-assigned UTC ISO timestamp. */
  timestamp?: string
}

/**
 * File generated/modified message (PR 283).
 * Backend sends this when new or modified files are detected in the run directory.
 */
export interface WsServerFileMessage {
  type: typeof WS_SERVER_MESSAGE_TYPE.FILE
  files: Array<{
    name: string
    url: string
    timestamp: number
    extension: string
    file_type: string
    action: 'created' | 'modified'
  }>
  /**
   * When true, this is the end-of-run aggregated list of every file the
   * agent created or modified during the task. The chat renders it under
   * a "Files the agent created or modified" header so users can find all
   * artifacts after the final answer.
   */
  summary?: boolean
  /**
   * Files the user uploaded for this run. Only present on the summary
   * message so the chat can render a separate "Files you uploaded"
   * section above the generated files for a complete overview.
   */
  uploaded_files?: Array<{
    name: string
    url: string
    timestamp: number
    extension: string
    file_type: string
  }>
  /** Optional server-assigned UTC ISO timestamp. */
  timestamp?: string
}

/**
 * Heartbeat response
 */
export interface WsServerPongMessage {
  type: typeof WS_SERVER_MESSAGE_TYPE.PONG
  timestamp: string
}

/**
 * Transient signal around an LLM call: "waiting for the model" vs
 * "generating". Not persisted — the next persistent message clears it.
 * ``model_slow`` is "still waiting" past a grace period.
 */
export type AgentActivityState = 'calling_model' | 'model_slow' | 'generating'

export interface WsServerAgentStateMessage {
  type: typeof WS_SERVER_MESSAGE_TYPE.AGENT_STATE
  state: AgentActivityState
  /** Agent that emitted the signal. */
  source: string
  /** Optional server-assigned UTC ISO timestamp. */
  timestamp?: string
}

// =============================================================================
// Client -> Server Messages
// =============================================================================

/**
 * Client message type constants
 */
export const WS_CLIENT_MESSAGE_TYPE = {
  START: 'start',
  STOP: 'stop',
  PAUSE: 'pause',
  INPUT_RESPONSE: 'input_response',
  APPROVAL_RESPONSE: 'approval_response',
  CONTINUATION_RESPONSE: 'continuation_response',
  PING: 'ping',
} as const

/**
 * Start task message
 */
export interface WsClientStartMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.START
  task: string
  files?: unknown[]
  team_config: Record<string, unknown>
  settings_config?: Record<string, unknown>
}

/**
 * Stop task message
 */
export interface WsClientStopMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.STOP
  reason?: string
}

/**
 * Pause task message
 * Pauses the current workflow, agent will yield a message and request user input
 */
export interface WsClientPauseMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.PAUSE
}

/**
 * User input response message. `files` carries optional mid-session
 * uploads.
 */
export interface WsClientInputResponseMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.INPUT_RESPONSE
  response: string
  files?: UploadedFileRef[]
}

/**
 * Structured approval response (Approve/Deny buttons or auto-approve)
 */
export interface WsClientApprovalResponseMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.APPROVAL_RESPONSE
  decision: 'approve' | 'deny'
  source: 'user' | 'auto_session'
}

/** Continue / Stop response on a max-rounds card. */
export interface WsClientContinuationResponseMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.CONTINUATION_RESPONSE
  decision: 'continue' | 'stop'
}

/**
 * Heartbeat ping message
 */
export interface WsClientPingMessage {
  type: typeof WS_CLIENT_MESSAGE_TYPE.PING
}

/**
 * All client-to-server message types (discriminated union)
 */
export type WsClientMessage =
  | WsClientStartMessage
  | WsClientStopMessage
  | WsClientPauseMessage
  | WsClientInputResponseMessage
  | WsClientApprovalResponseMessage
  | WsClientContinuationResponseMessage
  | WsClientPingMessage
