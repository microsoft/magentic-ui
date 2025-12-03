/**
 * State Types
 *
 * Layered architecture for frontend state management.
 * Layer 1: Server state (from API) - see api.ts for ServerRunStatus
 * Layer 2: Connection state (WebSocket)
 * Layer 3: Display status (computed from Layer 1-2, NOT Layer 4)
 * Layer 4: Pending status (button UI only - Sending.../Pausing...)
 *
 * Design decision: pendingAction is NOT used in sessionStatus computation.
 * This ensures CUA message tense reflects real backend state, not optimistic UI.
 *
 * TODO: Currently Layer 3 (SessionStatus) is computed separately in two places:
 * - Card: query cache → serverStatusToSessionStatus()
 * - ChatView: chatStore → computeSessionStatus()
 * This leads to potential inconsistency. Future improvement:
 * - Store SessionStatus (Layer 3) directly in a single place (e.g., chatStore)
 * - Compute once when Layer 1/2 changes, then all consumers read the same value
 * - Both Card and ChatView should read from this single source
 */

import type { SessionChatState } from './store'
import type { ServerRunStatus } from './api'

// =============================================================================
// Server Run Status (Layer 1) - Re-exported from api.ts
// =============================================================================

export type { ServerRunStatus } from './api'

// =============================================================================
// Connection Status (Layer 2)
// =============================================================================

/**
 * WebSocket connection status
 */
export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error'

// =============================================================================
// Session Status (Layer 3)
// =============================================================================

/**
 * Session status for UI display and business logic.
 * Computed from Layer 1-2 only. pendingAction (Layer 4) is NOT used here -
 * it's only for button text (Sending.../Stopping...).
 *
 * Mapping:
 * - Server status → directly maps to session status
 * - Connection error → error
 * - Connecting/reconnecting → prefer server status if available, else 'active'
 */
export type SessionStatus =
  | 'created' // New session or run just created
  | 'active' // Run is executing
  | 'awaiting-input' // Agent requesting user input
  | 'paused' // Agent paused by user - waiting for continue/input
  | 'stopped' // User stopped the run (terminal)
  | 'completed' // Run finished successfully
  | 'error' // Run encountered an error

/**
 * Session statuses considered "active" (not terminal).
 * Used for Dashboard "Active" tab and WebSocket connection management.
 *
 * Note: 'paused' is included because:
 * 1. Currently backend sends input_request after pause (maps to 'awaiting-input')
 * 2. Future: If backend sends 'paused' status directly, we want to keep connection alive
 */
export const ACTIVE_SESSION_STATUSES: readonly SessionStatus[] = [
  'created',
  'active',
  'awaiting-input',
  'paused',
] as const

/**
 * Server run statuses that require active WebSocket connection.
 * Uses ServerRunStatus (backend naming) for WebSocket manager.
 */
export const ACTIVE_RUN_STATUSES: readonly ServerRunStatus[] = [
  'created',
  'active',
  'awaiting_input',
  'paused',
] as const

// =============================================================================
// Pending Status (Layer 4)
// =============================================================================

/**
 * Pending action types for optimistic UI updates.
 * Used for button UI only (showing "Sending..." / "Stopping..." / "Pausing...").
 * - 'sending': Message being sent
 * - 'stopping': Stop button clicked, waiting for backend confirmation
 * - 'pausing': Take Control when active (browser takeover)
 */
export type PendingActionType = 'sending' | 'stopping' | 'pausing'

/**
 * Pending action with timestamp for timeout handling
 */
export interface PendingAction {
  type: PendingActionType
  timestamp: number
}

// =============================================================================
// Browser Control State
// =============================================================================

/**
 * Browser control state (who is operating the browser).
 * Stored in SessionChatState, computed from user actions.
 * - 'agent': Agent is controlling the browser (default)
 * - 'user-pending': User requested control, waiting for agent to pause
 * - 'user': User has taken control of the browser
 */
export type ControlState = 'agent' | 'user-pending' | 'user'

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Map server run status to session status.
 *
 * Note: This function should only receive valid ServerRunStatus values.
 * If an unknown status is received, it logs a warning and returns 'error'
 * to make the issue visible rather than silently defaulting to 'created'.
 */
export function serverStatusToSessionStatus(serverStatus: ServerRunStatus | null): SessionStatus {
  if (!serverStatus) return 'created'

  switch (serverStatus) {
    case 'created':
      return 'created'
    case 'active':
      return 'active'
    case 'awaiting_input':
      return 'awaiting-input'
    case 'paused':
      return 'paused'
    case 'stopped':
      return 'stopped'
    case 'complete':
      return 'completed'
    case 'error':
      return 'error'
    default: {
      // Log warning for unknown status - this indicates a type mismatch
      // between frontend and backend that should be investigated
      console.warn(
        `[serverStatusToSessionStatus] Unknown server status: '${serverStatus}'. ` +
          'This may indicate a backend change that needs frontend updates.'
      )
      // Return 'error' to make the issue visible in UI rather than silently
      // defaulting to 'created' which could be misleading
      return 'error'
    }
  }
}

/**
 * Compute session status from layered state.
 * See SessionStatus type for mapping rules.
 */
export function computeSessionStatus(state: SessionChatState): SessionStatus {
  if (state.connectionStatus === 'error') {
    return 'error'
  }

  // Connecting/reconnecting: prefer server status if available, else assume 'active'
  if (state.connectionStatus === 'connecting' || state.connectionStatus === 'reconnecting') {
    if (state.serverStatus && state.serverStatus !== 'created') {
      return serverStatusToSessionStatus(state.serverStatus)
    }
    return 'active'
  }

  return serverStatusToSessionStatus(state.serverStatus)
}
