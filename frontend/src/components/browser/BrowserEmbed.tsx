/**
 * BrowserEmbed Component
 *
 * Embedded browser view within message list.
 * Uses fixed 16:10 aspect ratio (matching Docker VM screen: 1440x900).
 * Supports screenshot playback with prev/next/Live controls.
 *
 * Playback state is read directly from chatStore via useSessionPlayback hook,
 * eliminating prop drilling through ChatView → MessageList.
 *
 * Layout (top → bottom):
 *   Toolbar (title + expand button)
 *   Viewer area (VNC + screenshot overlay + DescriptionOverlay)
 *   Bottom bar: LIVE toggle + Control (live) or ProgressBar + steps (history)
 */
import { useState, useCallback } from 'react'
import { BrowserViewer } from './BrowserViewer'
import { BrowserHeader } from './BrowserHeader'
import { DescriptionOverlay } from './DescriptionOverlay'
import { PlaybackControlsRow } from './PlaybackControlsRow'
import { usePlaybackControls, getBrowserTitle } from './usePlaybackControls'
import { useSessionPlayback } from '@/hooks'
import type { BrowserViewMode } from '@/types'

// =============================================================================
// Types
// =============================================================================

interface BrowserEmbedProps {
  novncUrl: string | null
  /** Per-slot RFB password from the backend; required for the noVNC handshake. */
  novncPassword: string | null
  /** Session ID — used to read playback state from chatStore */
  sessionId: number
  /** Whether this session is selected/visible - disconnects VNC when hidden to save bandwidth */
  isSessionSelected?: boolean
  /** Called when mode changes via toolbar buttons */
  onModeChange?: (mode: BrowserViewMode) => void
  /** Called when Control button is clicked (switches to expanded view for takeover) */
  onControlClick?: () => void
}

// VM screen aspect ratio (Docker config: 1440x900 = 16:10)
const ASPECT_RATIO = 16 / 10

// =============================================================================
// Component
// =============================================================================

export function BrowserEmbed({
  novncUrl,
  novncPassword,
  sessionId,
  isSessionSelected = true,
  onModeChange,
  onControlClick,
}: BrowserEmbedProps) {
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
  // Track VNC connection status - used to hide Control button when disconnected
  const [isVncConnected, setIsVncConnected] = useState(false)

  const handleVncConnect = useCallback(() => {
    setIsVncConnected(true)
  }, [])

  const handleVncDisconnect = useCallback(() => {
    setIsVncConnected(false)
  }, [])

  // Shared playback logic
  const playbackControls = usePlaybackControls({
    screenshotActions,
    isLive: playbackIsLive,
    currentIndex: playbackIndex,
    onIndexChange: onPlaybackIndexChange,
    isVncConnected,
    followLatest,
    liveActionInfo,
  })

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
    hasContent,
  } = playbackControls

  // Toolbar title
  const title = getBrowserTitle(isVncConnected, hasHistory, playbackIsLive)

  // Show bottom controls when VNC connected or has screenshot history
  const showBottomControls = isVncConnected || hasHistory

  return (
    // Container with fixed width, height adapts to aspect ratio + fixed bottom section
    <div className="border-border bg-card flex w-[480px] max-w-full flex-col overflow-hidden rounded-xl border shadow-sm">
      {/* Toolbar with centered title */}
      <BrowserHeader mode="embedded" onModeChange={onModeChange ?? (() => {})} title={title} />

      {/* VNC Viewer with screenshot overlay + description overlay */}
      <div className="relative w-full" style={{ aspectRatio: ASPECT_RATIO }}>
        {/* VNC: only mount when URL + password are available. The
            password is required for the RFB handshake; without it
            react-vnc would prompt the user. */}
        {isSessionSelected && novncUrl && novncPassword && (
          <BrowserViewer
            url={novncUrl}
            password={novncPassword}
            viewOnly
            className="size-full"
            onConnect={handleVncConnect}
            onDisconnect={handleVncDisconnect}
          />
        )}

        {/* Screenshot overlay: shown when not in live VNC mode */}
        {!displayIsLive && currentScreenshotUrl && (
          <img
            src={currentScreenshotUrl}
            alt={`Screenshot ${validCurrentIndex + 1}`}
            className="bg-card absolute inset-0 size-full object-contain"
          />
        )}

        {/* Description overlay: show when VNC connected or viewing screenshots */}
        {(isVncConnected || !displayIsLive) && (
          <DescriptionOverlay
            thoughts={thoughts}
            actionResult={actionResult}
            hasContent={hasContent}
          />
        )}
      </div>

      {/* Bottom bar: LIVE toggle + Control (live) or ProgressBar + steps (history) */}
      {showBottomControls && (
        <PlaybackControlsRow
          compact
          className="px-3 py-2.5"
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
      )}
    </div>
  )
}
