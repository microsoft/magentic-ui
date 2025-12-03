/**
 * Type Definitions
 *
 * Central type definitions for the frontend application.
 *
 * Files:
 * - api.ts: Backend API types (ServerRunStatus, Session, Run, Message, etc.)
 * - state.ts: Frontend state types (ConnectionStatus, SessionStatus, PendingAction)
 * - store.ts: Zustand store schemas (SessionChatState, Notification)
 * - websocket.ts: WebSocket message formats (server↔client protocol)
 * - message.ts: Parsed message types (discriminated union by 'kind')
 * - ui.ts: UI data types (UISession, User)
 *
 * State Layering:
 * ┌─────────────────────────────────────────────────────────────┐
 * │ Layer 1: ServerRunStatus (api.ts)                           │
 * │   Backend run status: created, active, complete, etc.       │
 * ├─────────────────────────────────────────────────────────────┤
 * │ Layer 2: ConnectionStatus (state.ts)                        │
 * │   WebSocket state: disconnected, connecting, connected      │
 * ├─────────────────────────────────────────────────────────────┤
 * │ Layer 3: SessionStatus (state.ts, computed)                 │
 * │   Display status = f(Layer 1, 2)                            │
 * ├─────────────────────────────────────────────────────────────┤
 * │ Layer 4: PendingAction (state.ts)                           │
 * │   Pending status (button UI only): starting, stopping       │
 * └─────────────────────────────────────────────────────────────┘
 */

// Server/API types
export type {
  ServerRunStatus,
  InputType,
  Session,
  SessionListItem,
  Message,
  MessageContentItem,
  MessageConfig,
  AgentMessageConfig,
  InputRequest,
  SessionRuns,
} from './api'

// State types (Layer 2-4)
export type {
  ConnectionStatus,
  PendingActionType,
  PendingAction,
  SessionStatus,
  ControlState,
} from './state'
export {
  serverStatusToSessionStatus,
  computeSessionStatus,
  ACTIVE_SESSION_STATUSES,
  ACTIVE_RUN_STATUSES,
} from './state'

// Store types
export type { SessionChatState, NotificationType, Notification, BrowserViewMode } from './store'
export { initialSessionChatState } from './store'

// WebSocket types
export { WS_SERVER_MESSAGE_TYPE, WS_CLIENT_MESSAGE_TYPE } from './websocket'
export type { ActiveRun, WsServerMessage, WsClientMessage } from './websocket'

// UI types
export type { UISession } from './ui'

// Browser types
export type { LatestCuaAction } from './browser'

// File types
export type {
  FileType,
  FileInfo,
  FileAttachment,
  FileAttachmentStatus,
  UploadedFileRef,
} from './file'

// Folder types
export type { FolderInfo } from './folder'

// Parsed message types
export type {
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
  ParsedReasoningMessage,
  ParsedFileMessage,
  ParsedTextMessage,
  BrowserToolArgs,
  NonBrowserToolArgs,
} from './message'

// Type guards (only export actually used ones)
export { isCuaBrowserMessage, isParsedInternalMessage, isOptimisticMessage } from './message'
