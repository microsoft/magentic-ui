/**
 * WebSocket Logger
 *
 * Centralized logging utility for all WebSocket-related events.
 *
 * Log Levels:
 * - **Always shown**: warn, error (connection issues, parse failures)
 * - **Debug level**: connection status, incoming/outgoing messages
 *   (hidden by default in browser DevTools; show via Verbose/Debug filter)
 */

const PREFIX = '[WsManager]'

// Color codes for console styling (readable on both light and dark backgrounds)
const COLORS = {
  incoming: 'color: #16a34a; font-weight: bold', // green-600
  outgoing: 'color: #2563eb; font-weight: bold', // blue-600
  sessionId: 'color: #db2777', // pink-600
  source: 'color: #ca8a04', // yellow-600
  type: 'color: #7c3aed', // violet-600
  reset: 'color: inherit',
}

/**
 * Format timestamp for log output
 */
function getTimestamp(): string {
  return new Date().toISOString().slice(11, 23) // HH:MM:SS.mmm
}

// =============================================================================
// Always-On Logging (warn, error)
// =============================================================================

/**
 * Log a warning message (always shown)
 */
export function logWarn(message: string, ...args: unknown[]): void {
  console.warn(`${PREFIX} ${message}`, ...args)
}

/**
 * Log an error message (always shown)
 */
export function logError(message: string, ...args: unknown[]): void {
  console.error(`${PREFIX} ${message}`, ...args)
}

// =============================================================================
// Connection Status Logging (debug level)
// =============================================================================

/**
 * Log connection opened
 */
export function logConnected(sessionId: number, runId: string): void {
  console.debug(`${PREFIX} Connected: session=${sessionId}, run=${runId}`)
}

/**
 * Log connection closed
 */
export function logClosed(sessionId: number, code: number): void {
  console.debug(`${PREFIX} Closed: session=${sessionId}, code=${code}`)
}

/**
 * Log auto-connecting to a live run
 */
export function logAutoConnect(sessionId: number, runId: string): void {
  console.debug(`${PREFIX} Auto-connecting live run: session=${sessionId}, run=${runId}`)
}

/**
 * Log run no longer live (disconnecting)
 */
export function logRunEnded(runId: string): void {
  console.debug(`${PREFIX} Run no longer live: ${runId}`)
}

/**
 * Log disconnect reason
 */
export function logDisconnect(sessionId: number, reason: string): void {
  console.debug(`${PREFIX} ${reason}, disconnecting: session=${sessionId}`)
}

/**
 * Log skipping reconnect (e.g., tab not visible)
 */
export function logSkipReconnect(reason: string): void {
  console.debug(`${PREFIX} ${reason}`)
}

// =============================================================================
// Message Logging (debug level)
// =============================================================================

/**
 * Log an incoming WebSocket message from the server
 *
 * @param sessionId - The session ID this message belongs to
 * @param runId - The run ID
 * @param rawMessage - The raw message string from WebSocket
 * @param parsedMessage - The parsed message object (optional, for display)
 */
export function logWsIncoming(
  sessionId: number,
  runId: string,
  rawMessage: string,
  parsedMessage?: unknown
): void {
  const timestamp = getTimestamp()
  const message = parsedMessage ?? tryParse(rawMessage)
  const messageType = (message as { type?: string })?.type ?? 'unknown'
  const source = (message as { data?: { source?: string } })?.data?.source ?? 'server'
  const metadataType = (message as { data?: { metadata?: { type?: string } } })?.data?.metadata
    ?.type

  // Build title with optional metadata type
  const metadataPart = metadataType ? ` meta=%c${metadataType}%c` : ''
  const title = `%cWS IN%c [${timestamp}] session=%c${sessionId}%c run=%c${runId.slice(0, 8)}%c type=%c${messageType}%c source=%c${source}%c${metadataPart}`

  // Build color args
  const colorArgs = [
    COLORS.incoming,
    COLORS.reset,
    COLORS.sessionId,
    COLORS.reset,
    COLORS.sessionId,
    COLORS.reset,
    COLORS.type,
    COLORS.reset,
    COLORS.source,
    COLORS.reset,
  ]
  if (metadataType) {
    colorArgs.push(COLORS.type, COLORS.reset)
  }

  // Redact known-sensitive fields (e.g. VNC password on browser_address messages)
  // before logging, so credentials never appear in browser DevTools.
  const safeMessage = scrubForLog(message)
  const safeRaw = JSON.stringify(safeMessage)

  console.groupCollapsed(title, ...colorArgs)
  console.debug('Scrubbed JSON:', safeRaw)
  console.debug('Parsed:', safeMessage)
  console.groupEnd()
}

/**
 * Log an outgoing WebSocket message to the server
 *
 * @param sessionId - The session ID this message belongs to
 * @param runId - The run ID
 * @param message - The message object being sent
 */
export function logWsOutgoing(sessionId: number, runId: string, message: unknown): void {
  const timestamp = getTimestamp()
  const messageType = (message as { type?: string })?.type ?? 'unknown'
  const safeMessage = scrubForLog(message)
  const safeRaw = JSON.stringify(safeMessage)

  console.groupCollapsed(
    `%cWS OUT%c [${timestamp}] session=%c${sessionId}%c run=%c${runId.slice(0, 8)}%c type=%c${messageType}`,
    COLORS.outgoing,
    COLORS.reset,
    COLORS.sessionId,
    COLORS.reset,
    COLORS.sessionId,
    COLORS.reset,
    COLORS.type
  )
  console.debug('Scrubbed JSON:', safeRaw)
  console.debug('Parsed:', safeMessage)
  console.groupEnd()
}

/**
 * Try to parse a JSON string, return original string if parsing fails
 */
function tryParse(str: string): unknown {
  try {
    return JSON.parse(str)
  } catch {
    return str
  }
}

// Keys whose values must never appear in console logs. Mirror of the backend
// `_SENSITIVE_LOG_KEYS` set in src/magentic_ui/backend/web/managers/connection.py.
const SENSITIVE_LOG_KEYS = new Set(['password', 'token', 'api_key', 'secret'])

/**
 * Recursively redact known-sensitive values (e.g. VNC password) for log output.
 *
 * Exported for tests; not part of the public API.
 */
export function scrubForLog(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(scrubForLog)
  }
  if (obj !== null && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      result[k] = SENSITIVE_LOG_KEYS.has(k.toLowerCase()) ? '***REDACTED***' : scrubForLog(v)
    }
    return result
  }
  return obj
}
