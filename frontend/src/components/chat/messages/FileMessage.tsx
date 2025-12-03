/**
 * File Message Component
 *
 * Displays agent-generated or edited files as bare chips in the chat view.
 * No collapsible header — just inline chips in the message flow.
 *
 * When `summary` is true, this is the end-of-run aggregated list shown
 * beneath the final answer. It renders two sections so users can see the
 * full input/output picture at a glance:
 *
 *   - "Files you uploaded"                     (from `uploadedFiles`, if any)
 *   - "Files the agent created or modified"    (from `files`, if any)
 */

import { FileChip } from '@/components/common'
import type { FileInfo } from '@/types'
import { isPreviewable, triggerFileDownload, openFileOrDownload } from '@/lib/fileUtils'

// =============================================================================
// Props
// =============================================================================

export interface FileMessageProps {
  /** Files generated or edited by the agent */
  files: FileInfo[]
  /** Called when user clicks a previewable file chip */
  onFilePreview?: (file: FileInfo) => void
  /**
   * When true, this is the end-of-run aggregated file list. Renders the
   * chips under section headers ("Files you uploaded" / "Files the agent
   * created or modified") so users get a complete overview after the
   * final answer.
   */
  summary?: boolean
  /**
   * Files the user uploaded for this run. Only meaningful when `summary`
   * is true; rendered above the agent-generated files for overview.
   */
  uploadedFiles?: FileInfo[]
}

// =============================================================================
// Internal helpers
// =============================================================================

function FileChipList({
  files,
  onFilePreview,
}: {
  files: FileInfo[]
  onFilePreview?: (file: FileInfo) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {files.map((file, i) => (
        <FileChip
          key={`${file.name}-${i}`}
          name={file.name}
          extension={file.extension}
          context="chat"
          tooltip={isPreviewable(file.name) ? 'Preview' : 'Download'}
          onClick={() => openFileOrDownload(file, onFilePreview)}
          onDownload={() => triggerFileDownload(file)}
        />
      ))}
    </div>
  )
}

function FileSection({
  label,
  files,
  onFilePreview,
}: {
  label: string
  files: FileInfo[]
  onFilePreview?: (file: FileInfo) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-muted-foreground text-sm font-medium">{label}</div>
      <FileChipList files={files} onFilePreview={onFilePreview} />
    </div>
  )
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders bare file chips inline in the message list.
 * Chips open preview for previewable files, or trigger download for others.
 *
 * For the end-of-run summary, chips are rendered under section headers
 * for uploaded and generated files.
 */
export function FileMessage({
  files,
  onFilePreview,
  summary = false,
  uploadedFiles,
}: FileMessageProps) {
  if (summary) {
    const hasUploaded = !!uploadedFiles && uploadedFiles.length > 0
    const hasGenerated = files.length > 0
    // Pull the summary up so it visually belongs to the preceding final
    // answer instead of looking like an unrelated next message. Standard
    // message gap is gap-6 (24px); -mt-3 (12px) leaves a gentle separation
    // (~12px) without breaking the message-as-its-own-bubble model.
    // Sections inside the summary use the same 12px rhythm via gap-3.
    return (
      <div className="-mt-3 flex flex-col gap-3">
        {hasUploaded && (
          <FileSection
            label="Files you uploaded"
            files={uploadedFiles!}
            onFilePreview={onFilePreview}
          />
        )}
        {hasGenerated && (
          <FileSection
            label="Files the agent created or modified"
            files={files}
            onFilePreview={onFilePreview}
          />
        )}
      </div>
    )
  }

  // Non-summary chips sit tight against the previous message
  return (
    <div className="-mt-4">
      <FileChipList files={files} onFilePreview={onFilePreview} />
    </div>
  )
}
