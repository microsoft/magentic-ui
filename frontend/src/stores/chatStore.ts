/**
 * Chat Store
 *
 * Zustand store for managing chat state per session.
 * Uses a Map to isolate state between sessions.
 *
 * State layers (see types/state.ts for details):
 * - Layer 1 (serverStatus), Layer 2 (connectionStatus), Layer 4 (pendingAction): Stored
 * - Layer 3 (sessionStatus): Computed via getSessionStatus(), not stored
 */
import { create } from 'zustand'
import { useShallow } from 'zustand/shallow'
import { useUIStore } from './uiStore'
import {
  type SessionChatState,
  type ServerRunStatus,
  type ConnectionStatus,
  type ControlState,
  type PendingAction,
  type Message,
  type ParsedMessage,
  type InputRequest,
  type SessionStatus,
  type BrowserViewMode,
  initialSessionChatState,
  computeSessionStatus,
  isOptimisticMessage,
} from '@/types'
import { parseMessage, parseMessages, type AgentMode } from '@/lib/messages'
import { isSameFile } from '@/lib/fileUtils'

// =============================================================================
// Store Types
// =============================================================================

interface ChatStore {
  // State
  sessionStates: Map<number, SessionChatState>
  /** User's explicit expand/collapse overrides per session. Cleared when detail toggles change. */
  expandedOverrides: Map<number, Map<string, boolean>>

  // Getters
  getSessionState: (sessionId: number) => SessionChatState
  getSessionStatus: (sessionId: number) => SessionStatus
  getExpandedState: (sessionId: number, itemId: string, defaultExpanded: boolean) => boolean

  // Session initialization
  initSession: (
    sessionId: number,
    runId?: string,
    initialStatus?: ServerRunStatus,
    agentMode?: AgentMode | null
  ) => void
  clearSession: (sessionId: number) => void

  // Server state updates (from WebSocket/API)
  setRunId: (sessionId: number, runId: string) => void
  setServerStatus: (sessionId: number, status: ServerRunStatus) => void
  /** Add a raw message - parsed internally before storing */
  addMessage: (sessionId: number, message: Message) => void
  /** Replace the optimistic user message with the backend-confirmed version */
  replaceOptimisticUserMessage: (sessionId: number, message: Message) => void
  /** Update file upload status on the optimistic user message */
  updateOptimisticFileStatus: (
    sessionId: number,
    status: import('@/types').FileAttachmentStatus
  ) => void
  /** Set all messages from raw array - parsed internally before storing */
  setMessages: (sessionId: number, messages: Message[], agentMode?: AgentMode | null) => void
  setInputRequest: (sessionId: number, request: InputRequest | null) => void

  // Connection state updates (from WebSocketManager)
  setConnectionStatus: (sessionId: number, status: ConnectionStatus) => void

  // Pending action updates (from UI)
  setPendingAction: (sessionId: number, action: PendingAction | null) => void

  // Browser view state updates
  setNovncUrl: (sessionId: number, url: string | null) => void
  setNovncPassword: (sessionId: number, password: string | null) => void
  setBrowserViewMode: (sessionId: number, mode: BrowserViewMode) => void
  setPlaybackState: (
    sessionId: number,
    isLive: boolean,
    index: number,
    followLatest: boolean
  ) => void
  setHighlightedActionId: (sessionId: number, actionId: string | null) => void
  setControlState: (sessionId: number, controlState: ControlState) => void
  setPendingTakeoverFeedback: (sessionId: number, pending: boolean) => void

  // File preview state
  setPreviewFile: (sessionId: number, file: import('@/types').FileInfo | null) => void
  setFileMaximized: (sessionId: number, maximized: boolean) => void

  // Folder mounting state
  setMountedFolder: (sessionId: number, folder: import('@/types').FolderInfo | null) => void

  // Auto-approve state
  /** Enable auto-approve for a specific tool or all tools in this session */
  setAutoApprove: (
    sessionId: number,
    scope: { scope: 'all' } | { scope: 'tool'; tool: string }
  ) => void

