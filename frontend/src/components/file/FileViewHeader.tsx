/**
 * File View Toolbar
 *
 * Top bar with centered filename (dropdown for file list) and mode buttons.
 * Mirrors BrowserHeader layout pattern.
 */

import { ChevronDown, Maximize, Columns2, X, FileIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useResponsiveLayout } from '@/hooks'
import { isSameFile } from '@/lib/fileUtils'
import type { FileInfo } from '@/types'

// =============================================================================
// Props
// =============================================================================

export interface FileViewHeaderProps {
  /** Currently displayed file */
  currentFile: FileInfo
  /** All available files (for dropdown) */
  allFiles: FileInfo[]
  /** Whether currently in maximized mode */
  isMaximized: boolean
  /** Called when user selects a file from dropdown */
  onFileSelect: (file: FileInfo) => void
  /** Called when maximize/restore button is clicked */
  onToggleMaximize: () => void
  /** Called when close button is clicked */
  onClose: () => void
}

// =============================================================================
// Component
// =============================================================================

export function FileViewHeader({
  currentFile,
  allFiles,
  isMaximized,
  onFileSelect,
  onToggleMaximize,
  onClose,
}: FileViewHeaderProps) {
  const hasMultipleFiles = allFiles.length > 1
  const { allowSideBySide } = useResponsiveLayout()

  return (
    <div className="relative flex items-center justify-end gap-2 p-2">
      {/* Centered filename (+ dropdown if multiple files) */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="pointer-events-auto">
          {hasMultipleFiles ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-1 text-base leading-6 font-bold"
                  aria-label="Select file"
                >
                  <FileIcon className="size-4 shrink-0" />
                  {currentFile.name}
                  <ChevronDown className="size-[18px]" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="center" className="max-h-80 overflow-y-auto">
                {allFiles.map((file, i) => (
                  <DropdownMenuItem
                    key={`${file.url || file.name}-${i}`}
                    onClick={() => onFileSelect(file)}
                    className={isSameFile(file, currentFile) ? 'bg-accent' : ''}
                  >
                    <FileIcon className="size-4 shrink-0" />
                    {file.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <span className="flex items-center gap-1 text-base leading-6 font-bold">
              <FileIcon className="size-4 shrink-0" />
              {currentFile.name}
            </span>
          )}
        </div>
      </div>

      {/* Right side: maximize/restore + close buttons */}
      {/* Hide side-by-side button on narrow screens when maximized */}
      {(!isMaximized || allowSideBySide) && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="icon-sm"
              onClick={onToggleMaximize}
              aria-label={isMaximized ? 'Side-by-side view' : 'Maximize view'}
            >
              {isMaximized ? <Columns2 className="size-3.5" /> : <Maximize className="size-3.5" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{isMaximized ? 'Side-by-side view' : 'Maximize view'}</TooltipContent>
        </Tooltip>
      )}

      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="secondary" size="icon-sm" onClick={onClose} aria-label="Close">
            <X className="size-3.5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Close</TooltipContent>
      </Tooltip>
    </div>
  )
}
