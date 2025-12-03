import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  BrowserRouter,
  Routes,
  Route,
  useNavigate,
  useParams,
  useLocation,
  Navigate,
} from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ErrorBoundary } from '@/components/common'
import { Header, type AppLayout } from '@/components/layout'
import { SessionView, Dashboard, DashboardTabs } from '@/components/session'
import { TooltipProvider } from '@/components/ui/tooltip'
import { OnboardingPage } from '@/pages/OnboardingPage'
import { SampleTasksPage } from '@/pages/SampleTasksPage'
import { getOnboardingStatus } from '@/api/onboarding'
import {
  useResponsiveLayout,
  WebSocketManagerProvider,
  useEnsureSessionData,
  type ActiveRun,
} from '@/hooks'
import { useSessionList, useSessionsWithStatus } from '@/api'
import { useUIStore, useNotificationStore } from '@/stores'
import { ACTIVE_SESSION_STATUSES, ACTIVE_RUN_STATUSES, type ServerRunStatus } from '@/types'
import { DRAFT_SESSION_ID, isDraftSession } from '@/lib/constants'
import { findInvalidSessionRedirect } from '@/lib/sessionRedirect'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
})

/**
 * Hook to create a new session and navigate to it.
 * Creates a local draft session (not persisted until first message is sent).
 * If a draft already exists, navigates to it instead of creating another.
 */
function useNewSession() {
  const navigate = useNavigate()
  const createDraftSession = useUIStore((s) => s.createDraftSession)
  const draftSession = useUIStore((s) => s.draftSession)

  return useCallback(() => {
    // If a draft already exists, just navigate to it
    if (draftSession) {
      navigate(`/sessions/${DRAFT_SESSION_ID}`)
      return
    }

    createDraftSession()
    navigate(`/sessions/${DRAFT_SESSION_ID}`)
  }, [createDraftSession, draftSession, navigate])
}

/**
 * Merges the in-memory draft session (if any) to the top of the API session list.
 * Draft is cleared externally (ChatView on promote, SessionDialogs on delete).
 */
function useSessionListWithDraft() {
  const { sessions: apiSessions, isLoading, error } = useSessionList()
  const draftSession = useUIStore((s) => s.draftSession)

  const sessions = useMemo(() => {
    if (!draftSession) return apiSessions
    return [draftSession, ...apiSessions]
  }, [apiSessions, draftSession])

  return { sessions, isLoading, error }
}

/**
 * Dashboard page - shows all sessions in a grid
 */
function DashboardPage() {
  const navigate = useNavigate()
  const handleNewSession = useNewSession()

  // Tab state from store
  const activeTab = useUIStore((s) => s.activeTab)
  const setActiveTab = useUIStore((s) => s.setActiveTab)

  // Fetch sessions from API (includes draft session at top if exists)
  const { sessions, isLoading, error } = useSessionListWithDraft()

  // Filter sessions based on active tab
  const filteredSessions = useMemo(() => {
    return sessions.filter((session) => {
      switch (activeTab) {
        case 'active':
          return ACTIVE_SESSION_STATUSES.includes(session.status)
        case 'stopped':
          return session.status === 'completed' || session.status === 'stopped'
        case 'all':
        default:
          return true
      }
    })
  }, [sessions, activeTab])

  const handleSessionClick = useCallback(
    (id: number) => {
      navigate(`/sessions/${id}`)
    },
    [navigate]
  )

  return (
    <div className="bg-background flex h-screen flex-col overflow-hidden">
      {/* Header with tabs */}
      <ErrorBoundary>
        <Header
          layout="dashboard"
          bottomSlot={<DashboardTabs activeTab={activeTab} onTabChange={setActiveTab} />}
          onNewSession={handleNewSession}
        />
      </ErrorBoundary>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-auto">
        <ErrorBoundary>
          {isLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <p className="text-muted-foreground text-lg">Loading sessions...</p>
            </div>
          ) : error ? (
            <div className="flex flex-1 items-center justify-center">
              <p className="text-destructive text-lg">
                Failed to load sessions: {error instanceof Error ? error.message : 'Unknown error'}
              </p>
            </div>
          ) : (
            <Dashboard sessions={filteredSessions} onSessionClick={handleSessionClick} />
          )}
        </ErrorBoundary>
      </main>
    </div>
  )
}

