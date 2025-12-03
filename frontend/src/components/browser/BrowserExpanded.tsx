/**
 * BrowserExpanded Component
 *
 * Side-by-side browser view container (right side of chat).
 *
 * Playback state is read directly from chatStore via useSessionPlayback hook,
 * eliminating prop drilling.
 *
 * Layout (top → bottom):
 *   Toolbar (title + action buttons)
 *   Viewer area (VNC + screenshot overlay)
 *   Bottom section:
 *     - Normal: ActionDescription + LIVE toggle + Control/ProgressBar
 *     - Takeover: TakeoverNotice (with Release Control button)
 *
 * Modes:
 * - Live: Shows VNC stream with pending action info
 * - Playback: Shows screenshot with completed action info
 * - Takeover: User is controlling, shows TakeoverNotice instead of playback controls
 */
import { useState, useCallback, useRef } from 'react'
import { BrowserViewer } from './BrowserViewer'
import { BrowserHeader } from './BrowserHeader'
import { ActionDescription } from './ActionDescription'
import { PlaybackControlsRow } from './PlaybackControlsRow'
import { TakeoverNotice } from './TakeoverNotice'
import { usePlaybackControls, getBrowserTitle } from './usePlaybackControls'
import { useSessionPlayback } from '@/hooks'
import type { BrowserViewMode, ControlState } from '@/types'

// =============================================================================
// Types
// =============================================================================

interface BrowserExpandedProps {
  /** noVNC WebSocket URL for browser streaming */
  novncUrl: string | null
  /** Per-slot RFB password for the noVNC handshake. */
  novncPassword: string | null
  /** Session ID — used to read playback state from chatStore */
  sessionId: number
  /** Current view mode */
  mode: BrowserViewMode
  /** Called when mode changes via toolbar buttons */
  onModeChange: (mode: BrowserViewMode) => void
  /** Whether this session is selected/visible - disconnects VNC when hidden */
  isSessionSelected?: boolean
  /** Current browser control state */
  controlState?: ControlState
  /** Called when Control button is clicked */
  onControlClick?: () => void
  /** Called when VNC connection is lost (parent should reset takeover state) */
  onVncDisconnect?: () => void
}

// =============================================================================
// Component
// =============================================================================

export function BrowserExpanded({
  novncUrl,
  novncPassword,
  sessionId,
  mode,
  onModeChange,
  isSessionSelected = true,
  controlState = 'agent',
  onControlClick,
  onVncDisconnect,
}: BrowserExpandedProps) {
  // Read playback state directly from store (eliminates prop drilling)
  const {
    screenshotActions,
    liveActionInfo,
    playbackIsLive,
    playbackIndex,
    followLatest,
    onPlaybackIndexChange,
    onSetLive,
  } = useSessionPlayback(sessionId)
  // Track VNC connection status.
  // - Controls Take Control button visibility (hidden until first connect)
  // - On disconnect: resets takeover state via onVncDisconnect callback
  const [isVncConnected, setIsVncConnected] = useState(false)

  // Track whether VNC has ever connected successfully.
  // Used to distinguish "initial connection failure" from "real network drop".
  // VNC may fire disconnect during its initial connection attempt (WebSocket fails
  // then retries) — we must NOT reset takeover state for those transient disconnects.
  const hasEverConnectedRef = useRef(false)

  const handleVncConnect = useCallback(() => {
    hasEverConnectedRef.current = true
    setIsVncConnected(true)
  }, [])

  const handleVncDisconnect = useCallback(() => {
    setIsVncConnected(false)
    // Only notify parent (reset takeover state) if VNC was previously connected.
    // Initial connection failures should not reset controlState.
    if (hasEverConnectedRef.current) {
      onVncDisconnect?.()
    }
  }, [onVncDisconnect])

  // Shared playback logic (eliminates duplicated inline calculations)
  const {
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
  } = usePlaybackControls({
    screenshotActions,
    isLive: playbackIsLive,
    currentIndex: playbackIndex,
    onIndexChange: onPlaybackIndexChange,
    isVncConnected: isVncConnected,
    followLatest,
    liveActionInfo,
  })

  // Key to reset ActionDescription expansion state when content changes
  const contentKey = `${thoughts ?? ''}-${actionResult ?? ''}`

  // User has or is requesting control
  const isUserControl = controlState === 'user' || controlState === 'user-pending'

  // Toolbar title
  const title = getBrowserTitle(isVncConnected, hasHistory, playbackIsLive, isUserControl)

  return (
    <div className="bg-card border-border flex h-full flex-col overflow-hidden rounded-xl border shadow-sm">
      {/* Toolbar */}
      <BrowserHeader mode={mode} onModeChange={onModeChange} title={title} />

      {/* Main content: VNC Viewer (always mounted) + Screenshot overlay */}
      <div className="relative flex-1 overflow-hidden">
        {/* VNC: only mount when URL + password are available. */}
        {isSessionSelected && novncUrl && novncPassword && (
          <BrowserViewer
            url={novncUrl}
            password={novncPassword}
            viewOnly={controlState !== 'user'}
            className="size-full"
            onConnect={handleVncConnect}
            onDisconnect={handleVncDisconnect}
          />
        )}

        {/* Screenshot overlay: shown when not in live VNC mode */}
        {!isUserControl && !displayIsLive && currentScreenshotUrl && (
          <img
            src={currentScreenshotUrl}
            alt={`Screenshot ${validCurrentIndex + 1}`}
            className="bg-card absolute inset-0 size-full object-contain"
          />
        )}
      </div>

      {/* Bottom section: TakeoverNotice when controlling, playback controls otherwise */}
      {/* During takeover + VNC connecting: hide both (no misleading playback bar) */}
      {/* When not takeover: hide controls while VNC connecting in live mode (prevents flash) */}
      {isUserControl ? (
        isVncConnected ? (
          <TakeoverNotice controlState={controlState} onControlClick={onControlClick} />
        ) : null
      ) : isVncConnected || hasHistory ? (
        <div className="flex flex-col gap-3 px-4 pt-4 pb-3">
          {/* Action description (expandable) */}
          <ActionDescription key={contentKey} thoughts={thoughts} actionResult={actionResult} />

          {/* Controls row: LIVE toggle + Control (live) or ProgressBar + steps (history) */}
          <PlaybackControlsRow
            isVncConnected={isVncConnected}
            onControlClick={onControlClick}
            displayIsLive={displayIsLive}
            onSetLive={onSetLive}
            total={total}
            validCurrentIndex={validCurrentIndex}
            onIndexChange={onPlaybackIndexChange}
            canStepBack={canStepBack}
            canStepForward={canStepForward}
            onStepBack={handleStepBack}
            onStepForward={handleStepForward}
            nextTooltip={nextTooltip}
          />
        </div>
      ) : null}
    </div>
  )
}
