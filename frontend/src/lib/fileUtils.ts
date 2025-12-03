/**
 * File Utilities
 *
 * Helper functions for file type detection, URL construction, and preview logic.
 */

import type { FileType, FileInfo, FileAttachment, FileAttachmentStatus } from '@/types'
import {
  ALL_PREVIEWABLE_EXTENSIONS,
  PREVIEWABLE_EXTENSIONS,
  MAX_FILE_UPLOAD_SIZE,
} from './constants'
import {
  File,
  FileText,
  FileCode,
  FileImage,
  FileSpreadsheet,
  FileVideo,
  FileAudio,
  FileArchive,
  type LucideIcon,
} from 'lucide-react'

// =============================================================================
// File Type Detection
// =============================================================================

/**
 * Map of file extensions to FileType categories.
 * Used for client-side type detection when backend type is missing.
 */
const EXTENSION_TO_TYPE: Record<string, FileType> = {
  // Images
  ...Object.fromEntries(PREVIEWABLE_EXTENSIONS.image.map((ext) => [ext, 'image' as const])),
  // Code
  ...Object.fromEntries(PREVIEWABLE_EXTENSIONS.code.map((ext) => [ext, 'code' as const])),
  // Markdown (treated as text for FileType, but rendered with Markdown component)
  ...Object.fromEntries(PREVIEWABLE_EXTENSIONS.markdown.map((ext) => [ext, 'text' as const])),
  // Text
  ...Object.fromEntries(PREVIEWABLE_EXTENSIONS.text.map((ext) => [ext, 'text' as const])),
  // PDF
  pdf: 'pdf',
}

/**
 * Detect FileType from a file extension.
 */
export function getFileType(extension: string): FileType {
  return EXTENSION_TO_TYPE[extension.toLowerCase()] ?? 'unknown'
}

/**
 * Get the file extension from a filename (without dot, lowercase).
 */
export function getFileExtension(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 ? filename.slice(dot + 1).toLowerCase() : ''
}

/**
 * Check if a file can be previewed in FileView.
 */
export function isPreviewable(filename: string): boolean {
  return ALL_PREVIEWABLE_EXTENSIONS.has(getFileExtension(filename))
}

/**
 * Check if a file extension is a markdown file.
 * Used by: FileView content renderer
 */
export function isMarkdownFile(extension: string): boolean {
  return (PREVIEWABLE_EXTENSIONS.markdown as readonly string[]).includes(extension.toLowerCase())
}

/**
 * Check if a file extension is a code file (for syntax highlighting).
 * Used by: FileView content renderer
 */
export function isCodeFile(extension: string): boolean {
  return (PREVIEWABLE_EXTENSIONS.code as readonly string[]).includes(extension.toLowerCase())
}

/**
 * Check if a file extension is an image.
 * Used by: FileView content renderer
 */
export function isImageFile(extension: string): boolean {
  return (PREVIEWABLE_EXTENSIONS.image as readonly string[]).includes(extension.toLowerCase())
}

// =============================================================================
// File Icon Selection (lucide)
// =============================================================================

// Extra extensions that the FileView preview doesn't yet handle but for which
// we still want a meaningful chip icon (download-only files in the chat).
const SPREADSHEET_EXTS = new Set(['csv', 'xlsx', 'xls', 'tsv', 'ods'])
const VIDEO_EXTS = new Set(['mp4', 'webm', 'mov', 'avi', 'mkv', 'm4v', 'ogv'])
const AUDIO_EXTS = new Set(['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a'])
const ARCHIVE_EXTS = new Set(['zip', 'tar', 'gz', 'tgz', 'bz2', '7z', 'rar'])

/**
 * Pick a lucide icon for a file extension. Falls back to the generic `File`
 * icon for unknown types so chips always render something.
 *
 * Order matters: spreadsheet/image/video/audio/archive are checked before
 * the broader `code`/`text` buckets so e.g. csv shows the spreadsheet icon
 * even though it lives in PREVIEWABLE_EXTENSIONS.text for rendering.
 */
export function getFileIcon(extension: string): LucideIcon {
  const ext = extension.toLowerCase()
  if (!ext) return File
  if (SPREADSHEET_EXTS.has(ext)) return FileSpreadsheet
  if (isImageFile(ext)) return FileImage
  if (VIDEO_EXTS.has(ext)) return FileVideo
  if (AUDIO_EXTS.has(ext)) return FileAudio
  if (ARCHIVE_EXTS.has(ext)) return FileArchive
  if (isCodeFile(ext)) return FileCode
  if (isMarkdownFile(ext)) return FileText
  if ((PREVIEWABLE_EXTENSIONS.text as readonly string[]).includes(ext)) return FileText
  // PDF lives in its own preview bucket, but a chip-sized text icon is the
  // closest match in lucide so use it here as a final fallback.
  if (ext === 'pdf') return FileText
  return File
}

