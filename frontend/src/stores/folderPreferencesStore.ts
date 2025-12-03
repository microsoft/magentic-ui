/**
 * Folder Preferences Store
 *
 * Zustand store for trusted folders, backed by dedicated backend API.
 * Stores folders the user chose "Always Allow" — skips the confirmation
 * dialog when they select these folders again.
 */
import { create } from 'zustand'
import type { FolderInfo } from '@/types'
import {
  listTrustedFolders,
  addTrustedFolder as apiAddTrustedFolder,
  removeTrustedFolder as apiRemoveTrustedFolder,
} from '@/api/settings'

interface TrustedFolderEntry extends FolderInfo {
  /** Database ID for direct delete */
  id: number
}

interface FolderPreferencesState {
  /** Folders the user has chosen "Always Allow" */
  trustedFolders: TrustedFolderEntry[]

  /** Whether the initial fetch from backend is complete */
  loaded: boolean

  /** Fetch trusted folders from backend */
  fetchTrustedFolders: () => Promise<void>

  /** Add a folder to the trusted list (persists to backend) */
  addTrustedFolder: (folder: FolderInfo) => void

  /** Remove a folder from the trusted list by path (persists to backend) */
  removeTrustedFolder: (path: string) => void

  /** Check if a folder path is trusted */
  isTrusted: (path: string) => boolean
}

export const useFolderPreferencesStore = create<FolderPreferencesState>()((set, get) => ({
  trustedFolders: [],
  loaded: false,

  fetchTrustedFolders: async () => {
    try {
      const folders = await listTrustedFolders()
      set({ trustedFolders: folders, loaded: true })
    } catch (err) {
      console.error('Failed to fetch trusted folders:', err)
      set({ loaded: true })
    }
  },

  addTrustedFolder: (folder) => {
    const state = get()
    if (state.trustedFolders.some((f) => f.path === folder.path)) return

    // Persist to backend, then update local state with server-assigned ID
    apiAddTrustedFolder(folder.name, folder.path)
      .then((saved) => {
        set((s) => {
          if (s.trustedFolders.some((f) => f.path === folder.path)) return s
          return { trustedFolders: [...s.trustedFolders, saved] }
        })
      })
      .catch((err) => {
        console.error('Failed to add trusted folder:', err)
      })
  },

  removeTrustedFolder: (path) => {
    const state = get()
    const entry = state.trustedFolders.find((f) => f.path === path)
    if (!entry) return

    // Optimistic update
    set({ trustedFolders: state.trustedFolders.filter((f) => f.path !== path) })

    // Persist to backend
    apiRemoveTrustedFolder(entry.id).catch((err) => {
      console.error('Failed to remove trusted folder:', err)
      // Revert on failure — only if path wasn't re-added while in-flight
      set((s) => {
        if (s.trustedFolders.some((f) => f.path === entry.path)) return s
        return { trustedFolders: [...s.trustedFolders, entry] }
      })
    })
  },

  isTrusted: (path) => get().trustedFolders.some((f) => f.path === path),
}))
