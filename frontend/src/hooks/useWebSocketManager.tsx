/* eslint-disable react-refresh/only-export-components */
// This file exports both the Provider component and hook - co-location is intentional

/**
 * WebSocket Manager Hook
 *
 * App-level manager for all active session WebSocket connections.
 * Maintains connections for all non-completed sessions so they can receive
 * real-time updates even when not actively viewed.
 *
 * Architecture:
 * - Called once at App level
 * - Manages Map<runId, WebSocket> for all active sessions
 * - Dispatches all messages to chatStore
 * - Provides context for components to send messages
 *
 * Key design decisions (to be fulfilled):
 * - Backend runs independently
 * - Frontend can close/open anytime without affecting backend
 * - All non-completed sessions maintain WebSocket connections
 */
import { useEffect, useRef, useCallback, createContext, useContext, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getWsBaseUrl } from '@/api/client'
import { createAuthenticatedWebSocket } from '@/api/auth'
import { sessionKeys } from '@/api/sessions'
import type { SessionListItem, UploadedFileRef } from '@/types'
import { useChatStore } from '@/stores/chatStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useBackendHealthStore } from '@/stores/backendHealthStore'
import { DEFAULT_USER_ID } from '@/lib/constants'
import { buildNovncUrl } from '@/lib/utils'
import type {
  ActiveRun,
  WsServerMessage,
  WsClientMessage,
  Message,
  ConnectionStatus,
  ServerRunStatus,
} from '@/types'
import { ACTIVE_RUN_STATUSES, isOptimisticMessage, type ParsedFileMessage } from '@/types'
import { WS_SERVER_MESSAGE_TYPE, WS_CLIENT_MESSAGE_TYPE } from '@/types/websocket'
import { DEFAULT_TEAM_CONFIG } from '@/lib/constants'
import {
  logWarn,
  logError,
  logConnected,
  logClosed,
  logAutoConnect,
  logRunEnded,
  logDisconnect,
  logSkipReconnect,
  logWsIncoming,
  logWsOutgoing,
} from '@/lib/wsLogger'

// Re-export for convenience (used by App.tsx)
export type { ActiveRun }

// Auto-incrementing ID for WebSocket messages (backend messages have DB ids;
// WS messages need client-generated unique ids to avoid React key collisions)
// Range: -1 to -999_999 (optimistic messages use -1_000_000 and below)
let wsMessageId = 0
function nextWsMessageId(): number {
  return --wsMessageId // negative to avoid collision with backend DB ids
}

// =============================================================================
// Types
// =============================================================================

/** WebSocket connection with metadata */
interface ManagedConnection {
  ws: WebSocket
  sessionId: number
  runId: string
  status: ConnectionStatus
  reconnectAttempts: number
  reconnectTimeout?: ReturnType<typeof setTimeout>
}

/** Context value for components to interact with WebSocket manager */
interface WebSocketManagerContext {
  /** Send a message to a specific run's WebSocket */
  send: (runId: string, message: WsClientMessage) => void
  /** Send start task to a specific run. Returns true if sent successfully. */
  sendStart: (
    runId: string,
    sessionId: number,
    task: string,
    files?: UploadedFileRef[],
    mountDirs?: string[]
  ) => Promise<boolean>
  /** Send stop to a specific run - cancels execution. Returns true if sent successfully. */
  sendStop: (runId: string, sessionId: number) => Promise<boolean>
  /** Send pause to a specific run - pauses execution and triggers input_request. Returns true if sent successfully. */
  sendPause: (runId: string, sessionId: number) => Promise<boolean>
  /**
   * Send input response to a specific run. `files` carries mid-session
   * uploads (must already be uploaded via `/runs/{run_id}/upload`).
   * Returns true if sent successfully.
   */
  sendInputResponse: (
    runId: string,
    sessionId: number,
    response: string,
    files?: UploadedFileRef[]
  ) => Promise<boolean>
  /** Send structured approval response. Returns true if sent successfully. */
  sendApprovalResponse: (
    runId: string,
    sessionId: number,
    decision: 'approve' | 'deny',
    source?: 'user' | 'auto_session'
  ) => Promise<boolean>
  /** Send Continue / Stop on the max-rounds card. Returns true if sent successfully. */
  sendContinuationResponse: (
    runId: string,
    sessionId: number,
    decision: 'continue' | 'stop'
  ) => Promise<boolean>
  /** Get connection status for a run */
  getConnectionStatus: (runId: string) => ConnectionStatus
}

