/**
 * UI Store
 *
 * Zustand store for UI state that persists across sessions.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { DashboardTab } from '@/components/session/DashboardTabs'
import type { UISession } from '@/types'
import { DRAFT_SESSION_ID } from '@/lib/constants'
import { useChatStore } from './chatStore'

interface UIState {
  // Session view state
  sidebarOpen: boolean
  /** True if user manually closed sidebar (vs auto-hidden due to narrow screen) */
  userClosedSidebar: boolean
  /** Call when user manually toggles sidebar */
  toggleSidebar: () => void
  /** Call when auto-showing due to wide screen (only if user didn't manually close) */
  autoShowSidebar: () => void

  // Dashboard tabs state
  activeTab: DashboardTab
  setActiveTab: (tab: DashboardTab) => void

  // Appearance
  /** Dark mode preference. Applied to document.documentElement on change. */
  darkMode: boolean
  setDarkMode: (enabled: boolean) => void

  // Message detail toggles
  /** Expand reasoning sections (e.g. "Thought for 3s") by default */
  showReasoningDetails: boolean
  setShowReasoningDetails: (enabled: boolean) => void
  /** Expand tool call sections (code execution, tool results, browser actions) by default */
  showToolCallDetails: boolean
  setShowToolCallDetails: (enabled: boolean) => void
  /** Show detailed reasoning and actions inside "using web browser" messages */
  showBrowserActionDetails: boolean
  setShowBrowserActionDetails: (enabled: boolean) => void

  /** Default line wrap for code/output blocks */
  wrapMode: boolean
  setWrapMode: (enabled: boolean) => void

  // Currently selected session (for notification filtering)
  // Not persisted - derived from URL, set by SessionPage
  selectedSessionId: number | undefined
  setSelectedSessionId: (id: number | undefined) => void

  // Draft session (not yet persisted to backend)
  // Stored in memory only — disappears on page refresh
  draftSession: UISession | null
  /** Create a new draft session. Returns the draft UISession. */
  createDraftSession: () => UISession
  /** Clear the draft session. */
  clearDraftSession: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      // Session view
      sidebarOpen: true,
      userClosedSidebar: false,
      toggleSidebar: () =>
        set((state) => ({
          sidebarOpen: !state.sidebarOpen,
          // Track if user is closing it
          userClosedSidebar: state.sidebarOpen ? true : false,
        })),
      autoShowSidebar: () =>
        set((state) => {
          // Only auto-show if user didn't manually close it
          if (state.userClosedSidebar) return state
          return { sidebarOpen: true }
        }),

      // Dashboard tabs (default to 'all')
      activeTab: 'all',
      setActiveTab: (tab) => set({ activeTab: tab }),

      // Appearance (default matches system; overwritten by persist rehydration)
      darkMode:
        typeof window !== 'undefined'
          ? window.matchMedia('(prefers-color-scheme: dark)').matches
          : true,
      setDarkMode: (enabled) => {
        document.documentElement.classList.toggle('dark', enabled)
        set({ darkMode: enabled })
      },

      // Message detail toggles
      showReasoningDetails: false,
      setShowReasoningDetails: (enabled) => set({ showReasoningDetails: enabled }),
      showToolCallDetails: false,
      setShowToolCallDetails: (enabled) => set({ showToolCallDetails: enabled }),
      showBrowserActionDetails: false,
      setShowBrowserActionDetails: (enabled) => set({ showBrowserActionDetails: enabled }),

      wrapMode: false,
      setWrapMode: (enabled) => set({ wrapMode: enabled }),

      // Selected session (not persisted, just runtime state)
      selectedSessionId: undefined,
      setSelectedSessionId: (id) => set({ selectedSessionId: id }),

      // Draft session (not persisted, memory only)
      draftSession: null,
      createDraftSession: () => {
        const existing = get().draftSession
        if (existing) return existing

        // Clear stale chatStore state from previous draft (same sessionId=-1 is reused).
        // Note: this creates a circular import (uiStore ↔ chatStore). This is safe because
        // both Zustand stores are fully initialized before any .getState() call executes
        // (ES module live bindings + Zustand’s synchronous create()).
        useChatStore.getState().clearSession(DRAFT_SESSION_ID)

        const draft: UISession = {
          id: DRAFT_SESSION_ID,
          title: 'New Session',
          status: 'created',
        }
        set({ draftSession: draft })
        return draft
      },
      clearDraftSession: () => set({ draftSession: null }),
    }),
    {
      name: 'ui-storage',
      // Only persist sidebar, tab state, appearance, and message detail toggles
      partialize: (
        state
      ): Pick<
        UIState,
        | 'sidebarOpen'
        | 'userClosedSidebar'
        | 'activeTab'
        | 'darkMode'
        | 'showReasoningDetails'
        | 'showToolCallDetails'
        | 'showBrowserActionDetails'
        | 'wrapMode'
      > => ({
        sidebarOpen: state.sidebarOpen,
        userClosedSidebar: state.userClosedSidebar,
        activeTab: state.activeTab,
        darkMode: state.darkMode,
        showReasoningDetails: state.showReasoningDetails,
        showToolCallDetails: state.showToolCallDetails,
        showBrowserActionDetails: state.showBrowserActionDetails,
        wrapMode: state.wrapMode,
      }),
      // Sync dark mode class after rehydration from localStorage
      onRehydrateStorage: () => (state) => {
        if (state) {
          document.documentElement.classList.toggle('dark', state.darkMode)
        }
      },
    }
  )
)
