/**
 * Helpers for deciding whether the current session URL should redirect.
 *
 * Extracted so the decision logic can be unit-tested in isolation, without
 * pulling React Router, TanStack Query, and Zustand into the test setup.
 *
 * Called by `SessionPage` in `App.tsx`. Two scenarios produce a redirect:
 *
 * 1. URL points to the draft sentinel ID but the in-memory draft has been
 *    cleared (e.g., page refresh dropped the Zustand state).
 * 2. URL points to a real session ID that doesn't exist in the API list
 *    (e.g., deleted session, hand-typed ID, stale link). See issue #582.
 *
 * In both cases we send the user to the first session shown in the
 * sidebar (the API list is pre-sorted by latest activity, with the draft
 * — if any — pinned at index 0), or to the dashboard if the list is
 * empty. The sidebar's own error / loading state covers the case where
 * the list itself failed to load.
 */
import { isDraftSession } from './constants'
import type { UISession } from '@/types'

export interface InvalidSessionRedirectInput {
  /** Session ID parsed from the URL (`undefined` when on `/sessions` with no id). */
  sessionId: number | undefined
  /** The in-memory draft session, if any. */
  draftSession: UISession | null
  /** Sessions from the API list (with draft already merged in at index 0 if present). */
  sessions: UISession[]
  /** Whether the API session list is still loading for the first time. */
  isLoading: boolean
  /** Truthy when the API session list failed to load. */
  error: Error | null
}

/**
 * Returns the URL to redirect to, or `null` when the current URL is valid
 * (or we don't have enough information yet to decide).
 */
export function findInvalidSessionRedirect({
  sessionId,
  draftSession,
  sessions,
  isLoading,
  error,
}: InvalidSessionRedirectInput): string | null {
  // No id in URL (e.g., `/sessions`) — nothing to validate.
  if (sessionId === undefined) return null
  // Wait for the API list before deciding, otherwise we'd redirect away
  // from a valid session just because it hasn't loaded yet.
  if (isLoading) return null
  // If the list failed to load, `sessions` is empty for the wrong reason.
  // Don't redirect — let SessionView render its own error state instead
  // of bouncing the user away from the URL they typed.
  if (error) return null

  if (isDraftSession(sessionId)) {
    // Draft sentinel in URL — only redirect when the in-memory draft is gone.
    if (draftSession) return null
  } else {
    // Real session id — only redirect when it isn't in the API list.
    if (sessions.some((s) => s.id === sessionId)) return null
  }

  // Send the user to the top of the sidebar. `sessions[0]` is the draft
  // when one exists (useSessionListWithDraft pins it at the top), and
  // otherwise the most-recent real session.
  const top = sessions[0]
  return top ? `/sessions/${top.id}` : '/'
}
