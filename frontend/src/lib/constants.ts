/**
 * Application Constants
 *
 * Central location for app-wide configuration values.
 */
import {
  CirclePlay,
  CircleStop,
  CircleCheck,
  CircleAlert,
  Hand,
  CircleDashed,
  CirclePause,
  LoaderCircle,
} from 'lucide-react'
import type { SessionStatus } from '@/types'

// =============================================================================
// Draft Session
// =============================================================================

/**
 * Sentinel session ID for draft (not yet persisted) sessions.
 * Negative to avoid collision with real backend IDs.
 */
export const DRAFT_SESSION_ID = -1

/**
 * Check whether a session ID refers to a local draft (not yet created on backend).
 */
export function isDraftSession(
  sessionId: number | undefined
): sessionId is typeof DRAFT_SESSION_ID {
  return sessionId === DRAFT_SESSION_ID
}

// =============================================================================
// API Configuration
// =============================================================================

/**
 * Base URL for REST API calls
 * In development, Vite proxy handles /api -> backend
 */
export const API_BASE_URL = '/api'

// =============================================================================
// User Configuration
// =============================================================================

/**
 * Default user ID for API calls
 * Must match backend DEFAULT_USER_ID in config.py
 */
export const DEFAULT_USER_ID = 'guestuser@gmail.com'

// =============================================================================
// External Documentation Links
// =============================================================================

const REPO_URL = 'https://github.com/microsoft/magentic-ui/blob/main'

/** Link to the Installation Guide (shown on the onboarding Welcome step). */
export const INSTALLATION_GUIDE_URL = `${REPO_URL}/docs/installation.md`

/** Link to the Model Hosting Guide (shown on Custom Endpoint step and Settings → Model). */
export const MODEL_HOSTING_GUIDE_URL = `${REPO_URL}/docs/model-hosting-guide.md`

/** Documentation link for the recommended Orchestrator model (MagenticBrain). */
export const ORCHESTRATOR_DOC_URL = 'https://aka.ms/MagenticBrain-foundry'

/** Documentation link for the recommended Browser-use model (Fara). */
export const FARA_DOC_URL = 'https://aka.ms/fara-foundry'

// =============================================================================
// Session Status UI Configuration
// =============================================================================

/**
 * Session status UI display configuration
 *
 * Maps each SessionStatus to its visual representation:
 * - icon: Lucide icon component
 * - colorClass: Tailwind color class for text/icon
 * - dotColorClass: Tailwind background color class for notification dot
 * - cardLabel: Status text for SessionCard
 * - chatLabel: Status text for ChatView bottom indicator
 *
 * Used by SessionCard and SessionStatusMessage for consistent status display.
 */
export const SESSION_STATUS_UI_CONFIG: Record<
  SessionStatus,
  {
    icon: typeof CirclePlay
    colorClass: string
    dotColorClass: string
    iconClassName?: string
    cardLabel: string
    chatLabel: string
  }
> = {
  created: {
    icon: CircleDashed,
    colorClass: 'text-status-stopped',
    dotColorClass: 'bg-status-stopped',
    cardLabel: 'Ready to start',
    chatLabel: 'Ready to start',
  },
  active: {
    icon: LoaderCircle,
    colorClass: 'text-status-active',
    dotColorClass: 'bg-status-active',
    iconClassName: 'animate-spin',
    cardLabel: 'In progress',
    chatLabel: 'In progress',
  },
  'awaiting-input': {
    icon: Hand,
    colorClass: 'text-status-waiting-input',
    dotColorClass: 'bg-status-waiting-input',
    cardLabel: 'Waiting for your input',
    chatLabel: 'Waiting for your input',
  },
  paused: {
    icon: CirclePause,
    colorClass: 'text-status-waiting-input',
    dotColorClass: 'bg-status-waiting-input',
    cardLabel: 'Paused',
    chatLabel: 'The task was paused',
  },
  stopped: {
    icon: CircleStop,
    colorClass: 'text-status-stopped',
    dotColorClass: 'bg-status-stopped',
    cardLabel: 'Stopped',
    chatLabel: 'The task was stopped',
  },
  completed: {
    icon: CircleCheck,
    colorClass: 'text-status-completed',
    dotColorClass: 'bg-status-completed',
    cardLabel: 'Completed',
    chatLabel: 'The task is completed',
  },
  error: {
    icon: CircleAlert,
    colorClass: 'text-status-error',
    dotColorClass: 'bg-status-error',
    cardLabel: 'Something went wrong',
    chatLabel: 'Something went wrong',
  },
}

// =============================================================================
// Content Display
// =============================================================================

/**
 * Maximum height (px) for scrollable content blocks (code blocks, tables, pre blocks).
 * Shared by CodeBlock, Markdown table wrappers, and Markdown pre blocks.
 */
export const MAX_CONTENT_BLOCK_HEIGHT = 300

// =============================================================================
// Layout Configuration
// =============================================================================

/**
 * Layout width constants for responsive calculations.
 *
 * Used by useResponsiveLayout hook to dynamically compute breakpoints.
 */
export const LAYOUT_WIDTHS = {
  /** Sidebar width in pixels */
  SIDEBAR: 340,

  /** Minimum chat width when NOT in side-by-side mode */
  CHAT_MIN: 480,

  /** Maximum chat width in side-by-side mode (then extra space goes to browser) */
  CHAT_MAX: 960,

  /** Minimum combined width for side-by-side (chat + browser, each 480px) */
  SIDE_BY_SIDE_MIN: 960,
} as const

// =============================================================================
// File Upload & Preview
// =============================================================================

/**
 * Maximum file upload size in bytes (100 MB).
 */
export const MAX_FILE_UPLOAD_SIZE = 100 * 1024 * 1024

/**
 * File extensions that can be previewed in FileView.
 * Grouped by rendering strategy.
 */
export const PREVIEWABLE_EXTENSIONS = {
  image: ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico'],
  markdown: ['md', 'markdown'],
  code: [
    'js',
    'jsx',
    'ts',
    'tsx',
    'py',
    'java',
    'c',
    'cpp',
    'cs',
    'go',
    'rb',
    'php',
    'html',
    'css',
    'scss',
    'json',
    'xml',
    'yaml',
    'yml',
    'sh',
    'bash',
    'sql',
  ],
  text: ['txt', 'csv', 'log', 'env', 'gitignore', 'dockerignore', 'cfg', 'ini', 'toml'],
  pdf: ['pdf'],
} as const

/**
 * All previewable file extensions (flat set for quick lookup).
 */
export const ALL_PREVIEWABLE_EXTENSIONS: Set<string> = new Set(
  Object.values(PREVIEWABLE_EXTENSIONS).flat()
)

// =============================================================================
// Team Configuration
// =============================================================================

/**
 * Default team configuration for starting a new task.
 * Required by backend WebSocket start message.
 */
export const DEFAULT_TEAM_CONFIG = {
  name: 'Default Team',
  participants: [],
  team_type: 'RoundRobinGroupChat',
  component_type: 'team',
} as const

// =============================================================================
// Notification Configuration
// =============================================================================

/**
 * Maximum number of notifications to keep in storage
 */
export const MAX_NOTIFICATIONS = 100

/**
 * Maps NotificationType to SessionStatus for reusing status UI config.
 */
export const NOTIFICATION_TYPE_TO_STATUS: Record<
  'input_request' | 'error' | 'completion',
  SessionStatus
> = {
  input_request: 'awaiting-input',
  error: 'error',
  completion: 'completed',
}
