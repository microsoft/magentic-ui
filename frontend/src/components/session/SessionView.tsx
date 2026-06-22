import { useReducer, useEffect, useMemo, useCallback, useRef } from 'react'
import { cn } from '@/lib/utils'
import { ErrorBoundary } from '@/components/common'
import { Sidebar } from './Sidebar'
import { ChatView } from '@/components/chat'
import { BrowserExpanded } from '@/components/browser'
import { FileExpanded } from '@/components/file'
import {
  useBrowserViewMode,
  useNovncUrl,
  useNovncPassword,
  useChatStore,
  useSessionMessages,
} from '@/stores'
import { useResponsiveLayout } from '@/hooks'
import { useSessionPlayback } from '@/hooks/useSessionPlayback'
import { useWebSocketManager } from '@/hooks/useWebSocketManager'
import { LAYOUT_WIDTHS } from '@/lib/constants'
import type { UISession, BrowserViewMode, FileInfo, ParsedFileMessage } from '@/types'
import { isPreviewable } from '@/lib/fileUtils'

const MAX_CACHED_SESSIONS = 5

interface SessionViewProps {
  sessions: UISession[]
  selectedSessionId?: number
  showSidebar?: boolean
  isLoading?: boolean
  error?: Error | null
  onSessionSelect?: (id: number) => void
  onSessionDeselect?: () => void
  className?: string
}

/**
 * Reducer for managing visited session IDs with LRU eviction.
 */
function visitedReducer(state: number[], selectedId: number | undefined): number[] {
  if (!selectedId) return state
  if (state.length > 0 && state[state.length - 1] === selectedId) {
    // Already at the end, no change needed
    return state
  }

  // Remove if exists (for LRU reordering)
  const filtered = state.filter((id) => id !== selectedId)
  const updated = [...filtered, selectedId]

  // Evict oldest if over limit
  if (updated.length > MAX_CACHED_SESSIONS) {
    return updated.slice(-MAX_CACHED_SESSIONS)
  }
  return updated
}

/**
 * Session view container with multi-session instance caching.
 *
 * Layout modes based on browserViewMode:
 * - embedded: Sidebar + ChatView (browser shows inside ChatView messages)
 * - expanded: Sidebar + ChatView + BrowserExpanded
 * - maximized: Sidebar + BrowserExpanded only (chat hidden)
 *
 * Responsive behavior:
 * - Expanded mode auto-switches to maximized on narrow screens
 *
 * TODO: Consider extracting hooks to reduce component size:
 * - useSessionBrowserControl(): handleControlClick, handleVncDisconnect, takeover logic
 * - useFilePreview(): handleFilePreview, handleFileClose, handleFileToggleMaximize, allSessionFiles
 */
