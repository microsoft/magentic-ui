/**
 * File Types
 *
 * Type definitions for file upload, download, and preview features.
 */

// =============================================================================
// File Type Classification
// =============================================================================

/**
 * File type categories for rendering decisions.
 * Determines how the file is displayed in FileView and chat previews.
 */
export type FileType = 'image' | 'code' | 'text' | 'pdf' | 'unknown'

// =============================================================================
// File Info (from backend)
// =============================================================================

/**
 * File metadata from backend WebSocket `type: "file"` messages.
 * PR 283 format: each file has url, action, timestamp.
 */
export interface FileInfo {
  /** File name (e.g., "report.md") */
  name: string
  /** URL path for download/preview (e.g., "/files/user/uid/sid/rid/report.md") */
  url: string
  /** Unix timestamp of file creation/modification */
  timestamp: number
  /** File extension without dot (e.g., "md") */
  extension: string
  /** Backend-detected file type */
  file_type: string
  /** Whether this file was created or modified */
  action: 'created' | 'modified'
  /** Relative path (legacy, from upload response) */
  path?: string
  /** Short path alias (legacy) */
  short_path?: string
  /** Detected file type category (client-side, for rendering) */
  type?: FileType | string
  /** File size in bytes (optional, from upload response) */
  size?: number
  /** Upload status for optimistic UI (only set on user-attached files) */
  uploadStatus?: FileAttachmentStatus
}

// =============================================================================
// File Attachment (input area)
// =============================================================================

/**
 * Upload status for file attachments in the input area.
 */
export type FileAttachmentStatus = 'pending' | 'uploading' | 'uploaded' | 'error'

/**
 * File attachment in the input area (before sending).
 * Represents a file selected by the user, being uploaded, or ready to send.
 */
export interface FileAttachment {
  /** Unique ID for React key (generated client-side) */
  id: string
  /** Original file name */
  name: string
  /** MIME type (e.g., "image/png", "text/plain") */
  mimeType: string
  /** File size in bytes */
  size: number
  /** Current upload status */
  status: FileAttachmentStatus
  /** Original browser File object (for upload) */
  file: File
  /** Base64 content for images (set after reading) */
  content?: string
  /** Relative path from backend after upload */
  path?: string
}

// =============================================================================
// Uploaded File Reference (frontend → backend WS payload)
// =============================================================================

/** Reference to a file already uploaded via POST /runs/{run_id}/upload. */
export interface UploadedFileRef {
  name: string
  /** Relative path under app_dir (e.g., "files/user/uid/sid/rid/data.csv") */
  path: string
  uploaded: true
}
