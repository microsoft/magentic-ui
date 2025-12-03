/**
 * Server/API Types
 *
 * Types that match backend API responses exactly.
 * See index.ts for the layered architecture overview.
 *
 * Backend source: /src/magentic_ui/backend/datamodel/
 */

// =============================================================================
// Server Run Status
// =============================================================================

/**
 * Run status from backend API.
 * Source: /src/magentic_ui/backend/datamodel/db.py → RunStatus
 */
export type ServerRunStatus =
  | 'created'
  | 'active'
  | 'complete'
  | 'error'
  | 'stopped'
  | 'awaiting_input'
  | 'paused'

// =============================================================================
// Input Types
// =============================================================================

/** Input type for user interaction requests. */
export type InputType = 'text_input' | 'approval' | 'continuation'

// =============================================================================
// API Response Types
// =============================================================================

/**
 * Session from backend API (for create/update operations)
 * Note: Field names differ from SessionListItem due to backend API design
 */
export interface Session {
  id: number
  user_id: string
  name: string
  created_at: string
  updated_at: string
}

/**
 * Session list item from backend API (GET /sessions/)
 * Optimized response with latest run info
 *
 * Note: latest_run.run_id is number here (backend returns number),
 * but Run.id is string. Convert to string when using for consistency.
 */
export interface SessionListItem {
  session_id: number
  name: string
  created_at: string | null
  latest_run: {
    run_id: number
    status: ServerRunStatus | null
    /** ISO timestamp of the latest run-status change (UTC). Used for sorting and the SessionCard timestamp. */
    updated_at: string | null
  } | null
}

/**
 * Run from backend API
 */
export interface Run {
  id: string
  session_id: number
  status: ServerRunStatus
  task: MessageConfig | null
  messages: Message[]
  error_message?: string
  /** Pending input request from agent (null if none or already responded) */
  input_request?: InputRequest | null
  /**
   * Agent mode that was active when this run started.
   * Mirrors backend `magentic_ui.magentic_ui_config.AgentMode`. Null on
   * legacy runs created before the column existed; consumers should treat
   * null as "unknown" and avoid hiding any messages (per the
   * information-preservation policy applied in the message parser).
   */
  agent_mode?: string | null
  created_at: string
  updated_at: string
}

/**
 * Message from backend API
 */
export interface Message {
  id?: number
  session_id: number
  run_id: string
  config: AgentMessageConfig
  created_at: string
  user_id?: string
}

/**
 * Agent message configuration - the actual message content
 */
export interface AgentMessageConfig {
  source: string
  content: string | MessageContentItem[]
  metadata?: Record<string, unknown>
}

/**
 * Content item for multimodal messages
 */
export type MessageContentItem =
  | string
  | { type: 'text'; text: string }
  | { type: 'image'; url: string; alt?: string }

/**
 * Base message configuration (for task)
 */
export interface MessageConfig {
  source: string
  content: string
}

/**
 * Input request from backend
 * Indicates agent needs user input. Content is displayed as a message.
 */
export interface InputRequest {
  input_type: InputType
  /** Message content to display (renamed from 'prompt') */
  content?: string
}

/**
 * Session runs response
 */
export interface SessionRuns {
  runs: Run[]
}
