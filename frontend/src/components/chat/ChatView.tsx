import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { ChatInput } from './ChatInput'
import { clearInputDraft, setInputDraft } from '@/lib/inputDrafts'
import { MessageList } from './MessageList'
import { SessionStatusIndicator } from './messages'
import { SampleTaskCards } from '@/components/common'
import { ChatInputBanner } from './ChatInputBanner'
import { shouldUseInputResponse } from './chatViewUtils'
import {
  useScrollRestoration,
  useScrollToImportantBackgroundMessage,
  useAutoScrollToBottom,
  useWebSocketManager,
} from '@/hooks'
import type { SampleTask } from '@/lib/sampleTasks'
import { consumePendingSampleTask } from '@/lib/sampleTasks'
import {
  useSessionMessages,
  useSessionStatus,
  useChatStore,
  useNotificationStore,
  useNovncUrl,
  useNovncPassword,
  useMountedFolder,
  useSessionAgentMode,
  useIsCuaActive,
  useUIStore,
  useBackendHealthStore,
} from '@/stores'
import {
  useSessionRun,
  useUpdateSession,
  createSession,
  fetchSessionRuns,
  sessionKeys,
} from '@/api/sessions'
import { useCurrentAgentMode } from '@/api/onboarding'
import type {
  BrowserViewMode,
  SessionListItem,
  FileAttachment,
  FileInfo,
  FolderInfo,
  UploadedFileRef,
} from '@/types'
import { ACTIVE_SESSION_STATUSES } from '@/types'
import type { CuaAction } from './messages'
import { isDraftSession, DEFAULT_USER_ID } from '@/lib/constants'
import { uploadFiles } from '@/api/files'
import { createFileAttachment } from '@/lib/fileUtils'
import type { Message } from '@/types/api'

// Negative IDs for optimistic messages (range: -1_000_000 and below)
// Separated from WS message IDs (range: -1 to -999_999) to avoid collision
let optimisticMsgId = -1_000_000

// Message shown above the chat input after the user releases browser control,
// reminding them that the agent needs feedback before continuing.
const TAKEOVER_FEEDBACK_BANNER_MESSAGE =
  'Tell the agent what you changed in the browser, what to do next, or just type **Continue**.'

interface ChatViewProps {
  sessionId?: number
  sessionTitle?: string
  className?: string
  /** Whether this chat view is currently active/visible (for scroll, notifications, VNC) */
  isActive?: boolean
  /** Current browser view mode - determines how browser is displayed */
  browserViewMode?: BrowserViewMode
  /** Called when mode changes via browser toolbar buttons */
  onBrowserModeChange?: (mode: BrowserViewMode) => void
  /** Called when a CUA action is clicked (for Browser screenshot sync) */
  onCuaActionClick?: (action: CuaAction) => void
  /** ID of the currently highlighted CUA action (from Browser playback) */
  highlightedActionId?: string | null
  /** Called when user clicks Control button in browser toolbar */
  onControlClick?: () => void
  /** Called when user clicks a file chip to preview */
  onFilePreview?: (file: FileInfo) => void
}

/**
 * Chat view component displaying conversation messages and input.
 * Layout: scrollable message area + fixed input at bottom.
 * - Preserves scroll position when switching between sessions
 * - Auto-scrolls to bottom when new messages arrive (if user is at bottom)
 * - Shows embedded browser when browserViewMode is 'embedded'
 */