export function SessionView({
  sessions,
  selectedSessionId,
  showSidebar = true,
  isLoading = false,
  error = null,
  onSessionSelect,
  onSessionDeselect,
  className,
}: SessionViewProps) {
  // Track visited sessions for lazy loading (only render ChatView for sessions user has opened)
  const [visitedIds, dispatchVisit] = useReducer(visitedReducer, [] as number[])

  // Update visited sessions when selection changes
  useEffect(() => {
    dispatchVisit(selectedSessionId)
  }, [selectedSessionId])

  // Build a Map for session lookup
  const sessionsById = useMemo(() => new Map(sessions.map((s) => [Number(s.id), s])), [sessions])

  // Get selected session ID as number (used by store selectors below)
  const numericSessionId = selectedSessionId ? Number(selectedSessionId) : undefined

  // =========================================================================
  // File Preview State (per-session, stored in chatStore)
  // =========================================================================

  const previewFile = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).previewFile : null
  )
  const fileMaximized = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).fileMaximized : false
  )
  const setPreviewFile = useChatStore((s) => s.setPreviewFile)
  const setFileMaximized = useChatStore((s) => s.setFileMaximized)

  // Tracks latest sessionId so handleVncDisconnect can ignore stale disconnects
  // from old BrowserExpanded instances unmounting during session switch.
  // Must sync during render (not useEffect) — child cleanup runs before parent effects.
  const currentSessionIdRef = useRef(numericSessionId)
  // eslint-disable-next-line react-hooks/refs -- must sync before child cleanup effects
  currentSessionIdRef.current = numericSessionId

  const browserViewMode = useBrowserViewMode(numericSessionId)
  const novncUrl = useNovncUrl(numericSessionId)
  const novncPassword = useNovncPassword(numericSessionId)
  const setBrowserViewMode = useChatStore((s) => s.setBrowserViewMode)

  // =========================================================================
  // File Preview Handlers (after browser state is declared)
  // =========================================================================

  /** Open file preview panel (closes browser expanded if open) */
  const handleFilePreview = useCallback(
    (file: FileInfo) => {
      if (!numericSessionId) return
      setPreviewFile(numericSessionId, file)
      setFileMaximized(numericSessionId, false)
      // Mutual exclusivity: browser returns to embedded when file preview opens
      if (browserViewMode !== 'embedded') {
        setBrowserViewMode(numericSessionId, 'embedded')
      }
    },
    [numericSessionId, browserViewMode, setBrowserViewMode, setPreviewFile, setFileMaximized]
  )

  /** Close file preview panel */
  const handleFileClose = useCallback(() => {
    if (!numericSessionId) return
    setPreviewFile(numericSessionId, null)
    setFileMaximized(numericSessionId, false)
  }, [numericSessionId, setPreviewFile, setFileMaximized])

  /** Toggle file panel between maximized and side-by-side */
  const handleFileToggleMaximize = useCallback(() => {
    if (!numericSessionId) return
    setFileMaximized(numericSessionId, !fileMaximized)
  }, [numericSessionId, fileMaximized, setFileMaximized])

  /** Change the previewed file (used by FileExpanded dropdown/prev/next) */
  const handleFileChange = useCallback(
    (file: FileInfo) => {
      if (numericSessionId) setPreviewFile(numericSessionId, file)
    },
    [numericSessionId, setPreviewFile]
  )

  // Get playback state setter from chat store (for handleCuaActionClick / chat↔browser sync)
  const setPlaybackState = useChatStore((s) => s.setPlaybackState)

  // Get highlighted action ID for Chat ↔ Browser sync
  const highlightedActionId = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).highlightedActionId : null
  )
  const setHighlightedActionId = useChatStore((s) => s.setHighlightedActionId)

  // CUA action click handler from shared playback hook (eliminates duplicate collectScreenshotActions)
  const { onCuaActionClick, screenshotActions } = useSessionPlayback(numericSessionId)

  // Get takeover state for selected session
  const controlState = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).controlState : ('agent' as const)
  )
  const setControlState = useChatStore((s) => s.setControlState)
  const setPendingTakeoverFeedback = useChatStore((s) => s.setPendingTakeoverFeedback)

  const setPendingAction = useChatStore((s) => s.setPendingAction)
  const chatPendingAction = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).pendingAction : null
  )

  // Get runId for the selected session (needed for WebSocket commands)
  const runId = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).runId : null
  )

  // Get server status for the selected session (needed for takeover logic)
  const serverStatus = useChatStore((s) =>
    numericSessionId ? s.getSessionState(numericSessionId).serverStatus : 'created'
  )

  // WebSocket manager for sending pause command
  const { sendPause } = useWebSocketManager()

  // Get messages for selected session
  const messages = useSessionMessages(numericSessionId)

  // Collect all unique previewable files from session messages.
  //
  // Ordering matches the end-of-run summary that appears under the final
  // answer ("Files you uploaded" first, then "Files the agent created or
  // modified") so the file dropdown / prev-next navigation in the preview
  // stays in sync with what the user just saw in chat. Within each section
  // files keep first-seen order; the latest FileInfo wins so the preview
  // opens the most recent version of each file.
  const allSessionFiles = useMemo(() => {
    type Bucket = 'uploaded' | 'generated'
    const order = new Map<string, { bucket: Bucket; index: number; file: FileInfo }>()
    let counter = 0

    const addFile = (f: FileInfo, bucket: Bucket) => {
      const key = f.url || f.name
      if (!key || !isPreviewable(f.name)) return
      const existing = order.get(key)
      if (existing) {
        // Keep first-seen position but always upgrade to the latest FileInfo.
        // If the file was first seen as uploaded and the agent later modified
        // it, surface it under "generated" so it shows up next to other
        // agent-touched files in the preview list.
        existing.file = f
        if (bucket === 'generated') existing.bucket = 'generated'
      } else {
        order.set(key, { bucket, index: counter++, file: f })
      }
    }

    for (const msg of messages) {
      // User-uploaded files come from the user message at the top of the run
      if (msg.kind === 'user' && msg.attachedFiles) {
        for (const f of msg.attachedFiles) addFile(f, 'uploaded')
      }
      // Files the agent created or modified
      if (msg.kind === 'file') {
        for (const f of msg.files) addFile(f, 'generated')
      }
    }

    return Array.from(order.values())
      .sort((a, b) => {
        if (a.bucket !== b.bucket) return a.bucket === 'uploaded' ? -1 : 1
        return a.index - b.index
      })
      .map((entry) => entry.file)
  }, [messages])

  // Check if screen is wide enough for side-by-side mode (considers sidebar state)
  const { allowSideBySide } = useResponsiveLayout()

  // Track the mode before auto-switching to maximized (for restoration)
  const modeBeforeAutoMaximize = useRef<BrowserViewMode | null>(null)

  // Auto-switch expanded → maximized on narrow screens, restore on wide screens (browser)
  useEffect(() => {
    if (!numericSessionId) return

    if (!allowSideBySide && browserViewMode === 'expanded') {
      modeBeforeAutoMaximize.current = 'expanded'
      setBrowserViewMode(numericSessionId, 'maximized')
    } else if (
      allowSideBySide &&
      browserViewMode === 'maximized' &&
      modeBeforeAutoMaximize.current === 'expanded'
    ) {
      modeBeforeAutoMaximize.current = null
      setBrowserViewMode(numericSessionId, 'expanded')
    }
  }, [allowSideBySide, browserViewMode, numericSessionId, setBrowserViewMode])

  // Auto-switch side-by-side → maximized on narrow screens, restore on wide screens (file preview)
  const fileWasSideBySide = useRef(false)
  // Reset when preview closes so stale ref doesn't affect next open
  useEffect(() => {
    if (!previewFile) fileWasSideBySide.current = false
  }, [previewFile])
  useEffect(() => {
    if (!numericSessionId || !previewFile) return

    if (!allowSideBySide && !fileMaximized) {
      // Going narrow: auto-maximize
      fileWasSideBySide.current = true
      setFileMaximized(numericSessionId, true)
    } else if (allowSideBySide && fileMaximized && fileWasSideBySide.current) {
      // Going wide: restore to side-by-side if we auto-switched
      fileWasSideBySide.current = false
      setFileMaximized(numericSessionId, false)
    }
  }, [allowSideBySide, fileMaximized, numericSessionId, previewFile, setFileMaximized])

  // Auto-switch to live when session becomes active (e.g., after releasing control / resuming)
  const prevServerStatusRef = useRef(serverStatus)
  useEffect(() => {
    const prev = prevServerStatusRef.current
    prevServerStatusRef.current = serverStatus
    if (numericSessionId && serverStatus === 'active' && prev !== 'active') {
      setPlaybackState(numericSessionId, true, 0, true)
      setHighlightedActionId(numericSessionId, null)
    }
  }, [serverStatus, numericSessionId, setPlaybackState, setHighlightedActionId])

  // Auto-open the first agent-created/modified file when the end-of-run
  // summary first appears, so the user can immediately see the most relevant
  // artifact next to the final answer. Skips if:
  //   - There are no agent-created/modified files (uploads only)
  //   - None of the generated files are previewable (e.g., zip)
  //   - The user already has a preview open (don't override their choice)
  // Tracked by message id so historical sessions don't auto-open every time
  // the user revisits them — only fires when a *new* summary message arrives.
  const lastAutoOpenedSummaryIdRef = useRef<string | null>(null)
  useEffect(() => {
    if (!numericSessionId) return
    // Find the most recent summary file message with generated files
    let summaryMsg: ParsedFileMessage | null = null
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i]
      if (m.kind === 'file' && m.summary && m.files.length > 0) {
        summaryMsg = m
        break
      }
    }
    if (!summaryMsg) return
    if (lastAutoOpenedSummaryIdRef.current === summaryMsg.id) return
    lastAutoOpenedSummaryIdRef.current = summaryMsg.id

    // Don't override a preview the user has already opened
    if (previewFile) return

    const firstPreviewable = summaryMsg.files.find((f) => isPreviewable(f.name))
    if (!firstPreviewable) return

    handleFilePreview(firstPreviewable)
  }, [messages, numericSessionId, previewFile, handleFilePreview])

  // Mode change handlers
  const handleModeChange = useCallback(
    (newMode: BrowserViewMode) => {
      if (!numericSessionId) return
      // On narrow screens, skip expanded mode
      if (!allowSideBySide && newMode === 'expanded') {
        // Going to expanded on narrow screen -> go to maximized instead
        setBrowserViewMode(numericSessionId, 'maximized')
      } else {
        setBrowserViewMode(numericSessionId, newMode)
      }
      // Mutual exclusivity: close file preview when browser expands
      if (newMode !== 'embedded' && previewFile) {
        setPreviewFile(numericSessionId, null)
        setFileMaximized(numericSessionId, false)
      }
      // When switching back to embedded mode:
      // Auto-release takeover (can't control in embedded mode)
      if (newMode === 'embedded') {
        // Auto-release takeover when switching to embedded
        if (controlState === 'user') {
          setControlState(numericSessionId, 'agent')
          // Keep pendingTakeoverFeedback true so user is prompted to describe actions
        } else if (controlState === 'user-pending') {
          // Cancel pending takeover (won't transition to 'user' on input_request).
          // Keep pendingAction ('pausing') so the button stays "Pausing..." until
          // the backend responds with input_request (which clears it).
          setControlState(numericSessionId, 'agent')
        }
      }
    },
    [
      numericSessionId,
      allowSideBySide,
      setBrowserViewMode,
      controlState,
      setControlState,
      previewFile,
      setPreviewFile,
      setFileMaximized,
    ]
  )

  // Handle click on CUA action in Chat → jump to corresponding screenshot in Browser
  // (uses shared playback hook to avoid duplicate collectScreenshotActions computation)
  const handleCuaActionClick = onCuaActionClick

  // Handle Control button click - toggle takeover mode
  // Take Control: enable user to interact with browser (VNC viewOnly=false)
  // Release Control: disable interaction, keep pendingTakeoverFeedback true
  const handleControlClick = useCallback(async () => {
    if (!numericSessionId) return

    // RELEASE CONTROL: If already controlling, just release
    if (controlState === 'user') {
      setControlState(numericSessionId, 'agent')
      // Keep pendingTakeoverFeedback true so user is prompted to describe actions
      return
    }

    // TAKE CONTROL: Enable takeover mode

    // Switch to expanded/maximized mode if currently in embedded
    // (user can only interact with browser in expanded/maximized mode)
    if (browserViewMode === 'embedded') {
      setBrowserViewMode(numericSessionId, allowSideBySide ? 'expanded' : 'maximized')
    }

    // Switch to live mode (show VNC, not screenshots)
    setPlaybackState(numericSessionId, true, 0, true)
    setHighlightedActionId(numericSessionId, null)

    // Only send pause if session is actively running
    // For other states, just enable takeover directly
    if (serverStatus === 'active' && runId) {
      // Set controlState to 'user-pending' and a 'pausing' pending action
      // controlState will transition to 'user' when we receive input_request
      setControlState(numericSessionId, 'user-pending')
      setPendingAction(numericSessionId, { type: 'pausing', timestamp: Date.now() })

      // Send pause to backend
      const success = await sendPause(runId, numericSessionId)

      // If send failed, reset control state immediately so control bar is restored
      if (!success) {
        console.warn('Failed to send pause, resetting control state')
        setPendingAction(numericSessionId, null)
        setControlState(numericSessionId, 'agent')
      }
    } else {
      // Session is not active (awaiting_input, complete, error, stopped)
      // Enable takeover immediately without sending pause
      setControlState(numericSessionId, 'user')
      setPendingTakeoverFeedback(numericSessionId, true)
    }
  }, [
    numericSessionId,
    runId,
    serverStatus,
    controlState,
    setPendingAction,
    setControlState,
    setPendingTakeoverFeedback,
    sendPause,
    browserViewMode,
    allowSideBySide,
    setBrowserViewMode,
    setPlaybackState,
    setHighlightedActionId,
  ])

  // VNC disconnect: reset controlState but keep pendingTakeoverFeedback.
  // Guarded against stale disconnects from session switch (currentSessionIdRef)
  // and initial connection failures (BrowserExpanded's hasEverConnectedRef).
  const handleVncDisconnect = useCallback(() => {
    if (!numericSessionId) return
    // Ignore disconnect from a BrowserExpanded that's being unmounted due to session switch
    if (numericSessionId !== currentSessionIdRef.current) return
    if (controlState !== 'agent') {
      setControlState(numericSessionId, 'agent')
      // Only clear pendingAction if not mid-pause — a pending pause request
      // should keep showing "Pausing..." until the backend responds.
      if (chatPendingAction?.type !== 'pausing') {
        setPendingAction(numericSessionId, null)
      }
      // Keep pendingTakeoverFeedback - user should still describe what they did
      // even if VNC dropped (network issue or mode switch unmounting BrowserExpanded)
    }
  }, [numericSessionId, controlState, setControlState, setPendingAction, chatPendingAction])

  // Handle session deletion: auto-select the previous session in the list,
  // or deselect if no sessions remain
  const handleSessionDeleted = useCallback(
    (deletedId: number) => {
      // Only act if the deleted session is the currently selected one
      if (deletedId !== selectedSessionId) return

      // Find the index of the deleted session in the current list
      const idx = sessions.findIndex((s) => s.id === deletedId)
      // Guard: sessions list may have already been refetched without the deleted entry
      if (idx === -1) {
        onSessionDeselect?.()
        return
      }
      // Pick the previous session, or the next one if deleted was first
      const fallback = sessions[idx - 1] ?? sessions[idx + 1]

      if (fallback) {
        onSessionSelect?.(fallback.id)
      } else {
        // No sessions left
        onSessionDeselect?.()
      }
    },
    [selectedSessionId, sessions, onSessionSelect, onSessionDeselect]
  )

  // Show browser panel in expanded/maximized modes (only when file preview is not open)
  // Support both live VNC and screenshot-only modes
  const hasScreenshots = screenshotActions.length > 0
  const showBrowserPanel =
    browserViewMode !== 'embedded' && (novncUrl || hasScreenshots) && !previewFile
  // Show file panel when a file is being previewed
  const showFilePanel = !!previewFile
  // Either panel can hide chat in maximized mode
  const hideChatInMaximized = browserViewMode === 'maximized' || (showFilePanel && fileMaximized)

  return (
    <div className={cn('flex h-full w-full', className)}>
      {/* Sidebar */}
      {showSidebar && (
        <ErrorBoundary>
          {isLoading ? (
            <aside
              aria-label="Session history"
              className="border-sidebar-border bg-sidebar flex h-full w-[340px] shrink-0 flex-col border-r"
            >
              <div className="flex flex-1 items-center justify-center">
                <p className="text-muted-foreground text-lg">Loading sessions...</p>
              </div>
            </aside>
          ) : error ? (
            <aside
              aria-label="Session history"
              className="border-sidebar-border bg-sidebar flex h-full w-[340px] shrink-0 flex-col border-r"
            >
              {/* Real error surfaces via the global ConnectionStatusBanner. */}
              <div className="flex flex-1 items-center justify-center">
                <p className="text-muted-foreground text-lg">No sessions to show</p>
              </div>
            </aside>
          ) : (
            <Sidebar
              sessions={sessions}
              selectedSessionId={selectedSessionId}
              onSessionSelect={onSessionSelect}
              onSessionDeleted={handleSessionDeleted}
            />
          )}
        </ErrorBoundary>
      )}

      {/* Main content area - Chat + Browser layout */}
      <div className="flex h-full min-w-0 flex-1 flex-col">
        <div className="relative flex min-h-0 min-w-0 flex-1">
          {/* Chat area - renders cached instances, shows selected one */}
          {/* Hidden when maximized, but keep rendered for state preservation */}
          <div
            className={cn(
              'relative h-full min-w-0 flex-1',
              // In maximized mode: hide but keep in DOM
              hideChatInMaximized && 'invisible w-0 max-w-0 min-w-0 overflow-hidden'
            )}
            // In side-by-side mode: chat and browser share space equally (flex-1),
            // but chat has max width for readability. Extra space goes to browser.
            style={{
              maxWidth:
                (showBrowserPanel || showFilePanel) && !hideChatInMaximized
                  ? `${LAYOUT_WIDTHS.CHAT_MAX}px`
                  : undefined,
            }}
          >
            {visitedIds.length === 0 ? (
              // No session selected yet
              <div className="flex h-full items-center justify-center">
                <p className="text-muted-foreground text-lg">Select a session to start chatting</p>
              </div>
            ) : (
              // Render all visited sessions, hide non-selected ones
              // Must use visibility (not display:none) so getBoundingClientRect works when saving scroll position
              visitedIds.map((id) => {
                const isSelected = id === selectedSessionId
                return (
                  <div
                    key={id}
                    className={cn(
                      'absolute inset-0 h-full w-full',
                      isSelected ? 'visible z-10' : 'invisible z-0'
                    )}
                  >
                    <ErrorBoundary>
                      <ChatView
                        sessionId={id}
                        sessionTitle={sessionsById.get(id)?.title}
                        isActive={isSelected}
                        browserViewMode={browserViewMode}
                        onBrowserModeChange={handleModeChange}
                        onCuaActionClick={handleCuaActionClick}
                        highlightedActionId={highlightedActionId}
                        onControlClick={handleControlClick}
                        onFilePreview={handleFilePreview}
                      />
                    </ErrorBoundary>
                  </div>
                )
              })
            )}
          </div>

          {/* Browser panel - shown in expanded/maximized modes */}
          {showBrowserPanel && (
            <div
              className={cn(
                'h-full min-w-0',
                // min-w-0 allows flex item to shrink below content size
                // Expanded mode: no left padding (chat provides scrollbar gap), 16px on other sides
                // 1:1 ratio with chat for better readability
                !hideChatInMaximized && 'flex-1 pt-4 pr-4 pb-3',
                // Maximized mode: 16px padding on all sides (chat is hidden)
                // browser takes full width
                hideChatInMaximized && 'flex-1 px-4 pt-4 pb-3'
              )}
            >
              <BrowserExpanded
                key={selectedSessionId}
                novncUrl={novncUrl ?? null}
                novncPassword={novncPassword ?? null}
                sessionId={numericSessionId!}
                mode={browserViewMode}
                onModeChange={handleModeChange}
                isSessionSelected={!!selectedSessionId}
                controlState={controlState}
                onControlClick={handleControlClick}
                onVncDisconnect={handleVncDisconnect}
              />
            </div>
          )}

          {/* File preview panel - shown when a file chip is clicked */}
          {showFilePanel && previewFile && (
            <div
              className={cn(
                'h-full min-w-0',
                !fileMaximized && 'flex-1 pt-4 pr-4 pb-3',
                fileMaximized && 'flex-1 px-4 pt-4 pb-3'
              )}
            >
              <FileExpanded
                file={previewFile}
                allFiles={allSessionFiles}
                isMaximized={fileMaximized}
                onFileChange={handleFileChange}
                onToggleMaximize={handleFileToggleMaximize}
                onClose={handleFileClose}
              />
            </div>
          )}
        </div>

        {/* Disclaimer */}
        <p className="text-muted-foreground shrink-0 pb-3 text-center text-xs">
          MagenticLite can make mistakes. Please monitor its work and intervene if necessary.
        </p>
      </div>
    </div>
  )
}
