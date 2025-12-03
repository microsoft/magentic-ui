/**
 * UI Types
 *
 * Types for UI display and component props.
 */

import type { SessionStatus } from './state'

// =============================================================================
// UI Data Types
// =============================================================================

/**
 * Session data for UI display (used by SessionCard, Sidebar, Dashboard, SessionView)
 */
export interface UISession {
  id: number
  title: string
  status: SessionStatus
  /** Latest run ID (string form), if available. */
  runId?: string
  /** ISO timestamp of the latest activity (run.updated_at, falls back to session.created_at). */
  updatedAt?: string | null
}