export function ChatView({
  sessionId,
  sessionTitle,
  className,
  isActive = true,
  browserViewMode = 'embedded',
  onBrowserModeChange,
  onCuaActionClick,
  highlightedActionId,
  onControlClick,
  onFilePreview,
}: ChatViewProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Get messages and status from chat store
  const messages = useSessionMessages(sessionId)
  const sessionStatus = useSessionStatus(sessionId)
  const novncUrl = useNovncUrl(sessionId)
  const novncPassword = useNovncPassword(sessionId)
  // Block Send when disconnected. Banner explains why.
  const backendReachable = useBackendHealthStore((s) => s.reachable)

  // Scroll restoration for switching between sessions
  const { scrollRef, handleItemRef } = useScrollRestoration({
    key: sessionId ? String(sessionId) : undefined,
    isActive,
  })

  // On session re-entry, jump to a final-answer / input-request / error
  // that arrived while the view was in the background, instead of restoring
  // the stale saved scroll position.
  useScrollToImportantBackgroundMessage({
    sessionId,
    isActive,
    messages,
    scrollRef,
  })

  // Check if any screenshots exist (enables browser embed without VNC)
  const hasScreenshots = useMemo(() => messages.some((m) => m.kind === 'screenshot'), [messages])

  // Loading state for past sessions (skip for draft sessions)
  const { isLoading: isLoadingMessages } = useSessionRun(
    isDraftSession(sessionId) ? undefined : sessionId
  )

  // Get runId from store (set by useEnsureSessionData in SessionPage)
  const runId = useChatStore((s) => (sessionId ? s.getSessionState(sessionId).runId : null))

  // Auto-scroll to bottom when new messages arrive (shares scrollRef with useScrollRestoration)
  useAutoScrollToBottom({
    scrollRef,
    itemCount: messages.length,
    isActive,
  })

  // Scroll to last CUA group when switching back to embedded mode
  // (browser embed is at the bottom of messages, likely off-screen)
  const prevBrowserModeRef = useRef(browserViewMode)
  useEffect(() => {
    const prev = prevBrowserModeRef.current
    prevBrowserModeRef.current = browserViewMode
    let rafId: number | undefined
    if (browserViewMode === 'embedded' && prev !== 'embedded' && scrollRef.current) {
      // Use requestAnimationFrame to wait for DOM update after mode switch
      rafId = requestAnimationFrame(() => {
        const container = scrollRef.current
        if (!container) return
        // Find last CUA group and scroll it to the top of the viewport
        const cuaGroups = container.querySelectorAll('[data-cua-group]')
        const lastGroup = cuaGroups[cuaGroups.length - 1] as HTMLElement | undefined
        if (lastGroup) {
          lastGroup.scrollIntoView({ behavior: 'smooth', block: 'start' })
        } else {
          // Fallback: scroll to bottom if no CUA groups
          container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
        }
      })
    }
    return () => {
      if (rafId !== undefined) cancelAnimationFrame(rafId)
    }
  }, [browserViewMode, scrollRef])

  // Get WebSocket manager functions
  const { sendStart, sendInputResponse, sendStop } = useWebSocketManager()

  // Get mounted folder for this session (to pass as mount_dirs in start message)
  const mountedFolder = useMountedFolder(sessionId)

  // Hide upload + folder-mount when Fara is the active agent. Fall back to the
  // user's saved agent_mode for draft sessions; while it's still loading, treat
  // as Fara to avoid flashing the buttons to a Fara-only user.
  const sessionAgentMode = useSessionAgentMode(sessionId)
  const { agentMode: currentAgentMode, isLoading: isCurrentAgentModeLoading } =
    useCurrentAgentMode()
  const effectiveAgentMode = sessionAgentMode ?? currentAgentMode
  const isFaraOnly =
    effectiveAgentMode === 'websurfer_only' ||
    (sessionAgentMode == null && isCurrentAgentModeLoading)
  // Gate the in-flight CUA check on a still-running session so an orphaned
  // tool_call (e.g. session stopped mid-delegation) doesn't permanently hide
  // the follow-up upload UI.
  const isSessionRunning =
    sessionStatus !== undefined && ACTIVE_SESSION_STATUSES.includes(sessionStatus)
  const isCuaActive = useIsCuaActive(sessionId) && isSessionRunning

  // Draft session management
  const clearDraftSession = useUIStore((s) => s.clearDraftSession)
  const initSession = useChatStore((s) => s.initSession)
  const addMessage = useChatStore((s) => s.addMessage)
  const setMountedFolder = useChatStore((s) => s.setMountedFolder)
  const updateOptimisticFileStatus = useChatStore((s) => s.updateOptimisticFileStatus)

  // Get pending action for optimistic UI (e.g., showing "Stopping..." state)
  const pendingAction = useChatStore((s) =>
    sessionId ? s.getSessionState(sessionId).pendingAction : null
  )
  const setPendingAction = useChatStore((s) => s.setPendingAction)

  // Get inputRequest state - indicates backend is waiting for user input
  const hasInputRequest = useChatStore((s) =>
    sessionId ? s.getSessionState(sessionId).inputRequest !== null : false
  )
  // Approvals are decisions, not messages: backend ignores any
  // attachments on an approval response.
  const isPendingApproval = useChatStore((s) =>
    sessionId ? s.getSessionState(sessionId).inputRequest?.input_type === 'approval' : false
  )

  // Get takeover state
  const controlState = useChatStore((s) =>
    sessionId ? s.getSessionState(sessionId).controlState : ('agent' as const)
  )
  const setControlState = useChatStore((s) => s.setControlState)
  const pendingTakeoverFeedback = useChatStore((s) =>
    sessionId ? s.getSessionState(sessionId).pendingTakeoverFeedback : false
  )
  const setPendingTakeoverFeedback = useChatStore((s) => s.setPendingTakeoverFeedback)

  // Timeout for pending actions - clear if stuck for too long (e.g., backend crashed)
  // Timeout: clear stuck pending actions (e.g., backend crashed during stop/pause/send).
  // Skip draft sessions — draft 'sending' can take arbitrarily long (file uploads)
  // and is cleaned up by createDraftSession's clearSession on next New Session.
  const PENDING_ACTION_TIMEOUT = 10000 // 10 seconds
  useEffect(() => {
    if (!pendingAction || !sessionId) return
    if (isDraftSession(sessionId)) return // draft cleanup handled by createDraftSession

    const elapsed = Date.now() - pendingAction.timestamp
    const remaining = PENDING_ACTION_TIMEOUT - elapsed

    const clearPending = () => {
      console.warn('[ChatView] Pending action timed out, clearing:', pendingAction.type)
      setPendingAction(sessionId, null)
      // If takeover was pending (Take Control while active), reset controlState too
      // Otherwise it stays stuck at 'user-pending' with a disabled button forever
      if (pendingAction.type === 'pausing' && controlState === 'user-pending') {
        setControlState(sessionId, 'agent')
      }
    }

    if (remaining <= 0) {
      clearPending()
      return
    }

    const timeoutId = setTimeout(clearPending, remaining)
    return () => clearTimeout(timeoutId)
  }, [pendingAction, sessionId, setPendingAction, controlState, setControlState])

  // Session update mutation for auto-renaming
  const updateSession = useUpdateSession()
  const updateSessionName = useNotificationStore((s) => s.updateSessionName)
  const removeSessionNotifications = useNotificationStore((s) => s.removeSessionNotifications)

  // Clear notifications when viewing this session
  useEffect(() => {
    if (sessionId && isActive) {
      removeSessionNotifications(sessionId)
    }
  }, [sessionId, isActive, removeSessionNotifications])

  /**
   * Build and inject an optimistic user message into the chat store.
   * Shows immediately in the UI before backend confirms.
   */
  const injectOptimisticUserMessage = useCallback(
    (
      targetSessionId: number,
      targetRunId: string,
      message: string,
      files?: FileAttachment[],
      folder?: FolderInfo
    ) => {
      const attachedFiles: FileInfo[] | undefined =
        files && files.length > 0
          ? files.map((f) => ({
              name: f.name,
              url: '',
              path: '',
              extension: f.name.split('.').pop() || '',
              file_type: f.mimeType,
              action: 'created' as const,
              timestamp: Date.now() / 1000,
              uploadStatus: 'uploading' as const,
            }))
          : undefined

      const optimisticMsg: Message = {
        id: --optimisticMsgId,
        session_id: targetSessionId,
        run_id: targetRunId,
        config: {
          source: 'user',
          content: message,
          metadata: {
            _optimistic: true,
            ...(attachedFiles ? { attached_files: JSON.stringify(attachedFiles) } : {}),
            ...(folder ? { mounted_folder: folder } : {}),
          },
        },
        created_at: new Date().toISOString(),
      }
      addMessage(targetSessionId, optimisticMsg)
    },
    [addMessage]
  )

  /** Upload pending attachments for a run and return WS file refs. */
  const uploadAttachmentsForRun = useCallback(
    async (
      targetSessionId: number,
      targetRunId: string,
      files: FileAttachment[] | undefined,
      logContext: string
    ): Promise<UploadedFileRef[] | undefined> => {
      if (!files || files.length === 0) return undefined
      try {
        const uploadResult = await uploadFiles(
          targetRunId,
          files.map((f) => f.file)
        )
        updateOptimisticFileStatus(targetSessionId, 'uploaded')
        return uploadResult.files.map((f) => ({
          name: f.name,
          path: f.relative_path,
          uploaded: true,
        }))
      } catch (err) {
        console.error(`File upload failed (${logContext}):`, err)
        updateOptimisticFileStatus(targetSessionId, 'error')
        return undefined
      }
    },
    [updateOptimisticFileStatus]
  )

  /**
   * Promote a draft session to a real backend session and send the first message.
   * Returns early from handleSend — caller should not continue after calling this.
   */
  const promoteDraftAndSend = useCallback(
    async (message: string, files?: FileAttachment[]) => {
      setPendingAction(sessionId!, { type: 'sending', timestamp: Date.now() })

      // Capture mount dirs before draft is cleared
      const mountDirs = mountedFolder ? [mountedFolder.path] : undefined

      // Track whether a real session was created, so catch/early-return can clean up properly
      let createdSessionId: number | null = null

      try {
        // Create session with message as name
        const sessionName = message.slice(0, 100).trim() || 'New Session'
        const session = await createSession({ name: sessionName, user_id: DEFAULT_USER_ID })
        createdSessionId = session.id

        // Fetch the auto-created run to get runId
        const runsData = await fetchSessionRuns(session.id, DEFAULT_USER_ID)
        const run = runsData.runs[0]
        if (!run) {
          console.error('No run found for newly created session')
          // Clean up draft state and navigate to the created session
          // (session exists on backend, just has no run — user can retry from there)
          setPendingAction(sessionId!, null)
          clearInputDraft(sessionId!)
          clearDraftSession()
          navigate(`/sessions/${session.id}`, { replace: true })
          return
        }

        // Initialize chatStore with real session
        initSession(session.id, run.id, run.status)

        // Optimistically inject user message immediately
        injectOptimisticUserMessage(session.id, run.id, message, files, mountedFolder ?? undefined)

        // Set pendingAction on real session (draft keeps its pending until navigate)
        setPendingAction(session.id, { type: 'sending', timestamp: Date.now() })

        // Inject new session into query cache for instant sidebar update.
        // `latest_run.updated_at` is set to now so the session sorts to the top
        // (matches the backend's COALESCE(updated_at, created_at) DESC ordering).
        queryClient.setQueryData(
          sessionKeys.list(DEFAULT_USER_ID),
          (old: SessionListItem[] | undefined) => {
            const now = new Date().toISOString()
            const newItem: SessionListItem = {
              session_id: session.id,
              name: sessionName,
              created_at: now,
              latest_run: { run_id: Number(run.id), status: run.status, updated_at: now },
            }
            return old ? [newItem, ...old] : [newItem]
          }
        )

        // Invalidate in background so cache stays accurate
        queryClient.invalidateQueries({ queryKey: sessionKeys.lists() })

        // Upload files if any (now we have a real runId)
        const fileRefs = await uploadAttachmentsForRun(session.id, run.id, files, 'draft promotion')

        // Send the task via WebSocket (before navigate so cleanup runs in mounted context)
        const taskJson = { content: message }
        const success = await sendStart(
          run.id,
          session.id,
          JSON.stringify(taskJson),
          fileRefs,
          mountDirs
        )

        if (!success) {
          console.warn('Failed to send message after promoting draft')
          setPendingAction(session.id, null)
        }

        // Migrate mounted folder from draft to real session
        if (mountedFolder) {
          setMountedFolder(session.id, mountedFolder)
        }

        // Clear draft state and navigate to real session
        // Don't clear draft pendingAction here — it keeps isSending=true until navigate
        // prevents upload button flash. Draft ChatView becomes invisible after navigate.
        clearInputDraft(sessionId!)
        clearDraftSession()
        navigate(`/sessions/${session.id}`, { replace: true })
      } catch (error) {
        console.error('Failed to promote draft session:', error)
        // TODO: Show toast/notification to user when session creation fails
        // Clean up pendingAction on draft
        setPendingAction(sessionId!, null)
        // Clean up pendingAction on real session if it was created and had pending set
        if (createdSessionId !== null) {
          setPendingAction(createdSessionId, null)
          // Session was created on backend — clean up draft and navigate there
          // so user doesn't get stuck on a broken draft
          clearInputDraft(sessionId!)
          clearDraftSession()
          navigate(`/sessions/${createdSessionId}`, { replace: true })
        }
      }
    },
    [
      sessionId,
      mountedFolder,
      setPendingAction,
      clearDraftSession,
      navigate,
      initSession,
      injectOptimisticUserMessage,
      setMountedFolder,
      uploadAttachmentsForRun,
      sendStart,
      queryClient,
    ]
  )

  const handleSend = useCallback(
    async (message: string, files?: FileAttachment[]) => {
      // Draft session: promote to real session first
      if (isDraftSession(sessionId)) {
        return promoteDraftAndSend(message, files)
      }

      // Need runId and sessionId to send messages
      if (!runId || !sessionId) {
        console.warn('Cannot send message: no active run')
        return
      }

      // Set pending action for optimistic UI feedback (prevents double-send)
      setPendingAction(sessionId, { type: 'sending', timestamp: Date.now() })

      // Auto-rename session if it has default name ("New Session ...")
      // Only rename on first user message (when no messages in store)
      if (sessionTitle?.startsWith('New Session') && messages.length === 0) {
        const newName = message.slice(0, 100).trim()
        if (newName) {
          updateSession.mutate(
            { sessionId, data: { name: newName } },
            {
              onSuccess: () => {
                updateSessionName(sessionId, newName)
              },
            }
          )
        }
      }

      // Decide whether to send as input_response (existing InputRequest,
      // takeover feedback, or mid-run steer/inbox queue) or start a new task.
      // See `shouldUseInputResponse` JSDoc for the full routing matrix.
      const useInputResponseRoute = shouldUseInputResponse({
        hasInputRequest,
        controlState,
        sessionStatus,
      })

      let success: boolean

      if (useInputResponseRoute) {
        // input_response messages do not carry folder mounting context.
        injectOptimisticUserMessage(sessionId, runId, message, files)

        const fileRefs = await uploadAttachmentsForRun(sessionId, runId, files, 'input response')

        success = await sendInputResponse(runId, sessionId, message, fileRefs)
        if (success) {
          if (controlState === 'user') {
            setControlState(sessionId, 'agent')
          }
          if (pendingTakeoverFeedback) {
            setPendingTakeoverFeedback(sessionId, false)
          }
        }
      } else {
        // start messages can include mounted folder context.
        injectOptimisticUserMessage(sessionId, runId, message, files, mountedFolder ?? undefined)

        // Start a new task, optionally with uploaded files
        const fileRefs = await uploadAttachmentsForRun(sessionId, runId, files, 'start task')

        const taskJson = { content: message }
        const mountDirs = mountedFolder ? [mountedFolder.path] : undefined
        success = await sendStart(runId, sessionId, JSON.stringify(taskJson), fileRefs, mountDirs)
        if (success && pendingTakeoverFeedback) {
          setPendingTakeoverFeedback(sessionId, false)
        }
      }

      if (!success) {
        console.warn('Failed to send message, clearing pending action')
        setPendingAction(sessionId, null)
      }
    },
    [
      sessionId,
      runId,
      sessionTitle,
      messages.length,
      mountedFolder,
      hasInputRequest,
      sessionStatus,
      controlState,
      pendingTakeoverFeedback,
      setPendingAction,
      setControlState,
      setPendingTakeoverFeedback,
      uploadAttachmentsForRun,
      promoteDraftAndSend,
      injectOptimisticUserMessage,
      sendStart,
      sendInputResponse,
      updateSession,
      updateSessionName,
    ]
  )

  // Handle stop button click
  const handleStop = async () => {
    if (!runId || !sessionId) {
      console.warn('Cannot stop: no active run')
      return
    }

    // Set pending action for optimistic UI feedback
    setPendingAction(sessionId, { type: 'stopping', timestamp: Date.now() })

    // Send stop message via WebSocket
    const success = await sendStop(runId, sessionId)

    // If send failed (e.g., connection error), clear pending action immediately
    if (!success) {
      console.warn('Failed to send stop, clearing pending action')
      setPendingAction(sessionId, null)
    }
  }

  // Determine if stop is in progress
  const isStopping = pendingAction?.type === 'stopping'

  // Determine if message send is in progress
  const isSending = pendingAction?.type === 'sending'

  // Track whether MessageList wants to hide the session status indicator
  const [hideStatusIndicator, setHideStatusIndicator] = useState(false)
  const handleHideStatusIndicator = useCallback((v: boolean) => setHideStatusIndicator(v), [])

  // Sample task banner — shown when user selects a sample task to edit before sending
  const [sampleTaskBanner, setSampleTaskBanner] = useState<string | null>(null)
  // Key to force ChatInput remount when sample task is selected (so it reads the new draft)
  const [inputKey, setInputKey] = useState(0)
  // Pre-loaded file attachments for sample tasks
  const [sampleAttachments, setSampleAttachments] = useState<FileAttachment[]>([])

  const handleSampleTaskSelect = useCallback(
    async (task: SampleTask) => {
      if (sessionId == null) return

      setInputDraft(sessionId, task.prompt)
      setSampleTaskBanner(task.ctaText)

      // Fetch sample files if the task has any
      let attachments: FileAttachment[] = []
      if (task.files && task.files.length > 0) {
        try {
          const fetched = await Promise.all(
            task.files.map(async (f) => {
              const res = await fetch(f.publicPath)
              if (!res.ok) {
                throw new Error(`Failed to fetch ${f.name}: HTTP ${res.status}`)
              }
              const blob = await res.blob()
              const file = new File([blob], f.name, { type: blob.type || 'text/plain' })
              return createFileAttachment(file)
            })
          )
          attachments = fetched
        } catch {
          // TODO: show user-visible notification that sample files failed to load
          console.warn('Failed to fetch sample task files')
        }
      }

      setSampleAttachments(attachments)
      setInputKey((k) => k + 1)
    },
    [sessionId]
  )

  // On mount: check for a pending sample task (set by SampleTasksPage before navigation)
  useEffect(() => {
    const pending = consumePendingSampleTask()
    if (pending) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time mount initialization
      void handleSampleTaskSelect(pending).catch((err) => {
        console.error('Failed to load pending sample task:', err)
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Clear banner when message is sent
  const handleSendWithBannerClear = useCallback(
    async (message: string, files?: FileAttachment[]) => {
      setSampleTaskBanner(null)
      return handleSend(message, files)
    },
    [handleSend]
  )

  return (
    <div className={cn('bg-background flex h-full w-full flex-col', className)}>
      {/* Messages area - scrollable */}
      <div className="relative flex-1">
        <div
          ref={scrollRef}
          className={cn(
            'absolute inset-0 overflow-y-auto',
            // In expanded mode, add right margin so scrollbar doesn't touch browser panel
            browserViewMode === 'expanded' && 'mr-1'
          )}
        >
          <div className="mx-auto flex min-h-full w-full max-w-[960px] flex-col p-6">
            {sessionId ? (
              messages.length > 0 ? (
                <>
                  <MessageList
                    messages={messages}
                    sessionId={sessionId}
                    onItemRef={handleItemRef}
                    novncUrl={novncUrl}
                    novncPassword={novncPassword}
                    hasScreenshots={hasScreenshots}
                    sessionStatus={sessionStatus}
                    isSessionSelected={isActive}
                    browserViewMode={browserViewMode}
                    onBrowserModeChange={onBrowserModeChange}
                    onCuaActionClick={onCuaActionClick}
                    highlightedActionId={highlightedActionId}
                    onControlClick={onControlClick}
                    onHideStatusIndicator={handleHideStatusIndicator}
                    onFilePreview={onFilePreview}
                  />
                  {/* Session status indicator — hidden when redundant or while a send is pending
                      (avoids flashing the prior "completed/stopped" status during the transition
                      window between user send and the server confirming 'active'). */}
                  {!hideStatusIndicator && !isSending && (
                    <div className="mt-6">
                      <SessionStatusIndicator status={sessionStatus} />
                    </div>
                  )}
                </>
              ) : isLoadingMessages ? (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-muted-foreground text-lg">Loading messages...</p>
                </div>
              ) : isSending ? (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-muted-foreground text-lg">Starting session...</p>
                </div>
              ) : isDraftSession(sessionId) ? (
                // Draft (newly created, not yet persisted) sessions show sample task
                // cards as an onboarding affordance. Real sessions with no messages
                // (rare — e.g. failed runs) fall through to a neutral empty state
                // below; we never want sample prompts to leak into a real session
                // (see issue #582).
                <div className="flex flex-1 flex-col items-center justify-center">
                  <div className="w-full max-w-[520px]">
                    <SampleTaskCards
                      title="Type a message to get started, or try a sample task:"
                      onTaskSelect={handleSampleTaskSelect}
                    />
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 items-center justify-center">
                  <p className="text-muted-foreground text-lg">Send a message to start the task</p>
                </div>
              )
            ) : (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-muted-foreground text-lg">
                  Select a session, or click the New Session button
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Divider line */}
      <div className="bg-border h-px w-full" />

      {/* Input area - fixed at bottom */}
      <div className="flex w-full justify-center px-6 pt-4 pb-3">
        <div className="w-full max-w-[960px]">
          {sampleTaskBanner ? (
            <ChatInputBanner
              message={sampleTaskBanner}
              onDismiss={() => setSampleTaskBanner(null)}
            />
          ) : pendingTakeoverFeedback && controlState === 'agent' && sessionId != null ? (
            <ChatInputBanner
              message={TAKEOVER_FEEDBACK_BANNER_MESSAGE}
              onDismiss={() => setPendingTakeoverFeedback(sessionId, false)}
            />
          ) : null}
          <ChatInput
            key={inputKey}
            sessionId={sessionId}
            onSend={handleSendWithBannerClear}
            onStop={handleStop}
            disabled={!sessionId || !backendReachable}
            sessionStatus={sessionStatus}
            isStopping={isStopping}
            isSending={isSending}
            showAttachments={
              (messages.length === 0 ||
                (shouldUseInputResponse({ hasInputRequest, controlState, sessionStatus }) &&
                  !isPendingApproval) ||
                sessionStatus === 'completed' ||
                sessionStatus === 'stopped' ||
                sessionStatus === 'error') &&
              !isLoadingMessages &&
              !isSending &&
              !isFaraOnly &&
              !isCuaActive
            }
            showFolderMount={
              messages.length === 0 &&
              !isLoadingMessages &&
              !isSending &&
              !hasInputRequest &&
              !isFaraOnly &&
              !isCuaActive
            }
            isControlling={controlState === 'user'}
            pendingTakeoverFeedback={pendingTakeoverFeedback}
            initialAttachments={sampleAttachments}
          />
        </div>
      </div>
    </div>
  )
}
