/**
 * Store Types
 *
 * Type definitions for Zustand stores.
 * Separate from state.ts which defines the state layering concept.
 */

import type { InputRequest } from './api'
import type { ParsedMessage } from './message'
import type { ServerRunStatus, ConnectionStatus, PendingAction, ControlState } from './state'
import type { FileInfo } from './file'
import type { FolderInfo } from './folder'
import type { AgentMode } from '@/lib/messages'

// =============================================================================
// Browser View Types
// =============================================================================

export type BrowserViewMode = 'embedded' | 'expanded' | 'maximized'

// =============================================================================
// Chat Store Types
// =============================================================================

/**
 * Per-session chat state
 *
 * TODO: Add `lastReadMessageId` field to track the last message
 * the user has read. This enables:
 * 1. Showing "New messages" divider at the first unread message
 * 2. Scrolling to first unread instead of bottom when new messages arrive
 */
export interface SessionChatState {
  // Server state
  runId: string | null
  serverStatus: ServerRunStatus
  messages: ParsedMessage[]
  inputRequest: InputRequest | null

  // Connection state
  connectionStatus: ConnectionStatus

  // Optimistic UI state
  pendingAction: PendingAction | null

  // Browser view state
  novncUrl: string | null
  /** Per-slot RFB password from the backend; passed to react-vnc so the noVNC handshake auths silently. */
  novncPassword: string | null
  browserViewMode: BrowserViewMode
  /** Whether showing live VNC stream (true) or screenshot playback (false). Only meaningful when VNC is connected. */
  playbackIsLive: boolean
  /** Current screenshot index when in playback mode */
  playbackIndex: number
  /** Whether to auto-advance to the latest screenshot as new ones arrive */
  followLatestScreenshot: boolean
  /** Message ID of the highlighted CUA action (for Chat ↔ Browser sync) */
  highlightedActionId: string | null
  /** Browser control state: 'agent' | 'user-pending' | 'user' */
  controlState: ControlState
  /** Whether user needs to describe their browser actions (persists after release) */
  pendingTakeoverFeedback: boolean
  /**
   * Agent mode persisted on the run row by the backend at run-start.
   * Used to decide whether the web_surfer's ``final_answer`` is the real
   * final answer (FARA-only mode) or an intermediate hand-off to OmniAgent.
   * Null on legacy runs created before the column existed; in that case the
   * parser keeps CUA's final_answer as a real final-answer (information
   * preservation over visual cleanliness). Narrowed to the typed
   * ``AgentMode`` enum at the boundary (see ``toAgentMode``) so unknown
   * strings from a newer backend are treated the same as legacy null.
   */
  agentMode: AgentMode | null

  // Auto-approve state (session-scoped, not persisted)
  /** Tool names auto-approved for this session (e.g. ['bash', 'create_file']) */
  autoApproveTools: string[]
  /** Whether all tools are auto-approved for this session */
  autoApproveAll: boolean

  // File preview state
  /** Currently previewed file (null = no file panel open) */
  previewFile: FileInfo | null
  /** Whether file panel is maximized (vs side-by-side) */
  fileMaximized: boolean

  // Folder mounting state
  /** Currently mounted folder for this session (null = none) */
  mountedFolder: FolderInfo | null
}

/**
 * Initial state for a new session
 */
export const initialSessionChatState: SessionChatState = {
  runId: null,
  serverStatus: 'created',
  messages: [],
  inputRequest: null,
  connectionStatus: 'disconnected',
  pendingAction: null,
  novncUrl: null,
  novncPassword: null,
  browserViewMode: 'embedded',
  playbackIsLive: true,
  playbackIndex: 0,
  followLatestScreenshot: true,
  highlightedActionId: null,
  controlState: 'agent',
  pendingTakeoverFeedback: false,
  agentMode: null,
  autoApproveTools: [],
  autoApproveAll: false,
  previewFile: null,
  fileMaximized: false,
  mountedFolder: null,
}

// =============================================================================
// Notification Types
// =============================================================================

/**
 * Types of notifications the app can show
 */
export type NotificationType = 'input_request' | 'error' | 'completion'

/**
 * A notification for the user
 */
export interface Notification {
  id: string
  sessionId: number
  sessionName: string
  type: NotificationType
  message: string
  timestamp: number
}
