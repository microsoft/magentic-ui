/**
 * Trusted Folders API
 *
 * Client for the trusted folders CRUD API.
 * Each folder is an independent DB row — no read-modify-write conflicts.
 */
import { apiClient } from './client'
import { DEFAULT_USER_ID } from '@/lib/constants'

// =============================================================================
// Types
// =============================================================================

export interface TrustedFolder {
  id: number
  name: string
  path: string
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * List all trusted folders for the current user
 */
export function listTrustedFolders(): Promise<TrustedFolder[]> {
  return apiClient.get<TrustedFolder[]>(
    `/trusted-folders/?user_id=${encodeURIComponent(DEFAULT_USER_ID)}`
  )
}

/**
 * Add a folder to the trusted list
 */
export function addTrustedFolder(name: string, path: string): Promise<TrustedFolder> {
  return apiClient.post<TrustedFolder>(
    `/trusted-folders/?user_id=${encodeURIComponent(DEFAULT_USER_ID)}`,
    {
      name,
      path,
    }
  )
}

/**
 * Remove a trusted folder by ID
 */
export function removeTrustedFolder(id: number): Promise<void> {
  return apiClient.delete(`/trusted-folders/${id}?user_id=${encodeURIComponent(DEFAULT_USER_ID)}`)
}