/**
 * Session page - shows session view with optional sidebar
 */
function SessionPage() {
  const navigate = useNavigate()
  const { sessionId: sessionIdParam } = useParams<{ sessionId: string }>()
  const handleNewSession = useNewSession()

  // Parse URL param to number (URL params are always strings)
  const sessionId = sessionIdParam ? parseInt(sessionIdParam, 10) : undefined
  const draftSession = useUIStore((s) => s.draftSession)

  useEnsureSessionData(sessionId)

  // Sidebar state from store (persists user preference)
  const sidebarOpen = useUIStore((s) => s.sidebarOpen)
  const toggleSidebar = useUIStore((s) => s.toggleSidebar)
  const autoShowSidebar = useUIStore((s) => s.autoShowSidebar)
  const setSelectedSessionId = useUIStore((s) => s.setSelectedSessionId)

  // Sync selected session ID to store (for notification filtering)
  useEffect(() => {
    setSelectedSessionId(sessionId)
    // Clear on unmount (user leaves session page)
    return () => setSelectedSessionId(undefined)
  }, [sessionId, setSelectedSessionId])

  // Responsive layout: auto-show/hide sidebar based on window width
  const { allowSidebar } = useResponsiveLayout()

  // Auto-show sidebar when screen becomes wide enough (if user didn't manually close it)
  useEffect(() => {
    if (allowSidebar) {
      autoShowSidebar()
    }
  }, [allowSidebar, autoShowSidebar])

  // Fetch sessions from API (with draft merged in)
  const { sessions, isLoading, error } = useSessionListWithDraft()

  // If the URL points to a session that doesn't exist — either the draft
  // sentinel after the in-memory draft was cleared (e.g., page refresh), or
  // a real session ID that isn't in the API list (e.g., deleted session,
  // hand-typed ID, or stale link) — redirect to the top of the sidebar
  // (the draft if one exists, otherwise the most recent real session), or
  // to the dashboard if the list is empty. Without this, ChatView would
  // fall through to its empty-state and leak sample prompts for a real
  // but missing session. See issue #582.
  useEffect(() => {
    const target = findInvalidSessionRedirect({
      sessionId,
      draftSession,
      sessions,
      isLoading,
      error,
    })
    if (target !== null) {
      navigate(target, { replace: true })
    }
  }, [sessionId, draftSession, sessions, isLoading, error, navigate])

  // Compute layout based on sidebar state
  const layout: AppLayout = sidebarOpen && allowSidebar ? 'sidebar-show' : 'sidebar-hide'

  const handleBackToDashboard = useCallback(() => {
    navigate('/')
  }, [navigate])

  const handleSessionSelect = useCallback(
    (id: number) => {
      navigate(`/sessions/${id}`)
    },
    [navigate]
  )

  const handleSessionDeselect = useCallback(() => {
    navigate('/sessions')
  }, [navigate])

  return (
    <div className="bg-background flex h-screen flex-col overflow-hidden">
      {/* Header */}
      <ErrorBoundary>
        <Header
          layout={layout}
          onNewSession={handleNewSession}
          newSessionDisabled={isDraftSession(sessionId)}
          onToggleSidebar={toggleSidebar}
          onBackToDashboard={handleBackToDashboard}
        />
      </ErrorBoundary>

      {/* Main content area */}
      <main className="flex flex-1 overflow-hidden">
        <ErrorBoundary>
          <SessionView
            sessions={sessions}
            selectedSessionId={sessionId}
            showSidebar={sidebarOpen && allowSidebar}
            isLoading={isLoading}
            error={error}
            onSessionSelect={handleSessionSelect}
            onSessionDeselect={handleSessionDeselect}
          />
        </ErrorBoundary>
      </main>
    </div>
  )
}