  // Expanded state overrides
  setExpandedOverride: (sessionId: number, itemId: string, expanded: boolean) => void
  clearAllExpandedOverrides: () => void
}

// =============================================================================
// Initial State (for testing)
// =============================================================================

const initialState = {
  sessionStates: new Map<number, SessionChatState>(),
  expandedOverrides: new Map<number, Map<string, boolean>>(),
}

// =============================================================================
// Store Implementation
// =============================================================================

export const useChatStore = create<ChatStore>((set, get) => ({
  // Initial state
  ...initialState,

  // ---------------------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------------------

  getSessionState: (sessionId: number): SessionChatState => {
    return get().sessionStates.get(sessionId) ?? initialSessionChatState
  },

  getSessionStatus: (sessionId: number): SessionStatus => {
    const state = get().sessionStates.get(sessionId)
    if (!state) return 'created' // Safe default for non-existent session
    return computeSessionStatus(state)
  },

  getExpandedState: (sessionId: number, itemId: string, defaultExpanded: boolean): boolean => {
    const sessionOverrides = get().expandedOverrides.get(sessionId)
    if (sessionOverrides?.has(itemId)) {
      return sessionOverrides.get(itemId)!
    }
    return defaultExpanded
  },

  // ---------------------------------------------------------------------------
  // Session Initialization
  // ---------------------------------------------------------------------------

  initSession: (
    sessionId: number,
    runId?: string,
    initialStatus?: ServerRunStatus,
    agentMode?: AgentMode | null
  ) => {
    set((state) => {
      const existing = state.sessionStates.get(sessionId)

      // If session exists with same runId, only update serverStatus / agentMode
      // when newly known. Status sync handles page refresh: chatStore resets to
      // 'created' but API has actual status; agentMode sync handles "WS-created
      // session loaded API data and now knows the persisted mode".
      if (existing && (!runId || existing.runId === runId)) {
        let next = existing
        if (initialStatus && existing.serverStatus === 'created' && initialStatus !== 'created') {
          next = { ...next, serverStatus: initialStatus }
        }
        if (agentMode != null && existing.agentMode == null) {
          next = { ...next, agentMode }
        }
        if (next === existing) return state
        const newStates = new Map(state.sessionStates)
        newStates.set(sessionId, next)
        return { sessionStates: newStates }
      }

      // Only create new Map if we're actually changing something. Distinguish
      // ``undefined`` (caller did not supply) from explicit ``null`` (caller
      // intentionally signaled "no mode known"); ``??`` would conflate them.
      const newStates = new Map(state.sessionStates)
      newStates.set(sessionId, {
        ...initialSessionChatState,
        runId: runId ?? null,
        serverStatus: initialStatus ?? initialSessionChatState.serverStatus,
        agentMode: agentMode !== undefined ? agentMode : initialSessionChatState.agentMode,
      })

      return { sessionStates: newStates }
    })
  },

  clearSession: (sessionId: number) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      newStates.delete(sessionId)
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Server State Updates
  // ---------------------------------------------------------------------------

  setRunId: (sessionId: number, runId: string) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, runId })
      return { sessionStates: newStates }
    })
  },

  setServerStatus: (sessionId: number, status: ServerRunStatus) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }

      let pendingAction = current.pendingAction
      if (pendingAction) {
        // Map pending action to expected server status
        const expectedStatus: Record<string, ServerRunStatus> = {
          starting: 'active',
          stopping: 'stopped',
        }
        // Clear on expected status OR any terminal/error state
        const terminalStatuses: ServerRunStatus[] = ['error', 'stopped', 'complete']
        if (status === expectedStatus[pendingAction.type] || terminalStatuses.includes(status)) {
          pendingAction = null
        }
      }

      newStates.set(sessionId, {
        ...current,
        serverStatus: status,
        pendingAction,
      })
      return { sessionStates: newStates }
    })
  },

  addMessage: (sessionId: number, message: Message) => {
    // Parse raw message before storing
    // Pass previous message timestamp for reasoning duration calculation
    const prevState = get().sessionStates.get(sessionId)
    const lastMsg = prevState?.messages.at(-1)
    const parsed = parseMessage(message, lastMsg?.timestamp, prevState?.agentMode ?? null)
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }

      // Auto-update previewFile when a file message arrives with matching file
      // (e.g., agent modifies a file that's currently open in FilePreview)
      let { previewFile } = current
      if (parsed.kind === 'file' && previewFile) {
        const updatedFile = parsed.files.find((f) => isSameFile(f, previewFile!))
        if (updatedFile) {
          previewFile = updatedFile
        }
      }

      newStates.set(sessionId, {
        ...current,
        messages: [...current.messages, parsed],
        previewFile,
      })
      return { sessionStates: newStates }
    })
  },

  replaceOptimisticUserMessage: (sessionId: number, message: Message) => {
    // Replace the first optimistic user message with backend version
    let parsed = parseMessage(message)
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      const idx = current.messages.findIndex(isOptimisticMessage)
      if (idx >= 0) {
        const optimisticMsg = current.messages[idx]
        if (
          parsed.kind === 'user' &&
          optimisticMsg?.kind === 'user' &&
          !parsed.mountedFolder &&
          optimisticMsg.mountedFolder
        ) {
          parsed = { ...parsed, mountedFolder: optimisticMsg.mountedFolder }
        }

        const newMessages = [...current.messages]
        newMessages[idx] = parsed
        newStates.set(sessionId, { ...current, messages: newMessages })
      } else {
        // No optimistic message found — append as new
        newStates.set(sessionId, {
          ...current,
          messages: [...current.messages, parsed],
        })
      }
      return { sessionStates: newStates }
    })
  },

  updateOptimisticFileStatus: (sessionId, status) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      const idx = current.messages.findIndex(isOptimisticMessage)
      if (idx < 0) return state
      const msg = current.messages[idx]
      if (msg.kind !== 'user' || !msg.attachedFiles) return state
      // Update all file uploadStatus values
      const updatedFiles = msg.attachedFiles.map((f) => ({ ...f, uploadStatus: status }))
      const newMessages = [...current.messages]
      newMessages[idx] = { ...msg, attachedFiles: updatedFiles }
      newStates.set(sessionId, { ...current, messages: newMessages })
      return { sessionStates: newStates }
    })
  },

  setMessages: (sessionId: number, messages: Message[], agentMode?: AgentMode | null) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      // Authoritative agentMode (from run.agent_mode) wins. Distinguish
      // ``undefined`` (caller did not supply, e.g. legacy callers / WS-only
      // paths — keep what's already in state) from explicit ``null``
      // (caller signaled "no mode known"); ``??`` would conflate them.
      const effectiveAgentMode = agentMode !== undefined ? agentMode : current.agentMode
      // Parse all raw messages before storing
      const parsed = parseMessages(messages, effectiveAgentMode)
      newStates.set(sessionId, {
        ...current,
        messages: parsed,
        agentMode: effectiveAgentMode,
      })
      return { sessionStates: newStates }
    })
  },

  setInputRequest: (sessionId: number, request: InputRequest | null) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, inputRequest: request })
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Connection State Updates
  // ---------------------------------------------------------------------------

  setConnectionStatus: (sessionId: number, status: ConnectionStatus) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, connectionStatus: status })
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Pending Action Updates
  // ---------------------------------------------------------------------------

  setPendingAction: (sessionId: number, action: PendingAction | null) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, pendingAction: action })
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Browser View State Updates
  // ---------------------------------------------------------------------------

  setNovncUrl: (sessionId: number, url: string | null) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, novncUrl: url })
      return { sessionStates: newStates }
    })
  },

  setNovncPassword: (sessionId: number, password: string | null) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, novncPassword: password })
      return { sessionStates: newStates }
    })
  },

  setBrowserViewMode: (sessionId: number, mode: BrowserViewMode) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, browserViewMode: mode })
      return { sessionStates: newStates }
    })
  },

  setPlaybackState: (sessionId: number, isLive: boolean, index: number, followLatest: boolean) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, {
        ...current,
        playbackIsLive: isLive,
        playbackIndex: index,
        followLatestScreenshot: followLatest,
      })
      return { sessionStates: newStates }
    })
  },

  setHighlightedActionId: (sessionId: number, actionId: string | null) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, highlightedActionId: actionId })
      return { sessionStates: newStates }
    })
  },

  setControlState: (sessionId: number, controlState: ControlState) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, controlState })
      return { sessionStates: newStates }
    })
  },

  setPendingTakeoverFeedback: (sessionId: number, pending: boolean) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, pendingTakeoverFeedback: pending })
      return { sessionStates: newStates }
    })
  },

  setPreviewFile: (sessionId, file) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, previewFile: file })
      return { sessionStates: newStates }
    })
  },

  setFileMaximized: (sessionId, maximized) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, fileMaximized: maximized })
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Folder Mounting
  // ---------------------------------------------------------------------------

  setMountedFolder: (sessionId, folder) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      newStates.set(sessionId, { ...current, mountedFolder: folder })
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Auto-Approve
  // ---------------------------------------------------------------------------

  setAutoApprove: (sessionId, scope) => {
    set((state) => {
      const newStates = new Map(state.sessionStates)
      const current = newStates.get(sessionId) ?? { ...initialSessionChatState }
      if (scope.scope === 'all') {
        newStates.set(sessionId, { ...current, autoApproveAll: true })
      } else {
        const tools = current.autoApproveTools.includes(scope.tool)
          ? current.autoApproveTools
          : [...current.autoApproveTools, scope.tool]
        newStates.set(sessionId, { ...current, autoApproveTools: tools })
      }
      return { sessionStates: newStates }
    })
  },

  // ---------------------------------------------------------------------------
  // Expanded State Overrides
  // ---------------------------------------------------------------------------

  setExpandedOverride: (sessionId: number, itemId: string, expanded: boolean) => {
    set((state) => {
      const newOverrides = new Map(state.expandedOverrides)
      const sessionOverrides = new Map(newOverrides.get(sessionId) ?? new Map())
      sessionOverrides.set(itemId, expanded)
      newOverrides.set(sessionId, sessionOverrides)
      return { expandedOverrides: newOverrides }
    })
  },

  clearAllExpandedOverrides: () => {
    set({ expandedOverrides: new Map() })
  },
}))

