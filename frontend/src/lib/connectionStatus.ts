/**
 * Connection Status — pure helpers shared by ConnectionStatusBanner and
 * any other surface that mirrors the same state.
 */
import { ACTIVE_RUN_STATUSES, type ConnectionStatus, type ServerRunStatus } from '@/types'

/**
 * The kind of connection problem currently affecting the frontend
 * (`null` when healthy). Today only one variant — HTTP and WS problems
 * are presented the same way. Modeled as a nullable string so future
 * variants don't break call sites that gate on `issue != null`.
 */
export type ConnectionIssue = 'unreachable' | null

/** Text for the unhealthy variant. */
interface ConnectionStatusCopy {
  label: string
  message: string
}

export const CONNECTION_STATUS_COPY: ConnectionStatusCopy = {
  label: 'Connection Error:',
  message: 'Check if the backend is running.',
}

/**
 * Returns `'unreachable'` when HTTP is unreachable OR the selected
 * session's WS is dropped during an active run; `null` otherwise.
 */
export function selectConnectionIssue(
  backendReachable: boolean,
  hasRunId: boolean,
  serverStatus: ServerRunStatus | null,
  connectionStatus: ConnectionStatus
): ConnectionIssue {
  if (!backendReachable) return 'unreachable'

  if (!hasRunId) return null
  // Backend says the run is terminal — disconnect is expected.
  if (serverStatus && !ACTIVE_RUN_STATUSES.includes(serverStatus)) return null

  switch (connectionStatus) {
    case 'reconnecting':
    case 'disconnected':
    case 'error':
      return 'unreachable'
    case 'connecting':
    case 'connected':
    default:
      return null
  }
}