/**
 * Route guard: redirects to /onboarding if onboarding not completed.
 * Fetches status on mount and re-fetches when entering /sample-tasks
 * (so that a preceding completeOnboarding() call is picked up).
 * Exempt paths (/onboarding, /sample-tasks) bypass the redirect.
 */
function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const [status, setStatus] = useState<'loading' | 'needs-onboarding' | 'ready'>('loading')

  const isExempt = (path: string) => path === '/onboarding' || path === '/sample-tasks'

  // Fetch onboarding status when status is 'loading'
  useEffect(() => {
    if (status !== 'loading') return

    let cancelled = false
    getOnboardingStatus()
      .then((result) => {
        if (!cancelled) {
          setStatus(result.onboarding_completed ? 'ready' : 'needs-onboarding')
        }
      })
      .catch(() => {
        if (!cancelled) setStatus('ready') // let user through on error
      })
    return () => {
      cancelled = true
    }
  }, [status])

  // Re-fetch status when entering /sample-tasks (onboarding just completed).
  const prevPathRef = useRef(location.pathname)
  useEffect(() => {
    const entering =
      location.pathname === '/sample-tasks' && prevPathRef.current !== '/sample-tasks'
    prevPathRef.current = location.pathname
    if (entering && status !== 'loading') {
      setStatus('loading')
    }
  }, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  if (status === 'loading') {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted-foreground text-lg">Loading...</p>
      </div>
    )
  }

  if (status === 'needs-onboarding' && !isExempt(location.pathname)) {
    return <Navigate to="/onboarding" replace />
  }

  if (status === 'ready' && location.pathname === '/onboarding') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

/**
 * App routes
 */
function AppRoutes() {
  return (
    <OnboardingGuard>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/sample-tasks" element={<SampleTasksPage />} />
        <Route path="/sessions" element={<SessionPage />} />
        <Route path="/sessions/:sessionId" element={<SessionPage />} />
      </Routes>
    </OnboardingGuard>
  )
}

/**
 * WebSocket manager wrapper
 * Provides WebSocket connections for all active sessions
 */
function WebSocketWrapper({ children }: { children: React.ReactNode }) {
  const { data: sessions, isLoading } = useSessionsWithStatus()
  const cleanupInvalidSessions = useNotificationStore((s) => s.cleanupInvalidSessions)
  const selectedSessionId = useUIStore((s) => s.selectedSessionId)

  // Track if we've done initial sync
  const hasSyncedRef = useRef(false)

  // Clean up stale notifications on initial load
  // This handles: page refresh, sessions deleted while offline
  // IMPORTANT: Wait for data to actually load before cleanup
  useEffect(() => {
    if (isLoading || hasSyncedRef.current || !sessions) return
    hasSyncedRef.current = true

    // Get valid session IDs from API
    const validSessionIds = sessions.map((s) => s.session_id)
    // Remove notifications for sessions that no longer exist
    cleanupInvalidSessions(validSessionIds)
  }, [sessions, isLoading, cleanupInvalidSessions])

  // Extract runs that need WebSocket connections (see ACTIVE_RUN_STATUSES for details)
  const activeRuns: ActiveRun[] = useMemo(() => {
    if (!sessions) return []

    return sessions
      .filter((session) => session.latest_run) // Has a run
      .filter((session) =>
        ACTIVE_RUN_STATUSES.includes(session.latest_run?.status as ServerRunStatus)
      )
      .map((session) => ({
        runId: String(session.latest_run!.run_id),
        sessionId: session.session_id,
        sessionName: session.name,
        status: session.latest_run!.status as ServerRunStatus,
      }))
  }, [sessions])

  return (
    <WebSocketManagerProvider activeRuns={activeRuns} selectedSessionId={selectedSessionId}>
      {children}
    </WebSocketManagerProvider>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={700}>
        <BrowserRouter>
          <WebSocketWrapper>
            <AppRoutes />
          </WebSocketWrapper>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  )
}

export default App