// =============================================================================
// Selector Hooks (for component usage)
// =============================================================================

/**
 * Get messages for a specific session
 * Uses useShallow to prevent unnecessary re-renders when array reference changes
 */
export function useSessionMessages(sessionId: number | undefined): ParsedMessage[] {
  return useChatStore(
    useShallow((state) =>
      sessionId !== undefined ? state.getSessionState(sessionId).messages : []
    )
  )
}

/**
 * Get session status for a specific session (Layer 4)
 */
export function useSessionStatus(sessionId: number | undefined): SessionStatus {
  return useChatStore((state) =>
    sessionId !== undefined ? state.getSessionStatus(sessionId) : 'created'
  )
}

/**
 * Get noVNC WebSocket URL for a specific session
 */
export function useNovncUrl(sessionId: number | undefined): string | null {
  return useChatStore((state) =>
    sessionId !== undefined ? state.getSessionState(sessionId).novncUrl : null
  )
}

/**
 * Get noVNC RFB password for a specific session.
 */
export function useNovncPassword(sessionId: number | undefined): string | null {
  return useChatStore((state) =>
    sessionId !== undefined ? state.getSessionState(sessionId).novncPassword : null
  )
}

/**
 * Get browser view mode for a specific session
 */
export function useBrowserViewMode(sessionId: number | undefined): BrowserViewMode {
  return useChatStore((state) =>
    sessionId !== undefined ? state.getSessionState(sessionId).browserViewMode : 'embedded'
  )
}

