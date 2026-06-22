/**
 * useConnectionIssue
 *
 * Returns the current backend connection issue (HTTP health + selected
 * session's WS), or `null` when healthy. Drives ConnectionStatusBanner.
 */
// Import chatStore before uiStore: chatStore has a top-level subscription
// that reads `useUIStore.getState()`, so it must be the entry point of the
// circular dependency to avoid undefined imports during module load.
import { useChatStore } from '@/stores/chatStore'
import { useUIStore } from '@/stores/uiStore'
import { useBackendHealthStore } from '@/stores/backendHealthStore'
import { selectConnectionIssue, type ConnectionIssue } from '@/lib/connectionStatus'

/**
 * Get the current connection issue (or `null` when healthy).
 */
export function useConnectionIssue(): ConnectionIssue {
  const selectedSessionId = useUIStore((s) => s.selectedSessionId)
  const reachable = useBackendHealthStore((s) => s.reachable)

  const connectionStatus = useChatStore((s) =>
    selectedSessionId !== undefined
      ? s.getSessionState(selectedSessionId).connectionStatus
      : 'disconnected'
  )
  const serverStatus = useChatStore((s) =>
    selectedSessionId !== undefined ? s.getSessionState(selectedSessionId).serverStatus : null
  )
  const runId = useChatStore((s) =>
    selectedSessionId !== undefined ? s.getSessionState(selectedSessionId).runId : null
  )

  return selectConnectionIssue(reachable, runId != null, serverStatus, connectionStatus)
}
