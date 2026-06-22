/**
 * Backend Health Store
 *
 * Tracks whether the backend HTTP API is reachable. Updated by the API
 * client on every request; consumed by the ConnectionStatusBanner.
 *
 * Reachability:
 * - `false` on fetch throw or 5xx (user can't make progress).
 * - `true` on 2xx/3xx/4xx (server is responding; 4xx is op-specific).
 */
import { create } from 'zustand'

interface BackendHealthState {
  /** Whether the backend HTTP API is currently reachable. */
  reachable: boolean
  /** Mark backend as reachable / unreachable based on the latest HTTP exchange. */
  setReachable: (value: boolean) => void
}

export const useBackendHealthStore = create<BackendHealthState>((set, get) => ({
  reachable: true,
  setReachable: (value) => {
    // No-op when unchanged. Returning state from the updater still
    // produces a new state object via shallow merge and notifies all
    // subscribers, so check first and skip set() entirely.
    if (get().reachable === value) return
    set({ reachable: value })
  },
}))