/**
 * Get playback state for a specific session
 * Uses useShallow to prevent infinite loops from returning new object each render
 */
export function usePlaybackState(sessionId: number | undefined): {
  isLive: boolean
  index: number
  followLatest: boolean
} {
  return useChatStore(
    useShallow((state) => {
      if (sessionId === undefined) return { isLive: true, index: 0, followLatest: true }
      const sessionState = state.getSessionState(sessionId)
      return {
        isLive: sessionState.playbackIsLive,
        index: sessionState.playbackIndex,
        followLatest: sessionState.followLatestScreenshot,
      }
    })
  )
}

/**
 * Low-level hook: Subscribe to expanded state for a specific item.
 * Returns true if expanded, false if collapsed.
 *
 * NOTE: Components should use `useCollapsibleGroup` from @/hooks instead.
 * This hook is used internally by useCollapsibleGroup.
 *
 * @see useCollapsibleGroup - High-level hook that combines this with toggle logic
 */
export function useExpandedState(
  sessionId: number,
  itemId: string,
  defaultExpanded: boolean
): boolean {
  return useChatStore((state) => {
    const sessionOverrides = state.expandedOverrides.get(sessionId)
    if (sessionOverrides?.has(itemId)) {
      return sessionOverrides.get(itemId)!
    }
    return defaultExpanded
  })
}

