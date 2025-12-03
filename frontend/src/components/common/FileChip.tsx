/**
 * File Attachment Chip
 *
 * Compact chip displaying a file name with icon. Used in two contexts:
 * - PromptInput: shows delete button on hover (removes attachment)
 * - ChatView: shows download button on hover, click opens preview or downloads
 *
 * States:
 * - pending/uploaded: file icon + name
 * - uploading: loader-circle (spinning) + name
 * - error: red border + tooltip "Upload failed"
 */

import { createElement } from 'react'
import { File, LoaderCircle, X, Download } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FileAttachmentStatus } from '@/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { getFileExtension, getFileIcon } from '@/lib/fileUtils'

// =============================================================================
// Props
// =============================================================================

export interface FileChipProps {
  /** File name to display */
  name: string
  /** Chip context determines hover behavior */
  context: 'input' | 'chat'
  /** Upload status (used in both contexts for chat file chips with upload tracking) */
  status?: FileAttachmentStatus
  /**
   * File extension (without dot). When provided, the leading icon adapts to
   * the file type (image / spreadsheet / code / etc.). When omitted, the
   * extension is derived from `name` and finally falls back to a generic
   * file icon for unknown types.
   */
  extension?: string
  /** Called when remove button is clicked (input context) */
  onRemove?: () => void
  /** Called when download button is clicked (chat context) */
  onDownload?: () => void
  /** Called when chip body is clicked (chat context → preview) */
  onClick?: () => void
  /** Optional tooltip shown on hover (e.g. 'Click to preview' or 'Click to download') */
  tooltip?: string
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders a file attachment chip with context-dependent hover behavior.
 */
export function FileChip({
  name,
  context,
  status = 'uploaded',
  extension,
  onRemove,
  onDownload,
  onClick,
  tooltip,
}: FileChipProps) {
  const isError = status === 'error'
  const isClickable = context === 'chat' && status === 'uploaded' && !!onClick

  const chip = (
    <div
      className={cn(
        'group/chip flex h-8 items-center gap-1.5 overflow-hidden rounded-lg border pr-1.5',
        isError ? 'border-destructive' : 'border-border-5',
        isClickable && 'cursor-pointer'
      )}
      onClick={isClickable ? onClick : undefined}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={
        isClickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick?.()
              }
            }
          : undefined
      }
    >
      {/* Icon area — context-dependent hover behavior */}
      <ChipIconArea
        context={context}
        status={status}
        name={name}
        extension={extension}
        onRemove={onRemove}
        onDownload={onDownload}
      />

      {/* File name */}
      <span
        className={cn(
          'truncate text-sm leading-5 font-medium',
          isError ? 'text-destructive' : 'text-foreground'
        )}
      >
        {name}
      </span>
    </div>
  )

  // Error state: wrap in tooltip
  if (isError) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{chip}</TooltipTrigger>
        <TooltipContent>Upload failed</TooltipContent>
      </Tooltip>
    )
  }

  // Clickable chip with tooltip
  if (tooltip && isClickable) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{chip}</TooltipTrigger>
        <TooltipContent>{tooltip}</TooltipContent>
      </Tooltip>
    )
  }

  return chip
}

// =============================================================================
// Icon Area Sub-component
// =============================================================================

interface ChipIconAreaProps {
  context: 'input' | 'chat'
  status: FileAttachmentStatus
  name: string
  extension?: string
  onRemove?: () => void
  onDownload?: () => void
}

/**
 * Renders a lucide icon picked by file extension. The icon constant returned
 * by `getFileIcon` is one of the stable lucide exports (e.g. `FileSpreadsheet`)
 * — not a freshly created component — but lint can't prove that statically.
 * Using `createElement` (instead of `<Icon />`) communicates this explicitly
 * and avoids a `react-hooks/static-components` warning while keeping a single
 * call site for the extension → icon mapping.
 */
function FileExtensionIcon({ extension, className }: { extension: string; className?: string }) {
  return createElement(getFileIcon(extension), { className })
}

/**
 * Left icon area of the chip.
 * - Uploading: spinning loader
 * - Error: file icon (red, no interaction)
 * - Input hover: X button (remove)
 * - Chat uploaded hover: download button
 */
function ChipIconArea({
  context,
  status,
  name,
  extension,
  onRemove,
  onDownload,
}: ChipIconAreaProps) {
  const iconSize = 'size-4'
  const ext = extension ?? getFileExtension(name)

  // Uploading state — show spinner
  if (status === 'uploading') {
    return (
      <div className="flex h-full w-[26px] shrink-0 items-center justify-center">
        <LoaderCircle className={cn(iconSize, 'text-muted-foreground animate-spin')} />
      </div>
    )
  }

  // Error state — static file icon, no interaction
  if (status === 'error') {
    return (
      <div className="flex h-full w-[26px] shrink-0 items-center justify-center">
        <File className={cn(iconSize, 'text-destructive')} />
      </div>
    )
  }

  // Input context — show X on hover
  if (context === 'input') {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={cn(
              'flex h-full w-[26px] shrink-0 items-center justify-center',
              'group-hover/chip:bg-secondary'
            )}
            onClick={(e) => {
              e.stopPropagation()
              onRemove?.()
            }}
            aria-label={`Remove ${name}`}
          >
            <FileExtensionIcon
              extension={ext}
              className={cn(iconSize, 'text-muted-foreground group-hover/chip:hidden')}
            />
            <X className={cn(iconSize, 'text-muted-foreground hidden group-hover/chip:block')} />
          </button>
        </TooltipTrigger>
        <TooltipContent>Remove</TooltipContent>
      </Tooltip>
    )
  }

  // Chat context — show download on hover (only when uploaded)
  if (status !== 'uploaded') {
    return (
      <div className="flex h-full w-[26px] shrink-0 items-center justify-center">
        <FileExtensionIcon extension={ext} className={cn(iconSize, 'text-muted-foreground')} />
      </div>
    )
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            'flex h-full w-[26px] shrink-0 items-center justify-center',
            'group-hover/chip:bg-secondary'
          )}
          onClick={(e) => {
            e.stopPropagation()
            onDownload?.()
          }}
          aria-label={`Download ${name}`}
        >
          <FileExtensionIcon
            extension={ext}
            className={cn(iconSize, 'text-muted-foreground group-hover/chip:hidden')}
          />
          <Download
            className={cn(iconSize, 'text-muted-foreground hidden group-hover/chip:block')}
          />
        </button>
      </TooltipTrigger>
      <TooltipContent>Download</TooltipContent>
    </Tooltip>
  )
}
