/**
 * Hook to ensure session data is loaded into chatStore
 *
 * This hook bridges the gap between REST API and chatStore:
 * - For active sessions: WebSocketManager handles real-time updates
 * - For completed sessions: This hook loads history from API
 *
 * Should be called at the page level (SessionPage), not in ChatView,
 * to keep ChatView as a pure UI component.
 */
import { useEffect } from 'react'
import { useSessionRun } from '@/api/sessions'
import { useChatStore } from '@/stores/chatStore'
import { buildNovncUrl } from '@/lib/utils'
import { isDraftSession } from '@/lib/constants'
import { toAgentMode } from '@/lib/messages'
import type { Message, ParsedMessage } from '@/types'

/**
 * Sessions whose API → store sync has already run during this page lifetime.
 * Module-scoped (not useRef) so it survives SessionPage unmount/remount.
 * Exported for tests; production code should not touch this directly.
 */
export const _syncedSessions = new Set<number>()

/** Reset module-level state. Test-only. */
export function _resetSyncedSessions(): void {
  _syncedSessions.clear()
}

/**
 * Ensures session data is available in chatStore.
 * Fetches from API and syncs to store if needed.
 *
 * @param sessionId - The session ID to ensure data for (undefined = no-op)
 */
export function useEnsureSessionData(sessionId: number | undefined) {
  const effectiveSessionId = isDraftSession(sessionId) ? undefined : sessionId
  const { data: run, isLoading } = useSessionRun(effectiveSessionId)
  const initSession = useChatStore((s) => s.initSession)
  const setMessages = useChatStore((s) => s.setMessages)
  const setNovncUrl = useChatStore((s) => s.setNovncUrl)

  useEffect(() => {
    if (!sessionId || !run) return
    if (_syncedSessions.has(sessionId)) return

    const agentMode = toAgentMode(run.agent_mode)
    initSession(sessionId, run.id, run.status, agentMode)

    const storeMessages: ParsedMessage[] = useChatStore
      .getState()
      .getSessionState(sessionId).messages
    const apiMessages: Message[] = run.messages ?? []

    if (apiMessages.length > 0 || storeMessages.length > 0) {
      const apiMessageIds = new Set(
        apiMessages
          .map((m: Message) => m.id)
          .filter((id): id is number => typeof id === 'number' && id > 0)
      )
      // User messages echoed via WS (negative id) duplicate the API copy that
      // the backend persists alongside the echo — drop store-side dupes by content.
      const apiUserContents = new Set(
        apiMessages
          .filter((m) => m.config?.source === 'user' || m.config?.source === 'user_proxy')
          .map((m) => m.config?.content)
      )
      // WS-streamed messages without a positive backend id, plus any
      // store messages whose id isn't yet in the API snapshot.
      const storeOnlyMessages = storeMessages
        .filter((m) => {
          if (m.kind === 'user' && apiUserContents.has(m.raw.config?.content)) return false
          const rawId = m.raw.id
          if (typeof rawId !== 'number' || rawId <= 0) return true
          return !apiMessageIds.has(rawId)
        })
        .map((m) => m.raw)

      // API as authoritative base, store-only messages appended.
      setMessages(sessionId, [...apiMessages, ...storeOnlyMessages], agentMode)
    }

    const currentMessages = useChatStore.getState().getSessionState(sessionId).messages
    for (let i = currentMessages.length - 1; i >= 0; i--) {
      const msg = currentMessages[i]
      if (msg.kind === 'browser-address') {
        setNovncUrl(sessionId, buildNovncUrl(msg.novncPort))
        break
      }
    }

    _syncedSessions.add(sessionId)
  }, [sessionId, run, initSession, setMessages, setNovncUrl])

  return { isLoading }
}