/**
 * Get mounted folder for a specific session
 */
export function useMountedFolder(
  sessionId: number | undefined
): import('@/types').FolderInfo | null {
  return useChatStore((state) =>
    sessionId !== undefined ? state.getSessionState(sessionId).mountedFolder : null
  )
}

/** Get the persisted agent mode for a specific session. */
export function useSessionAgentMode(sessionId: number | undefined): AgentMode | null {
  return useChatStore((state) =>
    sessionId !== undefined ? state.getSessionState(sessionId).agentMode : null
  )
}

/** True while a `delegate_cua` tool_call has no matching tool_result yet. */
export function useIsCuaActive(sessionId: number | undefined): boolean {
  return useChatStore((state) => {
    if (sessionId === undefined) return false
    const messages = state.getSessionState(sessionId).messages
    const resolvedToolCallIds = new Set<string>()
    for (const msg of messages) {
      if (msg.kind === 'tool-result' && msg.toolCallId) {
        resolvedToolCallIds.add(msg.toolCallId)
      }
    }
    for (const msg of messages) {
      if (
        msg.kind === 'orchestrator-tool' &&
        msg.tool === 'delegate_cua' &&
        msg.toolCallId &&
        !resolvedToolCallIds.has(msg.toolCallId)
      ) {
        return true
      }
    }
    return false
  })
}

// =============================================================================
// Cross-Store Subscriptions
// =============================================================================

/**
 * Subscribe to detail toggle changes and clear expanded overrides.
 * This keeps expandedOverrides logic within chatStore (owns the state).
 */
let prevShowReasoning = useUIStore.getState().showReasoningDetails
let prevShowToolCall = useUIStore.getState().showToolCallDetails
useUIStore.subscribe((state) => {
  if (
    state.showReasoningDetails !== prevShowReasoning ||
    state.showToolCallDetails !== prevShowToolCall
  ) {
    prevShowReasoning = state.showReasoningDetails
    prevShowToolCall = state.showToolCallDetails
    useChatStore.getState().clearAllExpandedOverrides()
  }
})

// =============================================================================
// Testing Utilities
// =============================================================================

/**
 * Get initial state for testing
 */
export function getInitialState(): typeof initialState {
  return initialState
}

/**
 * Reset store to initial state (for testing)
 */
export function resetStore(): void {
  useChatStore.setState(initialState)
}
