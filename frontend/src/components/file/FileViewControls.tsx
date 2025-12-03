/**
 * File View Controls
 *
 * Bottom bar with prev/next file navigation, wrap toggle, and download button.
 * Button style matches BrowserExpanded's PlaybackControlsRow.
 */

import { SkipBack, SkipForward, WrapText, Download } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { getFileDownloadUrl } from '@/lib/fileUtils'
import type { FileInfo } from '@/types'

// =============================================================================
// Props
// =============================================================================

export interface FileViewControlsProps {
  /** Currently displayed file */
  currentFile: FileInfo
  /** All files in the list (for tooltip filenames) */
  allFiles: FileInfo[]
  /** Index of current file in the list */
  currentIndex: number
  /** Whether line wrap is enabled */
  wrap: boolean
  /** Show wrap toggle (only for text/code files) */
  showWrapToggle: boolean
  /** Called when prev button is clicked */
  onPrev: () => void
  /** Called when next button is clicked */
  onNext: () => void
  /** Called when wrap toggle is clicked */
  onToggleWrap: () => void
}

// =============================================================================
// Component
// =============================================================================

export function FileViewControls({
  currentFile,
  allFiles,
  currentIndex,
  wrap,
  showWrapToggle,
  onPrev,
  onNext,
  onToggleWrap,
}: FileViewControlsProps) {
  const url = getFileDownloadUrl(currentFile)
  const canDownload = url && url.startsWith('/files/')
  const canPrev = currentIndex > 0
  const canNext = currentIndex < allFiles.length - 1
  const prevName = canPrev ? allFiles[currentIndex - 1].name : undefined
  const nextName = canNext ? allFiles[currentIndex + 1].name : undefined

  return (
    <div className="flex items-center justify-between px-4 pt-4 pb-3">
      {/* Left: prev/next navigation */}
      <div className="flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="icon"
              onClick={onPrev}
              disabled={!canPrev}
              aria-label="Previous file"
            >
              <SkipBack className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{prevName ? `Previous: ${prevName}` : 'Previous file'}</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="icon"
              onClick={onNext}
              disabled={!canNext}
              aria-label="Next file"
            >
              <SkipForward className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{nextName ? `Next: ${nextName}` : 'Next file'}</TooltipContent>
        </Tooltip>
      </div>

      {/* Right: wrap toggle + download */}
      <div className="flex items-center gap-2">
        {showWrapToggle && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                size="icon"
                className={cn(wrap && 'bg-accent')}
                onClick={onToggleWrap}
                aria-label={wrap ? 'Disable line wrap' : 'Enable line wrap'}
              >
                <WrapText className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{wrap ? 'Disable line wrap' : 'Enable line wrap'}</TooltipContent>
          </Tooltip>
        )}

        {canDownload && (
          <Button variant="secondary" className="h-8 gap-1.5 px-3" asChild>
            <a href={url} download={currentFile.name}>
              <Download className="size-[13px]" />
              <span className="text-sm leading-[21px]">Download</span>
            </a>
          </Button>
        )}
      </div>
    </div>
  )
}