// =============================================================================
// Constants
// =============================================================================

// Reconnect indefinitely with capped exponential backoff. The banner
// keeps the user informed; we don't give up while a run is still active.
const BASE_RECONNECT_DELAY = 1000 // ms, doubles each attempt
const MAX_RECONNECT_DELAY = 15_000
const PING_INTERVAL = 30000

// After this many consecutive failures, treat the whole backend as down
// (not just one socket) and wake up the banner/polling/refetch logic.
const WS_FAILURE_BACKEND_DOWN_THRESHOLD = 3

// =============================================================================
// Context
// =============================================================================

const WebSocketManagerCtx = createContext<WebSocketManagerContext | null>(null)

// No-op context for when provider is not available (e.g., during HMR)
const noopContext: WebSocketManagerContext = {
  send: () => {
    logWarn('send called but WebSocketManagerProvider is not available')
  },
  sendStart: async () => {
    logWarn('sendStart called but WebSocketManagerProvider is not available')
    return false
  },
  sendStop: async () => {
    logWarn('sendStop called but WebSocketManagerProvider is not available')
    return false
  },
  sendPause: async () => {
    logWarn('sendPause called but WebSocketManagerProvider is not available')
    return false
  },
  sendInputResponse: async () => {
    logWarn('sendInputResponse called but WebSocketManagerProvider is not available')
    return false
  },
  sendApprovalResponse: async () => {
    logWarn('sendApprovalResponse called but WebSocketManagerProvider is not available')
    return false
  },
  sendContinuationResponse: async () => {
    logWarn('sendContinuationResponse called but WebSocketManagerProvider is not available')
    return false
  },
  getConnectionStatus: () => 'disconnected',
}

/**
 * Hook to access WebSocket manager from any component
 *
 * Returns a no-op implementation if provider is not available (e.g., during HMR)
 * to prevent errors from crashing the UI.
 */
export function useWebSocketManager(): WebSocketManagerContext {
  const context = useContext(WebSocketManagerCtx)
  if (!context) {
    // During HMR or edge cases, return no-op instead of crashing
    // This prevents "useWebSocketManager must be used within Provider" errors
    logWarn('useWebSocketManager called outside of provider, using no-op')
    return noopContext
  }
  return context
}

// =============================================================================
// Provider Component
// =============================================================================

interface WebSocketManagerProviderProps {
  /** List of active runs to maintain connections for */
  activeRuns: ActiveRun[]
  /** Currently selected session ID (notifications for this session are suppressed) */
  selectedSessionId?: number
  children: ReactNode
}

/**
 * Provider component that manages WebSocket connections for all active sessions.
 * Should be placed near the root of the app, inside QueryClientProvider.
 */
