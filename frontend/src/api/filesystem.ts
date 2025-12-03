/**
 * Filesystem API
 *
 * Client for the server-side filesystem browsing API.
 * Used by FolderBrowserDialog to let users browse and select folders.
 */
import { apiClient } from './client'

// =============================================================================
// Types
// =============================================================================

export interface DirectoryEntry {
  name: string
  type: 'file' | 'directory'
  size?: number
  modified: string
}

export interface DirectoryListing {
  path: string
  parent: string | null
  entries: DirectoryEntry[]
}

export interface FilesystemRoots {
  home: string
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get the user's home directory path.
 */
export function getRoots(): Promise<FilesystemRoots> {
  return apiClient.get<FilesystemRoots>('/filesystem/roots')
}

/**
 * List contents of a directory
 */
export function listDirectory(path: string, showHidden = false): Promise<DirectoryListing> {
  const params = new URLSearchParams({ path })
  if (showHidden) params.set('show_hidden', 'true')
  return apiClient.get<DirectoryListing>(`/filesystem/list?${params}`)
}
