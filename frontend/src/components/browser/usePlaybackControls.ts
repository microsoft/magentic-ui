/**
 * usePlaybackControls Hook
 *
 * Shared playback logic for browser components (BrowserEmbed, BrowserExpanded).
 * Calculates derived state from screenshot actions + playback position.
 */

import { useMemo, useCallback } from 'react'
import type { LatestCuaAction } from '@/types'
import type { CuaAction } from '@/components/chat/messages'

// =============================================================================
// Types
// =============================================================================

interface UsePlaybackControlsOptions {
  /** CUA actions with screenshots (completed actions only) */
  screenshotActions: CuaAction[]
  /** Whether currently showing live VNC stream */
  isLive: boolean
  /** Current screenshot index (when in playback mode) */
  currentIndex: number
  /** Called when index changes */
  onIndexChange: (index: number) => void
  /** Whether VNC is currently connected */
  isVncConnected: boolean
  /** Whether auto-advancing to latest screenshot */
  followLatest: boolean
  /** Action info for live mode */
  liveActionInfo?: LatestCuaAction
}

interface UsePlaybackControlsResult {
  /** Total number of screenshot actions */
  total: number
  /** Whether there are any screenshots to play back */
  hasHistory: boolean
  /** Whether display is in live mode (user wants live AND VNC connected) */
  displayIsLive: boolean
  /** Current index clamped to valid range */
  validCurrentIndex: number
  /** Screenshot URL for current playback position */
  currentScreenshotUrl: string | undefined
  /** Whether step-back button is enabled */
  canStepBack: boolean
  /** Whether step-forward button is enabled */
  canStepForward: boolean
  /** Step back handler */
  handleStepBack: () => void
  /** Step forward handler */
  handleStepForward: () => void
  /** Tooltip for step-forward button */
  nextTooltip: string
  /** Current thoughts text (from playback or live action) */
  thoughts: string | undefined
  /** Current action result text (from playback or live action) */
  actionResult: string | undefined
  /** Whether there's any content to display in description */
  hasContent: boolean
}

// =============================================================================
// Hook
// =============================================================================

export function usePlaybackControls({
  screenshotActions,
  isLive,
  currentIndex,
  onIndexChange,
  isVncConnected,
  followLatest,
  liveActionInfo,
}: UsePlaybackControlsOptions): UsePlaybackControlsResult {
  const total = screenshotActions.length
  const hasHistory = total > 0

  // Display mode: live only when user wants live AND VNC is actually connected.
  // This controls whether VNC stream or screenshot overlay is shown.
  const displayIsLive = isLive && isVncConnected

  // Clamp index to valid range.
  // When followLatest is true, always show the latest screenshot.
  const validCurrentIndex =
    hasHistory && followLatest ? total - 1 : Math.max(0, Math.min(currentIndex, total - 1))

  // Current screenshot action (playback mode)
  const currentAction = hasHistory ? screenshotActions[validCurrentIndex] : undefined

  // Screenshot URL for current action
  const currentScreenshotUrl = currentAction?.screenshotUrl

  // Step controls — disabled in live mode
  const canStepBack = hasHistory && !displayIsLive && validCurrentIndex > 0
  const canStepForward = hasHistory && !displayIsLive && validCurrentIndex < total - 1

  const handleStepBack = useCallback(() => {
    if (canStepBack) {
      onIndexChange(validCurrentIndex - 1)
    }
  }, [canStepBack, validCurrentIndex, onIndexChange])

  const handleStepForward = useCallback(() => {
    if (canStepForward) {
      onIndexChange(validCurrentIndex + 1)
    }
  }, [canStepForward, validCurrentIndex, onIndexChange])

  // Tooltips
  const nextTooltip = displayIsLive
    ? 'Already on latest'
    : validCurrentIndex >= total - 1
      ? 'Last action'
      : 'Next action'

  // Action description content: use live info when live, playback action otherwise
  const { thoughts, actionResult, hasContent } = useMemo(() => {
    if (displayIsLive) {
      const t = liveActionInfo?.thoughts
      const a = liveActionInfo?.actionResult
      return { thoughts: t, actionResult: a, hasContent: !!(t || a) }
    }
    const t = currentAction?.toolArgs?.thoughts
    const a = currentAction?.actionResult
    return { thoughts: t, actionResult: a, hasContent: !!(t || a) }
  }, [displayIsLive, liveActionInfo, currentAction])

  return {
    total,
    hasHistory,
    displayIsLive,
    validCurrentIndex,
    currentScreenshotUrl,
    canStepBack,
    canStepForward,
    handleStepBack,
    handleStepForward,
    nextTooltip,
    thoughts,
    actionResult,
    hasContent,
  }
}

/**
 * Generate browser title based on connection, playback, and control state.
 */
export function getBrowserTitle(
  isVncConnected: boolean,
  hasHistory: boolean,
  isLive: boolean,
  isUserControl?: boolean
): string {
  if (isUserControl) return 'Browser (User Control)'
  if (!isVncConnected && !hasHistory) return 'Browser'
  // VNC disconnected + screenshots = always show history (e.g., completed session)
  if (!isVncConnected && hasHistory) return 'Browser (History)'
  return isLive ? 'Browser (Live)' : 'Browser (History)'
}
