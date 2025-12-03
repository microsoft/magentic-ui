/**
 * Session API
 *
 * TanStack Query hooks for session management.
 */
import { useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import { DEFAULT_USER_ID } from '@/lib/constants'
import type { Session, SessionListItem, SessionRuns, UISession } from '@/types'
import { serverStatusToSessionStatus } from '@/types'

// =============================================================================
// Query Keys
// =============================================================================

export const sessionKeys = {
  all: ['sessions'] as const,
  lists: () => [...sessionKeys.all, 'list'] as const,
  list: (userId: string) => [...sessionKeys.lists(), userId] as const,
  details: () => [...sessionKeys.all, 'detail'] as const,
  detail: (id: number) => [...sessionKeys.details(), id] as const,
  runs: (sessionId: number) => [...sessionKeys.detail(sessionId), 'runs'] as const,
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Fetch all sessions for a user (with latest run status)
 */
async function fetchSessions(userId: string): Promise<SessionListItem[]> {
  return apiClient.get<SessionListItem[]>(`/sessions/?user_id=${encodeURIComponent(userId)}`)
}

/**
 * Create a new session
 */
export async function createSession(data: Partial<Session>): Promise<Session> {
  return apiClient.post<Session>('/sessions/', data)
}

/**
 * Update a session
 */
async function updateSession(
  sessionId: number,
  data: Partial<Session>,
  userId: string
): Promise<Session> {
  return apiClient.put<Session>(`/sessions/${sessionId}?user_id=${encodeURIComponent(userId)}`, {
    ...data,
    id: sessionId,
    user_id: userId,
  })
}

/**
 * Delete a session
 */
async function deleteSession(sessionId: number, userId: string): Promise<void> {
  return apiClient.delete(`/sessions/${sessionId}?user_id=${encodeURIComponent(userId)}`)
}

/**
 * Fetch runs for a session
 */
export async function fetchSessionRuns(sessionId: number, userId: string): Promise<SessionRuns> {
  return apiClient.get<SessionRuns>(
    `/sessions/${sessionId}/runs?user_id=${encodeURIComponent(userId)}`
  )
}

// =============================================================================
// Query Hooks
// =============================================================================

/**
 * Hook to fetch the run for a session (1 session = 1 run)
 * Returns the run directly, or undefined if not loaded yet
 */
export function useSessionRun(sessionId: number | undefined, userId: string = DEFAULT_USER_ID) {
  const query = useQuery({
    queryKey: sessionKeys.runs(sessionId!),
    queryFn: () => fetchSessionRuns(sessionId!, userId),
    enabled: sessionId !== undefined,
    // 1 session = 1 run (never changes), status updates via WebSocket
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    select: (data) => data.runs[0] ?? null,
  })
  return query
}

/**
 * Hook to fetch all sessions with their latest run status
 * Returns SessionListItem[] directly from backend (no N+1 queries)
 */
export function useSessionsWithStatus(userId: string = DEFAULT_USER_ID) {
  return useQuery({
    queryKey: sessionKeys.list(userId),
    queryFn: () => fetchSessions(userId),
  })
}

/**
 * Hook to fetch all sessions formatted for UI display (Sidebar, Dashboard)
 * Status comes from query cache, and can be updated directly by WebSocket manager
 */
export function useSessionList(userId: string = DEFAULT_USER_ID): {
  sessions: UISession[]
  isLoading: boolean
  error: Error | null
} {
  const { data, isLoading, error } = useSessionsWithStatus(userId)

  const sessions: UISession[] = useMemo(() => {
    if (!data) return []
    // Sort by latest activity (run.updated_at), fallback to session.created_at.
    // ISO-8601 strings sort lexically === chronologically. The backend already
    // orders by the same key; this re-sort handles optimistic updates and WS
    // status bumps in the cache.
    return [...data]
      .filter((item) => item.latest_run !== null)
      .sort((a, b) => {
        const at = a.latest_run?.updated_at ?? a.created_at ?? ''
        const bt = b.latest_run?.updated_at ?? b.created_at ?? ''
        return bt.localeCompare(at)
      })
      .map((item) => ({
        id: item.session_id,
        title: item.name || `Session ${item.session_id}`,
        status: serverStatusToSessionStatus(item.latest_run!.status),
        runId: String(item.latest_run!.run_id),
        updatedAt: item.latest_run!.updated_at ?? item.created_at,
      }))
  }, [data])

  return { sessions, isLoading, error: error as Error | null }
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/**
 * Hook to update a session
 */
export function useUpdateSession(userId: string = DEFAULT_USER_ID) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ sessionId, data }: { sessionId: number; data: Partial<Session> }) =>
      updateSession(sessionId, data, userId),
    onSuccess: (updatedSession) => {
      // Update the specific session in cache
      queryClient.setQueryData(sessionKeys.detail(updatedSession.id), updatedSession)
      // Invalidate list to refetch
      queryClient.invalidateQueries({ queryKey: sessionKeys.lists() })
    },
  })
}

/**
 * Hook to delete a session
 */
export function useDeleteSession(userId: string = DEFAULT_USER_ID) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (sessionId: number) => deleteSession(sessionId, userId),
    onSuccess: (_, sessionId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: sessionKeys.detail(sessionId) })
      // Invalidate list to refetch
      queryClient.invalidateQueries({ queryKey: sessionKeys.lists() })
    },
  })
}
