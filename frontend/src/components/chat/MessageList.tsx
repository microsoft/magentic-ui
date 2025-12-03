/**
 * Chat message list component
 *
 * Handles message rendering including merging related messages:
 * - code-execution + tool-result → single CodeExecutionMessage
 * - Consecutive CUA actions → grouped CuaMessage with BrowserEmbed
 *
 * Performance optimization:
 * - Render items (pairing/grouping) are memoized and only recomputed when message count changes
 * - Individual message rendering is handled by memoized MessageRenderer
 */

import { useMemo, useEffect } from 'react'
import { Globe } from 'lucide-react'
import { MessageRenderer } from './MessageRenderer'
import { CuaMessage, type CuaAction, CollapsibleHeader } from './messages'
import { BrowserEmbed } from '@/components/browser'
import { type ParsedMessage, type BrowserViewMode, type SessionStatus } from '@/types'
import type { FileInfo } from '@/types'
import {
  computeRenderItems,
  insertTimestampSeparators,
  shouldHideStatusIndicator,
} from './messageListUtils'
import { formatChatSeparator } from '@/lib/timeFormat'

// =============================================================================
// Types
// =============================================================================

interface MessageListProps {
  messages: ParsedMessage[]
  sessionId: number
  /** Callback to register item element refs for scroll tracking */
  onItemRef?: (id: string, element: HTMLDivElement | null) => void
  /** noVNC WebSocket URL for browser embed (if available) */
  novncUrl?: string | null
  /** Per-slot RFB password for the noVNC handshake. */
  novncPassword?: string | null
  /** Whether screenshot actions exist (enables browser embed without VNC) */
  hasScreenshots?: boolean
  /** Current session status - used for CUA message tense */
  sessionStatus?: SessionStatus
  /** Whether this session is selected/visible - disconnects VNC when hidden */
  isSessionSelected?: boolean
  /** Current browser view mode - determines how browser is displayed */
  browserViewMode?: BrowserViewMode
  /** Called when mode changes via browser toolbar buttons */
  onBrowserModeChange?: (mode: BrowserViewMode) => void
  /** Called when a CUA action is clicked (for Browser screenshot sync) */
  onCuaActionClick?: (action: CuaAction) => void
  /** ID of the currently highlighted CUA action (from Browser playback) */
  highlightedActionId?: string | null
  /** Called when user clicks the Take Control button in browser toolbar */
  onControlClick?: () => void
  /** Notifies parent when session status indicator should be hidden */
  onHideStatusIndicator?: (hidden: boolean) => void
  /** Called when user clicks a file chip to preview */
  onFilePreview?: (file: FileInfo) => void
}

// Re-export CuaAction type for consumers
export type { CuaAction }

// =============================================================================
// Component
// =============================================================================

/** Renders a list of chat messages with CUA grouping and browser embed */
export function MessageList({
  messages,
  sessionId,
  onItemRef,
  novncUrl,
  novncPassword,
  hasScreenshots = false,
  sessionStatus,
  isSessionSelected = true,
  browserViewMode = 'embedded',
  onBrowserModeChange,
  onCuaActionClick,
  highlightedActionId,
  onControlClick,
  onHideStatusIndicator,
  onFilePreview,
}: MessageListProps) {
  // Compute render items - re-runs when message count, novncUrl, or sessionId changes
  // Internal messages (browser_address, debugging) are always filtered out and logged to console instead.
  // Then layer in inline timestamp separators (independent post-processing pass).
  const renderItems = useMemo(
    () => insertTimestampSeparators(computeRenderItems(messages, novncUrl, hasScreenshots)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messages, novncUrl, hasScreenshots, sessionId]
  )

  // Hide session status indicator when last message already conveys the status
  const hideStatusIndicator = useMemo(
    () => shouldHideStatusIndicator(renderItems, sessionStatus),
    [renderItems, sessionStatus]
  )

  // Notify parent when status indicator visibility changes
  useEffect(() => {
    onHideStatusIndicator?.(hideStatusIndicator)
  }, [hideStatusIndicator, onHideStatusIndicator])

  // Stable ref callback factory - creates callbacks that persist across renders
  // Uses closure-based cache instead of ref to avoid ref access during render
  // eslint-disable-next-line react-hooks/preserve-manual-memoization -- closure-based cache requires manual memoization
  const getRefCallback = useMemo(() => {
    if (!onItemRef) return () => undefined
    const cache = new Map<string, (el: HTMLDivElement | null) => void>()
    return (id: string) => {
      let callback = cache.get(id)
      if (!callback) {
        callback = (el: HTMLDivElement | null) => onItemRef(id, el)
        cache.set(id, callback)
      }
      return callback
    }
  }, [onItemRef])

  return (
    <div role="log" aria-label="Conversation" aria-live="polite" className="flex flex-col gap-6">
      {renderItems.map((item) => {
        switch (item.kind) {
          case 'message':
            return (
              <MessageRenderer
                key={item.message.id}
                ref={getRefCallback(item.message.id)}
                message={item.message}
                sessionId={sessionId}
                codeResultContent={item.codeResultContent}
                toolResultContent={item.toolResultContent}
                onFilePreview={onFilePreview}
              />
            )

          case 'cua-group':
            return (
              <div key={item.groupId} data-cua-group={item.groupId} className="flex w-full">
                <div className="min-w-0 pr-16">
                  <CuaMessage
                    groupId={item.groupId}
                    sessionId={sessionId}
                    actions={item.actions}
                    canUseProgressiveTense={item.canUseProgressiveTense}
                    sessionStatus={sessionStatus}
                    hasLiveBrowser={!!novncUrl}
                    onActionClick={onCuaActionClick}
                    highlightedActionId={highlightedActionId}
                  />
                </div>
              </div>
            )

          case 'cua-placeholder':
            // Show a non-interactive header as placeholder before first CUA action arrives
            return (
              <div key={item.groupId} className="flex w-full">
                <div className="min-w-0 pr-16">
                  <CollapsibleHeader
                    icon={<Globe className="size-4" />}
                    label="Using web browser"
                    isExpanded={false}
                    disabled
                    isActive
                  />
                </div>
              </div>
            )

          case 'browser-embed':
            // Only show embedded browser in embedded mode
            // In expanded/maximized modes, browser is shown in SessionView
            if (browserViewMode !== 'embedded') return null
            return (
              <BrowserEmbed
                key={item.groupId}
                novncUrl={novncUrl ?? null}
                novncPassword={novncPassword ?? null}
                sessionId={sessionId}
                isSessionSelected={isSessionSelected}
                onModeChange={onBrowserModeChange}
                onControlClick={onControlClick}
              />
            )

          case 'timestamp':
            return (
              <div key={item.id} className="flex w-full justify-center">
                <p className="text-muted-foreground text-sm leading-[21px] font-bold tracking-[0.07px]">
                  {formatChatSeparator(item.iso)}
                </p>
              </div>
            )
        }
      })}
    </div>
  )
}
