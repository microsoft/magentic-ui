/**
 * useSessionPlayback Hook
 *
 * Provides playback state and derived data for browser components.
 * Reads directly from chatStore, eliminating prop drilling through
 * ChatView → MessageList → BrowserEmbed.
 *
 * Used by: BrowserEmbed, BrowserExpanded, SessionView
 */

import { useMemo, useCallback, useRef, useEffect } from 'react'
import { useChatStore, useSessionMessages, usePlaybackState, useNovncUrl } from '@/stores'
import {
  collectScreenshotActions,
  type ScreenshotActionsResult,
} from '@/components/chat/messageListUtils'
import type { LatestCuaAction } from '@/types'
import type { CuaAction } from '@/components/chat/messages'

// =============================================================================
// Types
// =============================================================================

export interface UseSessionPlaybackResult {
  /** CUA actions with screenshots (for progress bar / playback) */
  screenshotActions: CuaAction[]
  /** Action info for live mode (pending action's thoughts, or last completed) */
  liveActionInfo: LatestCuaAction | undefined
  /** Whether currently showing live VNC stream */
  playbackIsLive: boolean
  /** Current playback index */
  playbackIndex: number
  /** Whether auto-advancing to latest screenshot */
  followLatest: boolean
  /** Called when user selects a screenshot index */
  onPlaybackIndexChange: (index: number) => void
  /** Set live mode on/off (true = live view, false = history at last screenshot) */
  onSetLive: (isLive: boolean) => void
  /** Called when a CUA action is clicked in chat — jumps to corresponding screenshot */
  onCuaActionClick: (action: CuaAction) => void
}

// =============================================================================
// Hook
// =============================================================================

export function useSessionPlayback(sessionId: number | undefined): UseSessionPlaybackResult {
  // Read playback state from store
  const { isLive: playbackIsLive, index: playbackIndex, followLatest } = usePlaybackState(sessionId)
  const novncUrl = useNovncUrl(sessionId)
  const setPlaybackState = useChatStore((s) => s.setPlaybackState)
  const setHighlightedActionId = useChatStore((s) => s.setHighlightedActionId)

  // Get messages and compute screenshot actions
  const messages = useSessionMessages(sessionId)
  const { completedActions, pendingAction, hasMessageAfterLastCua } =
    useMemo<ScreenshotActionsResult>(() => collectScreenshotActions(messages), [messages])

  // Ref to access latest completedActions in callbacks without recreating them
  const completedActionsRef = useRef(completedActions)
  useEffect(() => {
    completedActionsRef.current = completedActions
  }, [completedActions])

  // Compute liveActionInfo (same logic as SessionView had)
  const liveActionInfo = useMemo<LatestCuaAction | undefined>(() => {
    if (hasMessageAfterLastCua) return undefined
    if (!novncUrl) return undefined

    if (pendingAction) {
      return {
        thoughts: pendingAction.toolArgs?.thoughts || undefined,
      }
    }
    if (completedActions.length > 0) {
      const lastCompleted = completedActions[completedActions.length - 1]
      return {
        thoughts: lastCompleted.toolArgs?.thoughts || undefined,
        actionResult: lastCompleted.actionResult || undefined,
      }
    }
    return undefined
  }, [completedActions, pendingAction, hasMessageAfterLastCua, novncUrl])

  // Playback handlers
  const onPlaybackIndexChange = useCallback(
    (index: number) => {
      if (sessionId === undefined) return
      const total = completedActionsRef.current.length
      const isLast = total > 0 && index >= total - 1
      // Follow latest when user navigates to last screenshot, stop following otherwise
      // Always exit VNC live mode when manually navigating
      setPlaybackState(sessionId, false, index, isLast)
      const action = completedActionsRef.current[index]
      setHighlightedActionId(sessionId, action?.messageId ?? null)
    },
    [sessionId, setPlaybackState, setHighlightedActionId]
  )

  const onSetLive = useCallback(
    (isLive: boolean) => {
      if (sessionId === undefined) return
      if (isLive) {
        // Switching to VNC live: follow latest screenshots too
        setPlaybackState(sessionId, true, 0, true)
        setHighlightedActionId(sessionId, null)
      } else {
        // Switching to history: show last screenshot, follow latest
        const lastIndex = Math.max(0, completedActionsRef.current.length - 1)
        setPlaybackState(sessionId, false, lastIndex, true)
      }
    },
    [sessionId, setPlaybackState, setHighlightedActionId]
  )

  const onCuaActionClick = useCallback(
    (action: CuaAction) => {
      if (sessionId === undefined) return
      const index = completedActionsRef.current.findIndex((a) => a.messageId === action.messageId)
      if (index >= 0) {
        const total = completedActionsRef.current.length
        const isLast = index >= total - 1
        setPlaybackState(sessionId, false, index, isLast)
        setHighlightedActionId(sessionId, action.messageId)
      }
    },
    [sessionId, setPlaybackState, setHighlightedActionId]
  )

  return {
    screenshotActions: completedActions,
    liveActionInfo,
    playbackIsLive,
    playbackIndex,
    followLatest,
    onPlaybackIndexChange,
    onSetLive,
    onCuaActionClick,
  }
}
