/**
 * File Upload API
 *
 * Upload files to a run's working directory via REST API.
 * Uses raw fetch (not apiClient) because file upload requires multipart/form-data.
 */

import { API_BASE_URL } from '@/lib/constants'
import { getAuthHeaders } from './auth'

// =============================================================================
// Types
// =============================================================================

/** Single file info returned from upload endpoint */
export interface UploadedFileInfo {
  name: string
  size: number
  path: string
  relative_path: string
}

/** Upload response from backend */
export interface UploadResponse {
  status: boolean
  message: string
  files: UploadedFileInfo[]
}

// =============================================================================
// Upload Function
// =============================================================================

/**
 * Upload files to a run's working directory.
 *
 * @param runId - Run ID to associate files with
 * @param files - Array of File objects from browser file input
 * @returns Upload response with file paths
 * @throws Error if upload fails
 */
export async function uploadFiles(runId: string, files: File[]): Promise<UploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }

  const res = await fetch(`${API_BASE_URL}/runs/${runId}/upload`, {
    method: 'POST',
    body: formData, // browser auto-sets Content-Type with boundary
    headers: getAuthHeaders(),
  })

  if (!res.ok) {
    throw new Error(`File upload failed: ${res.status} ${res.statusText}`)
  }

  return res.json()
}
