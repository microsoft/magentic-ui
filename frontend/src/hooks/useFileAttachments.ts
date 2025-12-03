/**
 * useFileAttachments Hook
 *
 * Manages file attachment state and handlers for ChatInput.
 * Handles: file selection, paste, drag & drop, size validation, removal.
 */

import { useState, useCallback, useRef } from 'react'
import type { FileAttachment } from '@/types'
import { isFileSizeValid, createFileAttachment } from '@/lib/fileUtils'

export interface UseFileAttachmentsReturn {
  /** Current file attachments */
  attachments: FileAttachment[]
  /** Clear all attachments (after send) */
  clearAttachments: () => void
  /** Remove a single attachment by ID */
  removeAttachment: (id: string) => void
  /** Whether a drag is currently over the drop zone */
  isDragOver: boolean
  /** Ref for the hidden file input element */
  fileInputRef: React.RefObject<HTMLInputElement | null>
  /** Handler for file input change event */
  handleFileInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  /** Handler for paste event (extracts images from clipboard) */
  handlePaste: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  /** Handler for drag over event */
  handleDragOver: (e: React.DragEvent) => void
  /** Handler for drag leave event */
  handleDragLeave: (e: React.DragEvent) => void
  /** Handler for drop event */
  handleDrop: (e: React.DragEvent) => void
}

/**
 * Hook for managing file attachments in ChatInput.
 * Validates file size (100MB limit) and provides handlers for all input methods.
 */
export function useFileAttachments(
  initialAttachments?: FileAttachment[]
): UseFileAttachmentsReturn {
  const [attachments, setAttachments] = useState<FileAttachment[]>(initialAttachments ?? [])
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  /** Add files to the attachment list (validates size) */
  const addFiles = useCallback((files: FileList | File[]) => {
    const fileArray = Array.from(files)
    const validFiles = fileArray.filter((f) => {
      if (!isFileSizeValid(f)) {
        // TODO: Show toast notification for oversized files
        console.warn(`File "${f.name}" exceeds 100MB limit, skipping`)
        return false
      }
      return true
    })

    // No deduplication by name/size — it's unreliable without content hashing.
    // Users can add the same file multiple times; this matches Gmail/Slack behavior.
    setAttachments((prev) => {
      const newAttachments = validFiles.map((f) => createFileAttachment(f))
      return [...prev, ...newAttachments]
    })
  }, [])

  const clearAttachments = useCallback(() => setAttachments([]), [])

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        addFiles(e.target.files)
        e.target.value = '' // Reset so same file can be re-selected
      }
    },
    [addFiles]
  )

  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = e.clipboardData?.items
      if (!items) return

      const imageFiles: File[] = []
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) imageFiles.push(file)
        }
      }

      if (imageFiles.length > 0) {
        e.preventDefault()
        addFiles(imageFiles)
      }
    },
    [addFiles]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragOver(false)
      if (e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files)
      }
    },
    [addFiles]
  )

  return {
    attachments,
    clearAttachments,
    removeAttachment,
    isDragOver,
    fileInputRef,
    handleFileInputChange,
    handlePaste,
    handleDragOver,
    handleDragLeave,
    handleDrop,
  }
}