// =============================================================================
// File URL Construction
// =============================================================================

/**
 * Build the download URL for a file from its FileInfo.
 * PR 283 provides `url` directly; legacy uses `path`/`short_path`.
 *
 * @param file - FileInfo from backend message
 * @returns Absolute URL path for downloading/viewing the file
 */
/**
 * Normalize a file path/url to a web-accessible URL.
 * Handles absolute disk paths by extracting the /files/user/... portion.
 */
function normalizeFileUrl(raw: string): string {
  if (!raw) return ''
  const filesIdx = raw.indexOf('/files/user/')
  if (filesIdx >= 0) return raw.slice(filesIdx)
  return raw.startsWith('/') ? raw : `/${raw}`
}

export function getFileDownloadUrl(file: FileInfo): string {
  // Try url first, then path/short_path — normalize all of them
  const raw = file.url || file.short_path || file.path || ''
  const base = normalizeFileUrl(raw)
  if (!base) return ''
  // Append timestamp as version param to bust cache on file updates
  if (file.timestamp != null) {
    const separator = base.includes('?') ? '&' : '?'
    return `${base}${separator}v=${file.timestamp}`
  }
  return base
}

// =============================================================================
// File Validation
// =============================================================================

/**
 * Check if a file is within the upload size limit.
 */
export function isFileSizeValid(file: File): boolean {
  return file.size <= MAX_FILE_UPLOAD_SIZE
}

/**
 * Generate a unique ID for a file attachment.
 */
let fileIdCounter = 0
function generateFileAttachmentId(): string {
  return `file-${Date.now()}-${++fileIdCounter}`
}

/**
 * Create a FileAttachment from a browser File object.
 */
export function createFileAttachment(file: File): FileAttachment {
  return {
    id: generateFileAttachmentId(),
    name: file.name,
    mimeType: file.type || 'application/octet-stream',
    size: file.size,
    status: 'pending',
    file,
  }
}

/**
 * Trigger a file download by creating a temporary anchor element.
 * No-op if the file has no valid download URL (e.g., optimistic message before upload completes).
 */
export function triggerFileDownload(file: FileInfo): void {
  // A valid file URL must start with /files/ (served by backend StaticFiles)
  const url = getFileDownloadUrl(file)
  if (!url || !url.startsWith('/files/')) {
    console.warn(`Cannot download "${file.name}": no valid URL (got "${url}")`)
    return
  }
  const link = document.createElement('a')
  link.href = url
  link.download = file.name
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * Handle file click: open preview if supported and callback provided, otherwise download.
 */
export function openFileOrDownload(file: FileInfo, onFilePreview?: (file: FileInfo) => void): void {
  if (onFilePreview && isPreviewable(file.name)) {
    onFilePreview(file)
  } else {
    triggerFileDownload(file)
  }
}

/**
 * Check if two FileInfo objects refer to the same file.
 * Matches by url (preferred) or name (fallback).
 */
export function isSameFile(a: FileInfo, b: FileInfo): boolean {
  if (a.url && b.url) return a.url === b.url
  return a.name === b.name
}

// =============================================================================
// File Info Parsing
// =============================================================================

/**
 * Parse the `metadata.files` JSON string from backend messages into FileInfo[].
 * Returns empty array if parsing fails.
 */
export function parseFileInfoFromMetadata(filesJson: string): FileInfo[] {
  try {
    const parsed = JSON.parse(filesJson)
    if (!Array.isArray(parsed)) return []

    return parsed.map((file: Record<string, unknown>) => {
      const name = String(file.name ?? '')
      const extension = String(file.extension ?? getFileExtension(name))
      const rawUrl = String(file.url ?? file.short_path ?? file.path ?? '')
      const url = rawUrl && !rawUrl.startsWith('/') ? `/${rawUrl}` : rawUrl
      // Canonical file type: prefer file_type (backend), fall back to type, then detect
      const fileType = String(file.file_type ?? file.type ?? getFileType(extension))
      return {
        name,
        url,
        path: String(file.path ?? url),
        short_path: file.short_path ? String(file.short_path) : undefined,
        extension,
        file_type: fileType,
        type: fileType,
        action: (file.action as 'created' | 'modified') ?? 'created',
        timestamp: typeof file.timestamp === 'number' ? file.timestamp : Date.now() / 1000,
        size: typeof file.size === 'number' ? file.size : undefined,
        uploadStatus: file.uploadStatus as FileAttachmentStatus | undefined,
      }
    })
  } catch {
    return []
  }
}
