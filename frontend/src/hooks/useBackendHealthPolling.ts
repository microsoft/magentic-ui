/**
 * Backend Health Polling
 *
 * Probes `/api/health` with capped exponential backoff (3s→15s) while
 * the backend is marked unreachable. On recovery, refetches any errored
 * TanStack Query and the trusted-folders store so the UI fills back in.
 */
import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { pingBackend } from '@/api/health'
import { useBackendHealthStore } from '@/stores/backendHealthStore'
import { useFolderPreferencesStore } from '@/stores/folderPreferencesStore'

const INITIAL_DELAY_MS = 3_000
const MAX_DELAY_MS = 15_000

export function useBackendHealthPolling(): void {
  const reachable = useBackendHealthStore((s) => s.reachable)
  const queryClient = useQueryClient()

  // Track previous value to detect the recovery edge.
  const prevReachableRef = useRef(reachable)
  useEffect(() => {
    if (!prevReachableRef.current && reachable) {
      queryClient.refetchQueries({
        type: 'all',
        predicate: (query) => query.state.status === 'error',
      })
      // Folders live in zustand, not react-query — refetch manually.
      const folderStore = useFolderPreferencesStore.getState()
      if (folderStore.loaded) {
        folderStore.fetchTrustedFolders()
      }
    }
    prevReachableRef.current = reachable
  }, [reachable, queryClient])

  useEffect(() => {
    if (reachable) return

    let cancelled = false
    let attempt = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    const scheduleNext = () => {
      const delay = Math.min(MAX_DELAY_MS, INITIAL_DELAY_MS * Math.pow(2, attempt))
      attempt++
      timer = setTimeout(probe, delay)
    }

    const probe = async () => {
      if (cancelled) return
      try {
        await pingBackend()
      } catch {
        // Wrapper already recorded the failure; just retry.
      }
      if (cancelled) return
      scheduleNext()
    }

    scheduleNext()
    return () => {
      cancelled = true
      // `setTimeout` can return `0` in some environments, so guard
      // against `undefined` rather than truthiness.
      if (timer !== undefined) clearTimeout(timer)
    }
  }, [reachable])
}
