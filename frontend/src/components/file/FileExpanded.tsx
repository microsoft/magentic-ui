/**
 * File Expanded Component
 *
 * Side-by-side file preview panel (right side of chat).
 *
 * Layout (top → bottom):
 *   FileViewHeader (filename dropdown + maximize/close)
 *   FileViewContent (file content renderer)
 *   FileViewControls (prev/next + wrap + download)
 */

import { useCallback, useEffect } from 'react'
import { FileViewHeader } from './FileViewHeader'
import { FileViewContent } from './FileViewContent'
import { FileViewControls } from './FileViewControls'
import { isCodeFile, isSameFile } from '@/lib/fileUtils'
import { useWrapState } from '@/hooks'
import type { FileInfo } from '@/types'

// =============================================================================
// Props
// =============================================================================

export interface FileExpandedProps {
  /** Currently selected file to preview */
  file: FileInfo
  /** All available files in this session (for dropdown + prev/next) */
  allFiles: FileInfo[]
  /** Whether in maximized mode (vs side-by-side) */
  isMaximized: boolean
  /** Called when user selects a different file */
  onFileChange: (file: FileInfo) => void
  /** Called when maximize/restore is toggled */
  onToggleMaximize: () => void
  /** Called when close button is clicked */
  onClose: () => void
}

// =============================================================================
// Component
// =============================================================================

export function FileExpanded({
  file,
  allFiles,
  isMaximized,
  onFileChange,
  onToggleMaximize,
  onClose,
}: FileExpandedProps) {
  const [wrap, setWrap] = useWrapState()

  // Current file index in the list
  const currentIndex = allFiles.findIndex((f) => isSameFile(f, file))
  const validIndex = currentIndex >= 0 ? currentIndex : 0

  // Show wrap toggle for code and plain text files (not markdown, images, PDFs)
  // Markdown renders as HTML which wraps naturally
  const ext = file.extension?.toLowerCase() || ''
  const showWrapToggle = isCodeFile(ext) || ['txt', 'csv', 'log'].includes(ext)

  // Prev/Next navigation
  const handlePrev = useCallback(() => {
    if (validIndex > 0) onFileChange(allFiles[validIndex - 1])
  }, [validIndex, allFiles, onFileChange])

  const handleNext = useCallback(() => {
    if (validIndex < allFiles.length - 1) onFileChange(allFiles[validIndex + 1])
  }, [validIndex, allFiles, onFileChange])

  // Keyboard shortcut: Escape to close
  // Skip if a Radix overlay (dropdown, dialog) is open — let it handle Escape first
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !e.defaultPrevented) {
        const hasOpenOverlay = document.querySelector('[data-radix-popper-content-wrapper]')
        if (!hasOpenOverlay) onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="bg-card border-border flex h-full flex-col overflow-hidden rounded-xl border shadow-sm">
      {/* Toolbar */}
      <FileViewHeader
        currentFile={file}
        allFiles={allFiles}
        isMaximized={isMaximized}
        onFileSelect={onFileChange}
        onToggleMaximize={onToggleMaximize}
        onClose={onClose}
      />

      {/* Content area — scrollable */}
      <div className="min-h-0 flex-1 overflow-auto">
        <FileViewContent file={file} wrap={wrap} />
      </div>

      {/* Bottom controls */}
      <FileViewControls
        currentFile={file}
        allFiles={allFiles}
        currentIndex={validIndex}
        wrap={wrap}
        showWrapToggle={showWrapToggle}
        onPrev={handlePrev}
        onNext={handleNext}
        onToggleWrap={() => setWrap((w) => !w)}
      />
    </div>
  )
}