export function WebSocketManagerProvider({
  activeRuns,
  selectedSessionId,
  children,
}: WebSocketManagerProviderProps) {
  // Map of runId -> managed connection
  const connectionsRef = useRef<Map<string, ManagedConnection>>(new Map())

  // Keep activeRuns in a ref for access in message handlers
  const activeRunsRef = useRef<ActiveRun[]>(activeRuns)
  useEffect(() => {
    activeRunsRef.current = activeRuns
  }, [activeRuns])

  // Keep selectedSessionId in a ref for access in message handlers
  const selectedSessionIdRef = useRef<number | undefined>(selectedSessionId)
  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId
  }, [selectedSessionId])

  // Query client for invalidating cache on status changes
  const queryClient = useQueryClient()

  // Store actions
  const setConnectionStatus = useChatStore((s) => s.setConnectionStatus)
  const setServerStatus = useChatStore((s) => s.setServerStatus)
  const addMessage = useChatStore((s) => s.addMessage)
  const replaceOptimisticUserMessage = useChatStore((s) => s.replaceOptimisticUserMessage)
  const setInputRequest = useChatStore((s) => s.setInputRequest)
  const setNovncUrl = useChatStore((s) => s.setNovncUrl)
  const setNovncPassword = useChatStore((s) => s.setNovncPassword)
  const initSession = useChatStore((s) => s.initSession)
  const setPendingAction = useChatStore((s) => s.setPendingAction)
  const setControlState = useChatStore((s) => s.setControlState)
  const setPendingTakeoverFeedback = useChatStore((s) => s.setPendingTakeoverFeedback)
  const getSessionState = useChatStore((s) => s.getSessionState)

  // Ref for send function (used inside createMessageHandler for auto-approve)
  const sendRef = useRef<(runId: string, message: WsClientMessage) => void>(() => {})

  // Notification store
  const addNotification = useNotificationStore((s) => s.addNotification)
  const removeSessionNotifications = useNotificationStore((s) => s.removeSessionNotifications)

  // Helper to get session name from activeRuns or query cache
  const getSessionName = useCallback(
    (sessionId: number): string => {
      // First try activeRuns ref
      const run = activeRunsRef.current.find((r) => r.sessionId === sessionId)
      if (run?.sessionName) {
        return run.sessionName
      }

      // Fallback: try to get from query cache (SessionListItem[])
      const cachedSessions = queryClient.getQueryData<SessionListItem[]>(
        sessionKeys.list(DEFAULT_USER_ID)
      )
      const cachedSession = cachedSessions?.find((s) => s.session_id === sessionId)
      if (cachedSession?.name) {
        return cachedSession.name
      }

      return `Session ${sessionId}`
    },
    [queryClient]
  )

  // Helper to update session status directly in query cache
  // This avoids a refetch - WebSocket is the source of truth for status.
  // Also bumps `updated_at` so the session re-sorts to the top of the list
  // (matches the backend's COALESCE(updated_at, created_at) DESC ordering).
  const updateSessionStatusInCache = useCallback(
    (sessionId: number, status: ServerRunStatus) => {
      const now = new Date().toISOString()
      queryClient.setQueryData<SessionListItem[]>(sessionKeys.list(DEFAULT_USER_ID), (oldData) => {
        if (!oldData) return oldData
        return oldData.map((item) =>
          item.session_id === sessionId && item.latest_run
            ? { ...item, latest_run: { ...item.latest_run, status, updated_at: now } }
            : item
        )
      })
    },
    [queryClient]
  )

  // ---------------------------------------------------------------------------
  // Message Handler Factory
  // ---------------------------------------------------------------------------

  const createMessageHandler = useCallback(
    (sessionId: number, runId: string) => {
      return (event: MessageEvent) => {
        let message: WsServerMessage
        try {
          message = JSON.parse(event.data)
        } catch {
          logError('Failed to parse message:', event.data)
          return
        }

        // Log incoming message (verbose mode only)
        logWsIncoming(sessionId, runId, event.data, message)

        switch (message.type) {
          // =====================================================================
          // SYSTEM: Single source of truth for status updates
          // Handles: paused, complete, error, stopped, active
          //
          // Note: Backend sends 'connected' as a WebSocket connection acknowledgement.
          // This is a connection event, NOT a run status change, so we skip it.
          // The actual run status is initialized via initSession() on connect.
          // =====================================================================
          case WS_SERVER_MESSAGE_TYPE.SYSTEM: {
            const { status, content } = message

            // Skip connection events - they're not run status changes
            // 'connected' is sent by backend when WebSocket connection is established
            if (status === 'connected') {
              break
            }

            // At this point, status should be a valid ServerRunStatus
            // Type assertion is safe because we've filtered out connection events
            setServerStatus(sessionId, status as ServerRunStatus)

            // Terminal states: disconnect and notify
            const isTerminalState = ['complete', 'error', 'stopped'].includes(status)

            if (isTerminalState) {
              // Update sessions list cache directly (WebSocket is source of truth)
              updateSessionStatusInCache(sessionId, status)
              // Remove old input_request notification
              removeSessionNotifications(sessionId, 'input_request')

              // Disconnect - backend won't process messages on this connection anymore
              const connection = connectionsRef.current.get(runId)
              if (connection) {
                logDisconnect(sessionId, `Received system status '${status}'`)
                connection.ws.close(1000, `Run ${status}`)
                connectionsRef.current.delete(runId)
                setConnectionStatus(sessionId, 'disconnected')
              }

              // Add notification (skip if user is viewing this session)
              if (sessionId !== selectedSessionIdRef.current) {
                const notificationType = status === 'complete' ? 'completion' : 'error'
                addNotification({
                  sessionId,
                  sessionName: getSessionName(sessionId),
                  type: notificationType,
                  message: content || (status === 'complete' ? 'Task completed' : `Task ${status}`),
                })
              }
            } else {
              // Non-terminal states (active, paused): just invalidate cache
              queryClient.invalidateQueries({ queryKey: sessionKeys.lists() })

              // If status changed to 'active', clear 'sending' pendingAction
              // This confirms backend received and started processing the user's message
              if (status === 'active') {
                const sessionState = getSessionState(sessionId)
                if (sessionState.pendingAction?.type === 'sending') {
                  setPendingAction(sessionId, null)
                }
              }
            }

            // If system message has content, add it as a displayable message
            if (content) {
              const systemMsg: Message = {
                id: nextWsMessageId(),
                session_id: sessionId,
                run_id: runId,
                config: {
                  source: 'system',
                  content: content,
                  metadata: { type: 'system', status },
                },
                created_at: message.timestamp ?? new Date().toISOString(),
              }
              addMessage(sessionId, systemMsg)
            }
            break
          }

          case WS_SERVER_MESSAGE_TYPE.MESSAGE: {
            const source = message.data?.source

            // User message echo: replace the optimistic message (which has uploading chips)
            // with the backend version (which has complete attached_files with paths)
            if (source === 'user' || source === 'user_proxy') {
              const sessionState = getSessionState(sessionId)
              const hasOptimistic = sessionState.messages.some(isOptimisticMessage)
              if (hasOptimistic) {
                // Replace by removing optimistic and adding backend version
                const msg: Message = {
                  id: nextWsMessageId(),
                  session_id: sessionId,
                  run_id: runId,
                  config: message.data,
                  created_at: message.timestamp ?? new Date().toISOString(),
                }
                replaceOptimisticUserMessage(sessionId, msg)
                // Optimistic message was replaced; avoid adding a duplicate below
                break
              }
              // No optimistic message found; fall through to generic addMessage handler
            }

            const msg: Message = {
              id: nextWsMessageId(),
              session_id: sessionId,
              run_id: runId,
              config: message.data,
              created_at: message.timestamp ?? new Date().toISOString(),
            }
            addMessage(sessionId, msg)

            // Extract noVNC URL + RFB password from the browser_address
            // message. Both arrive together and feed react-vnc so the
            // handshake authenticates without a UI prompt.
            const metadata = message.data?.metadata as
              | { type?: string; novnc_port?: string; password?: string }
              | undefined
            if (metadata?.type === 'browser_address') {
              if (metadata.novnc_port) {
                setNovncUrl(sessionId, buildNovncUrl(metadata.novnc_port))
              }
              // Always update so a new slot without a password doesn't
              // leave a stale credential from a prior slot in the store.
              setNovncPassword(sessionId, metadata.password ?? null)
            }
            break
          }

          case WS_SERVER_MESSAGE_TYPE.MESSAGE_CHUNK:
            // TODO: Handle streaming chunks
            break

          // =====================================================================
          // INPUT_REQUEST: Agent needs user input
          // Does NOT update status (system message does that).
          // Only sets inputRequest state and optionally displays content.
          //
          // If controlState is 'user-pending' (user clicked Take Control),
          // this confirms the agent has paused - enable takeover mode.
          // =====================================================================
          case WS_SERVER_MESSAGE_TYPE.INPUT_REQUEST: {
            // Check if this is a takeover confirmation (user clicked Take Control)
            const sessionState = getSessionState(sessionId)
            if (sessionState.controlState === 'user-pending') {
              // Agent has paused via Take Control - enable takeover mode
              setControlState(sessionId, 'user')
              setPendingTakeoverFeedback(sessionId, true)
              setPendingAction(sessionId, null)
            } else if (sessionState.pendingAction?.type === 'pausing') {
              // Regular pause - just clear pending action
              setPendingAction(sessionId, null)
            }

            // Auto-approve: if session has auto-approve for this tool, respond immediately
            if (message.input_type === 'approval') {
              const autoState = getSessionState(sessionId)
              const shouldAutoApprove =
                autoState.autoApproveAll ||
                (message.tool && autoState.autoApproveTools.includes(message.tool))
              if (shouldAutoApprove) {
                sendRef.current(runId, {
                  type: WS_CLIENT_MESSAGE_TYPE.APPROVAL_RESPONSE,
                  decision: 'approve',
                  source: 'auto_session',
                })
                // Clear any stale input request and restore active status
                setInputRequest(sessionId, null)
                setServerStatus(sessionId, 'active')
                logWsOutgoing(sessionId, runId, { type: 'approval_response (auto)' })
                break
              }
            }

            // Set input request state (determines if next user message is an input response)
            setInputRequest(sessionId, {
              input_type: message.input_type,
              content: message.content,
            })

            // Add notification for input request (skip if user is viewing this session)
            if (sessionId !== selectedSessionIdRef.current) {
              addNotification({
                sessionId,
                sessionName: getSessionName(sessionId),
                type: 'input_request',
                message: message.content || 'Agent needs your input',
              })
            }

            // If input_request has content (or is approval type), add as displayable message
            if (message.content || message.input_type === 'approval') {
              const inputRequestMsg: Message = {
                id: nextWsMessageId(),
                session_id: sessionId,
                run_id: runId,
                config: {
                  source: 'system',
                  content: message.content ?? '',
                  metadata: {
                    type: 'input_request',
                    input_type: message.input_type,
                    ...(message.tool != null && { tool: message.tool }),
                    ...(message.tool_args != null && { tool_args: message.tool_args }),
                    ...(message.category != null && { category: message.category }),
                    ...(message.reason != null && { reason: message.reason }),
                  },
                },
                created_at: message.timestamp ?? new Date().toISOString(),
              }
              addMessage(sessionId, inputRequestMsg)
            }
            break
          }

          case WS_SERVER_MESSAGE_TYPE.PONG:
            break

          // =====================================================================
          // FILE: Generated/modified file notification (PR 283)
          // Backend sends this when new or modified files are detected.
          // Only insert a chat message for newly seen files (dedup by url).
          // =====================================================================
          case WS_SERVER_MESSAGE_TYPE.FILE: {
            const { files, summary, uploaded_files: uploadedFiles } = message
            const hasGenerated = !!files && files.length > 0
            const hasUploaded = !!uploadedFiles && uploadedFiles.length > 0
            // Summary messages may carry only uploaded files (agent didn't
            // change anything but the user attached files). Skip only when
            // there's nothing to render at all.
            if (!hasGenerated && !hasUploaded) break

            // Dedup: skip files we've already seen with same url AND same timestamp.
            // Files with action='modified' always pass through (content changed).
            // The end-of-run summary always passes through too — it's the
            // aggregated list shown under a header after the final answer.
            const sessionState = getSessionState(sessionId)
            const seenFileKeys = new Set(
              sessionState.messages
                .filter((m): m is ParsedFileMessage => m.kind === 'file')
                .flatMap((m) => m.files.map((f) => `${f.url}@${f.timestamp}`))
            )

            const sourceFiles = files ?? []
            const newFiles = summary
              ? sourceFiles
              : sourceFiles.filter(
                  (f) => f.action === 'modified' || !seenFileKeys.has(`${f.url}@${f.timestamp}`)
                )
            if (newFiles.length === 0 && !hasUploaded) break

            // Convert to a displayable message with metadata.type = 'file'
            const fileMsg: Message = {
              id: nextWsMessageId(),
              session_id: sessionId,
              run_id: runId,
              config: {
                source: 'system',
                content: 'File Generated',
                metadata: {
                  type: 'file',
                  files: JSON.stringify(
                    newFiles.map((f) => ({
                      name: f.name,
                      url: f.url,
                      path: f.url,
                      short_path: f.url,
                      extension: f.extension,
                      file_type: f.file_type,
                      type: f.file_type,
                      action: f.action,
                      timestamp: f.timestamp,
                    }))
                  ),
                  ...(summary ? { summary: true } : {}),
                  ...(hasUploaded
                    ? {
                        uploaded_files: JSON.stringify(
                          uploadedFiles.map((f) => ({
                            name: f.name,
                            url: f.url,
                            path: f.url,
                            short_path: f.url,
                            extension: f.extension,
                            file_type: f.file_type,
                            type: f.file_type,
                            timestamp: f.timestamp,
                          }))
                        ),
                      }
                    : {}),
                },
              },
              created_at: message.timestamp ?? new Date().toISOString(),
            }
            addMessage(sessionId, fileMsg)
            break
          }

          default:
            logWarn('Unknown message type:', message)
        }
      }
    },
    [
      setConnectionStatus,
      setServerStatus,
      addMessage,
      replaceOptimisticUserMessage,
      setInputRequest,
      setNovncUrl,
      setNovncPassword,
      queryClient,
      addNotification,
      getSessionName,
      removeSessionNotifications,
      updateSessionStatusInCache,
      getSessionState,
      setControlState,
      setPendingTakeoverFeedback,
      setPendingAction,
    ]
  )

  // ---------------------------------------------------------------------------
  // Connection Management
  // ---------------------------------------------------------------------------

  // Use a ref to store connect function for recursive calls in onclose
  const connectRef = useRef<
    ((runId: string, sessionId: number, initialStatus?: ServerRunStatus) => void) | null
  >(null)

  const connect = useCallback(
    (runId: string, sessionId: number, initialStatus?: ServerRunStatus) => {
      // Skip if already connected or connecting
      const existing = connectionsRef.current.get(runId)
      if (existing && (existing.status === 'connected' || existing.status === 'connecting')) {
        return
      }

      // On retry, keep status as 'reconnecting' (not 'connecting') so the
      // banner doesn't flash every retry cycle.
      const isRetry = existing?.status === 'reconnecting'
      const nextStatus: ConnectionStatus = isRetry ? 'reconnecting' : 'connecting'

      // Initialize session in store with API status to avoid status flicker
      initSession(sessionId, runId, initialStatus)
      setConnectionStatus(sessionId, nextStatus)

      const wsUrl = `${getWsBaseUrl()}/ws/runs/${runId}`
      const ws = createAuthenticatedWebSocket(wsUrl)

      const connection: ManagedConnection = {
        ws,
        sessionId,
        runId,
        status: nextStatus,
        reconnectAttempts: existing?.reconnectAttempts ?? 0,
      }
      connectionsRef.current.set(runId, connection)

      ws.onopen = () => {
        logConnected(sessionId, runId)
        connection.status = 'connected'
        connection.reconnectAttempts = 0
        setConnectionStatus(sessionId, 'connected')
        // A successful WS open also proves the backend is reachable.
        useBackendHealthStore.getState().setReachable(true)
      }

      ws.onmessage = createMessageHandler(sessionId, runId)

      ws.onerror = (error) => {
        // Log only — onclose owns the state transition.
        logError(`Error: session=${sessionId}`, error)
      }

      ws.onclose = (event) => {
        logClosed(sessionId, event.code)

        // Reconnect indefinitely unless the close was clean.
        const shouldReconnect =
          event.code !== 1000 && event.code !== 1001 && connectionsRef.current.has(runId)

        if (shouldReconnect) {
          connection.status = 'reconnecting'
          setConnectionStatus(sessionId, 'reconnecting')

          const delay = Math.min(
            MAX_RECONNECT_DELAY,
            BASE_RECONNECT_DELAY * Math.pow(2, connection.reconnectAttempts)
          )
          connection.reconnectAttempts++

          // Repeated failures → likely the whole backend is down.
          if (connection.reconnectAttempts >= WS_FAILURE_BACKEND_DOWN_THRESHOLD) {
            useBackendHealthStore.getState().setReachable(false)
          }

          logSkipReconnect(
            `Reconnecting session=${sessionId} in ${delay}ms (attempt ${connection.reconnectAttempts})`
          )

          connection.reconnectTimeout = setTimeout(() => {
            // Use ref to call latest connect function
            connectRef.current?.(runId, sessionId)
          }, delay)
        } else {
          connection.status = 'disconnected'
          setConnectionStatus(sessionId, 'disconnected')
          connectionsRef.current.delete(runId)
        }
      }
    },
    [initSession, setConnectionStatus, createMessageHandler]
  )

  // Keep ref updated with latest connect function
  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const disconnect = useCallback(
    (runId: string) => {
      const connection = connectionsRef.current.get(runId)
      if (!connection) return

      // Clear reconnect timeout
      if (connection.reconnectTimeout) {
        clearTimeout(connection.reconnectTimeout)
      }

      // Close WebSocket
      if (connection.ws.readyState === WebSocket.OPEN) {
        connection.ws.close(1000, 'Manager disconnect')
      }

      setConnectionStatus(connection.sessionId, 'disconnected')
      connectionsRef.current.delete(runId)
    },
    [setConnectionStatus]
  )

  // ---------------------------------------------------------------------------
  // Sync connections with activeRuns (live statuses only)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const currentRunIds = new Set(connectionsRef.current.keys())
    const targetRunIds = new Set(
      activeRuns.filter((run) => ACTIVE_RUN_STATUSES.includes(run.status)).map((run) => run.runId)
    )

    // Connect to new runs that are live
    for (const run of activeRuns) {
      if (ACTIVE_RUN_STATUSES.includes(run.status) && !currentRunIds.has(run.runId)) {
        logAutoConnect(run.sessionId, run.runId)
        connect(run.runId, run.sessionId, run.status)
      }
    }

    // Disconnect from runs that are no longer live
    for (const runId of currentRunIds) {
      if (!targetRunIds.has(runId)) {
        logRunEnded(runId)
        disconnect(runId)
      }
    }
  }, [activeRuns, connect, disconnect])

  // Cleanup all connections on unmount
  useEffect(() => {
    const connections = connectionsRef.current
    return () => {
      for (const [runId] of connections) {
        disconnect(runId)
      }
    }
  }, [disconnect])

  // ---------------------------------------------------------------------------
  // Heartbeat - Keep connections alive
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const pingInterval = setInterval(() => {
      for (const [, connection] of connectionsRef.current) {
        if (connection.ws.readyState === WebSocket.OPEN) {
          connection.ws.send(JSON.stringify({ type: WS_CLIENT_MESSAGE_TYPE.PING }))
        }
      }
    }, PING_INTERVAL)

    return () => clearInterval(pingInterval)
  }, [])

  // ---------------------------------------------------------------------------
  // Send Functions
  // ---------------------------------------------------------------------------

  /**
   * Wait for a connection to become ready (OPEN state)
   * Returns a promise that resolves when connected, or rejects after timeout
   */
  const waitForConnection = useCallback(
    (runId: string, timeoutMs: number = 5000): Promise<void> => {
      return new Promise((resolve, reject) => {
        const startTime = Date.now()
        const checkInterval = 50 // Check every 50ms

        const check = () => {
          const connection = connectionsRef.current.get(runId)
          if (connection?.ws.readyState === WebSocket.OPEN) {
            resolve()
            return
          }

          if (Date.now() - startTime > timeoutMs) {
            reject(new Error(`Connection timeout for run ${runId}`))
            return
          }

          setTimeout(check, checkInterval)
        }

        check()
      })
    },
    []
  )

  const send = useCallback((runId: string, message: WsClientMessage) => {
    const connection = connectionsRef.current.get(runId)
    if (connection?.ws.readyState === WebSocket.OPEN) {
      // Log outgoing message (verbose mode only)
      logWsOutgoing(connection.sessionId, runId, message)
      connection.ws.send(JSON.stringify(message))
    } else {
      logWarn(`Cannot send to run ${runId}, not connected`)
    }
  }, [])

  // Keep sendRef in sync for use inside createMessageHandler (auto-approve)
  useEffect(() => {
    sendRef.current = send
  }, [send])

  /**
   * Ensure connection is ready, then send a message.
   * Connects if not connected, waits for connection to be ready.
   */
  const ensureConnectedAndSend = useCallback(
    async (runId: string, sessionId: number, message: WsClientMessage): Promise<boolean> => {
      const connection = connectionsRef.current.get(runId)
      if (!connection || connection.ws.readyState !== WebSocket.OPEN) {
        connect(runId, sessionId)
        try {
          await waitForConnection(runId)
        } catch (error) {
          logError(`Failed to connect for ${message.type}:`, error)
          return false
        }
      }
      send(runId, message)
      return true
    },
    [connect, send, waitForConnection]
  )

  const sendStart = useCallback(
    async (
      runId: string,
      sessionId: number,
      task: string,
      files?: UploadedFileRef[],
      mountDirs?: string[]
    ): Promise<boolean> => {
      setInputRequest(sessionId, null)
      setNovncUrl(sessionId, null)
      setNovncPassword(sessionId, null)

      // Build settings_config with per-session mount directories if provided
      const settingsConfig: Record<string, unknown> =
        mountDirs && mountDirs.length > 0 ? { mount_dirs: mountDirs } : {}

      return ensureConnectedAndSend(runId, sessionId, {
        type: WS_CLIENT_MESSAGE_TYPE.START,
        task,
        ...(files && files.length > 0 ? { files } : {}),
        team_config: DEFAULT_TEAM_CONFIG,
        ...(Object.keys(settingsConfig).length > 0 ? { settings_config: settingsConfig } : {}),
      })
    },
    [ensureConnectedAndSend, setInputRequest, setNovncUrl, setNovncPassword]
  )

  const sendStop = useCallback(
    async (runId: string, sessionId: number): Promise<boolean> => {
      return ensureConnectedAndSend(runId, sessionId, {
        type: WS_CLIENT_MESSAGE_TYPE.STOP,
        reason: 'User requested stop',
      })
    },
    [ensureConnectedAndSend]
  )

  const sendPause = useCallback(
    async (runId: string, sessionId: number): Promise<boolean> => {
      return ensureConnectedAndSend(runId, sessionId, {
        type: WS_CLIENT_MESSAGE_TYPE.PAUSE,
      })
    },
    [ensureConnectedAndSend]
  )

  const sendInputResponse = useCallback(
    async (
      runId: string,
      sessionId: number,
      response: string,
      files?: UploadedFileRef[]
    ): Promise<boolean> => {
      setInputRequest(sessionId, null)
      // Optimistically restore active status so "Waiting for your input" doesn't flash
      setServerStatus(sessionId, 'active')

      const success = await ensureConnectedAndSend(runId, sessionId, {
        type: WS_CLIENT_MESSAGE_TYPE.INPUT_RESPONSE,
        response,
        ...(files && files.length > 0 ? { files } : {}),
      })
      if (!success) {
        setServerStatus(sessionId, 'awaiting_input')
      }
      return success
    },
    [ensureConnectedAndSend, setInputRequest, setServerStatus]
  )

  const sendApprovalResponse = useCallback(
    async (
      runId: string,
      sessionId: number,
      decision: 'approve' | 'deny',
      source: 'user' | 'auto_session' = 'user'
    ): Promise<boolean> => {
      setInputRequest(sessionId, null)
      // Restore status to active immediately so "Waiting for your input" doesn't flash
      setServerStatus(sessionId, 'active')

      const success = await ensureConnectedAndSend(runId, sessionId, {
        type: WS_CLIENT_MESSAGE_TYPE.APPROVAL_RESPONSE,
        decision,
        source,
      })
      if (!success) {
        setServerStatus(sessionId, 'awaiting_input')
      }
      return success
    },
    [ensureConnectedAndSend, setInputRequest, setServerStatus]
  )

  const sendContinuationResponse = useCallback(
    async (runId: string, sessionId: number, decision: 'continue' | 'stop'): Promise<boolean> => {
      setInputRequest(sessionId, null)
      // Restore status before send so "Waiting for your input" doesn't flash.
      setServerStatus(sessionId, 'active')

      const success = await ensureConnectedAndSend(runId, sessionId, {
        type: WS_CLIENT_MESSAGE_TYPE.CONTINUATION_RESPONSE,
        decision,
      })
      if (!success) {
        setServerStatus(sessionId, 'awaiting_input')
      }
      return success
    },
    [ensureConnectedAndSend, setInputRequest, setServerStatus]
  )

  const getConnectionStatus = useCallback((runId: string): ConnectionStatus => {
    return connectionsRef.current.get(runId)?.status ?? 'disconnected'
  }, [])

  // ---------------------------------------------------------------------------
  // Context Value
  // ---------------------------------------------------------------------------

  const contextValue: WebSocketManagerContext = {
    send,
    sendStart,
    sendStop,
    sendPause,
    sendInputResponse,
    sendApprovalResponse,
    sendContinuationResponse,
    getConnectionStatus,
  }

  return (
    <WebSocketManagerCtx.Provider value={contextValue}>{children}</WebSocketManagerCtx.Provider>
  )
}
