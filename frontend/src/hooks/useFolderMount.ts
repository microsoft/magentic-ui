/**
 * useFolderMount Hook
 *
 * Manages folder mounting state and handlers for ChatInput.
 * Uses the server-side filesystem browser dialog to let users
 * browse and select folders (full path) from any browser.
 */

import { useState, useCallback } from 'react'
import { useChatStore, useMountedFolder, useFolderPreferencesStore } from '@/stores'
import type { FolderInfo } from '@/types'

export interface UseFolderMountReturn {
  /** Currently mounted folder for this session (null if none) */
  mountedFolder: FolderInfo | null
  /** Whether the confirmation dialog is open */
  folderDialogOpen: boolean
  /** Set dialog open state */
  setFolderDialogOpen: (open: boolean) => void
  /** Name of the folder pending confirmation */
  pendingFolderName: string
  /** Whether the folder browser dialog is open (browser mode) */
  folderBrowserOpen: boolean
  /** Set folder browser dialog open state */
  setFolderBrowserOpen: (open: boolean) => void
  /** Trigger folder selection (button click) */
  handleSelectFolder: () => Promise<void>
  /** Handler for selecting a folder from the browser dialog */
  handleBrowserSelect: (name: string, path: string) => void
  /** Handler for "Allow" button in dialog */
  handleFolderAllow: () => void
  /** Handler for "Always Allow" button in dialog */
  handleFolderAlwaysAllow: () => void
  /** Handler for "Cancel" button in dialog */
  handleFolderCancel: () => void
  /** Handler for "Deselect folder" in dropdown */
  handleDeselectFolder: () => void
}

export function useFolderMount(sessionId: number | undefined): UseFolderMountReturn {
  const mountedFolder = useMountedFolder(sessionId)
  const setMountedFolder = useChatStore((s) => s.setMountedFolder)
  const isTrusted = useFolderPreferencesStore((s) => s.isTrusted)
  const addTrustedFolder = useFolderPreferencesStore((s) => s.addTrustedFolder)
  const [folderDialogOpen, setFolderDialogOpen] = useState(false)
  const [folderBrowserOpen, setFolderBrowserOpen] = useState(false)
  const [pendingFolderName, setPendingFolderName] = useState('')
  const [pendingFolderPath, setPendingFolderPath] = useState('')

  /** Shared logic for mounting a folder (used by all selection methods) */
  const mountFolder = useCallback(
    (name: string, path: string) => {
      if (isTrusted(path)) {
        if (sessionId != null) {
          setMountedFolder(sessionId, { name, path })
        }
      } else {
        setPendingFolderName(name)
        setPendingFolderPath(path)
        setFolderDialogOpen(true)
      }
    },
    [isTrusted, sessionId, setMountedFolder]
  )

  const handleSelectFolder = useCallback(async () => {
    // Refresh trusted folders in the background before opening browser
    useFolderPreferencesStore.getState().fetchTrustedFolders()
    setFolderBrowserOpen(true)
  }, [])

  const handleBrowserSelect = useCallback(
    (name: string, path: string) => {
      mountFolder(name, path)
    },
    [mountFolder]
  )

  const handleFolderAllow = useCallback(() => {
    if (sessionId != null) {
      setMountedFolder(sessionId, { name: pendingFolderName, path: pendingFolderPath })
    }
    setFolderDialogOpen(false)
  }, [sessionId, setMountedFolder, pendingFolderName, pendingFolderPath])

  const handleFolderAlwaysAllow = useCallback(() => {
    addTrustedFolder({ name: pendingFolderName, path: pendingFolderPath })
    if (sessionId != null) {
      setMountedFolder(sessionId, { name: pendingFolderName, path: pendingFolderPath })
    }
    setFolderDialogOpen(false)
  }, [addTrustedFolder, sessionId, setMountedFolder, pendingFolderName, pendingFolderPath])

  const handleFolderCancel = useCallback(() => {
    setFolderDialogOpen(false)
  }, [])

  const handleDeselectFolder = useCallback(() => {
    if (sessionId != null) {
      setMountedFolder(sessionId, null)
    }
  }, [sessionId, setMountedFolder])

  return {
    mountedFolder,
    folderDialogOpen,
    setFolderDialogOpen,
    pendingFolderName,
    folderBrowserOpen,
    setFolderBrowserOpen,
    handleSelectFolder,
    handleBrowserSelect,
    handleFolderAllow,
    handleFolderAlwaysAllow,
    handleFolderCancel,
    handleDeselectFolder,
  }
}
