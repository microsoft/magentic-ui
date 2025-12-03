import { useEffect, useRef } from 'react'
import type { ParsedMessage } from '@/types'

/**
 * Message kinds that warrant overriding scroll restoration when they arrive
 * in a background session: the user almost certainly wants to see these
 * immediately upon switching back instead of being dropped at their last
 * read position.
 */
const IMPORTANT_KINDS = new Set<string>(['final-answer', 'input-request', 'error'])

/**
 * Per-session record of the last message id the user saw while the chat
 * view was active. Lives at module scope so it survives unmount/remount
 * and is shared across all hook instances.
 *
 * LRU bounded: Map preserves insertion order, so we delete-then-set on
 * update (moves the entry to the end) and evict the oldest entry when at
 * capacity. Mirrors the approach in useScrollRestoration's `scrollStates`.
 */
const lastSeenMessageIdBySession = new Map<number, string>()
const MAX_LAST_SEEN_ENTRIES = 100

function rememberLastSeen(sessionId: number, messageId: string): void {
  // Move to end on update so subsequent eviction targets truly oldest entries
  if (lastSeenMessageIdBySession.has(sessionId)) {
    lastSeenMessageIdBySession.delete(sessionId)
  } else if (lastSeenMessageIdBySession.size >= MAX_LAST_SEEN_ENTRIES) {
    const oldestKey = lastSeenMessageIdBySession.keys().next().value
    if (oldestKey !== undefined) lastSeenMessageIdBySession.delete(oldestKey)
  }
  lastSeenMessageIdBySession.set(sessionId, messageId)
}

/** Test-only: reset module-level state between tests. */
export function _resetLastSeenForTesting(): void {
  lastSeenMessageIdBySession.clear()
}

/** Test-only: peek at recorded value for a session. */
export function _peekLastSeenForTesting(sessionId: number): string | undefined {
  return lastSeenMessageIdBySession.get(sessionId)
}

interface UseScrollToImportantBackgroundMessageOptions {
  /** Session id; hook is a no-op when undefined. */
  sessionId: number | undefined
  /** Whether this chat view is currently the active/visible one. */
  isActive: boolean
  /** Parsed messages for this session, ordered oldest → newest. */
  messages: ParsedMessage[]
  /** Ref to the scroll container that holds [data-scroll-id="..."] elements. */
  scrollRef: React.RefObject<HTMLDivElement | null>
}

/**
 * On session re-entry (background → foreground), scroll directly to the
 * first "important" message that arrived while the user was away — final
 * answer, input request, or error — so they can immediately act on it
 * instead of being dropped at the saved scroll position.
 *
 * While the view is active the hook keeps a per-session pointer to the
 * latest message id; on the next false → true transition it diffs against
 * that pointer to find the first new important message. Uses a double
 * requestAnimationFrame to run *after* both useScrollRestoration's restore
 * and useAutoScrollToBottom's scroll-to-bottom that may have just fired.
 *
 * Crucial implementation detail: the pointer-update effect must NOT advance
 * on the activation render itself. If it did, it would clobber the
 * baseline before the detection effect reads it, and the jump would never
 * happen. The hook handles this with a "was already active" ref guard.
 */
export function useScrollToImportantBackgroundMessage({
  sessionId,
  isActive,
  messages,
  scrollRef,
}: UseScrollToImportantBackgroundMessageOptions): void {
  // While the chat view is active, advance the per-session pointer to the
  // latest message id. Only runs when the view was ALREADY active on the
  // previous render — see the doc comment above for why.
  //
  // Initial value is `false` (not `isActive`) so that even the very first
  // render does not advance the pointer: that lets the detection effect
  // below treat the first activation render uniformly as "false → true".
  const wasActiveForRememberRef = useRef(false)
  useEffect(() => {
    const wasActive = wasActiveForRememberRef.current
    wasActiveForRememberRef.current = isActive
    if (!isActive || !wasActive || sessionId === undefined || messages.length === 0) return
    rememberLastSeen(sessionId, messages[messages.length - 1].id)
  }, [isActive, sessionId, messages])

  // Detection: on false → true transition, find the first important message
  // beyond the baseline and scroll it to the top. Initial value is `false`
  // so even the first render counts as a transition; the "no baseline yet"
  // guard below is what prevents an unwanted jump on first-ever opening.
  const prevIsActiveRef = useRef(false)
  useEffect(() => {
    const wasActive = prevIsActiveRef.current
    prevIsActiveRef.current = isActive
    if (!isActive || wasActive || sessionId === undefined || messages.length === 0) return

    const lastSeen = lastSeenMessageIdBySession.get(sessionId)
    // Skip auto-jump on the very first open of this session in this app
    // session — let normal scroll behavior apply.
    if (!lastSeen) return

    const seenIdx = messages.findIndex((m) => m.id === lastSeen)
    // If the last-seen message is gone (e.g., history truncation), treat
    // everything as new.
    const startIdx = seenIdx >= 0 ? seenIdx + 1 : 0
    const important = messages.slice(startIdx).find((m) => IMPORTANT_KINDS.has(m.kind))
    if (!important) return

    // Advance the baseline to the latest message NOW that we've decided
    // to surface this important message. Otherwise, if the user leaves
    // and comes right back without any other render firing the
    // pointer-update effect (which is gated by `wasActive`), the same
    // important message would be detected again and the hook would jump
    // to it on every re-entry.
    rememberLastSeen(sessionId, messages[messages.length - 1].id)

    let raf2 = 0
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        const container = scrollRef.current
        if (!container) return
        const el = container.querySelector<HTMLElement>(`[data-scroll-id="${important.id}"]`)
        if (el) el.scrollIntoView({ behavior: 'auto', block: 'start' })
      })
    })
    return () => {
      cancelAnimationFrame(raf1)
      if (raf2) cancelAnimationFrame(raf2)
    }
  }, [isActive, sessionId, messages, scrollRef])
}
