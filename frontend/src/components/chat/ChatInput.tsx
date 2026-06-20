import { useState, useRef, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { FileChip } from '@/components/common'
import { FolderMountDialog } from './FolderMountDialog'
import { FolderBrowserDialog } from './FolderBrowserDialog'
import { Send, CircleStop, CirclePlay, File, FolderClosed, ChevronDown, X } from 'lucide-react'
import type { SessionStatus, FileAttachment } from '@/types'
import { getInputDraft, setInputDraft, clearInputDraft } from '@/lib/inputDrafts'
import { useFileAttachments } from '@/hooks/useFileAttachments'
import { useFolderMount } from '@/hooks/useFolderMount'

interface ChatInputProps {
  /** Session ID — used to persist input drafts per session */
  sessionId?: number
  onSend?: (message: string, files?: FileAttachment[]) => void
  onStop?: () => void
  disabled?: boolean
  sessionStatus?: SessionStatus
  isStopping?: boolean
  isSending?: boolean
  /** Show the file upload button. */
  showAttachments?: boolean
  /** Show the folder mount button (start-task only). */
  showFolderMount?: boolean
  /** Whether user is controlling (or waiting to control) the browser */
  isControlling?: boolean
  /** Whether user needs to describe their browser actions (persists after releasing control) */
  pendingTakeoverFeedback?: boolean
  /** Pre-loaded file attachments (e.g. from sample tasks) */
  initialAttachments?: FileAttachment[]
}

// Placeholder text based on session state
const PLACEHOLDER_DEFAULT = 'Type your message here.'
const PLACEHOLDER_ACTIVE = 'Send a message to steer the agent, or use Stop to end the task.'
const PLACEHOLDER_PAUSED = 'Type your message here, or click Continue to resume the task.'
const PLACEHOLDER_TAKEOVER = 'Briefly describe what you changed in the browser.'

// Shared button styles
const BUTTON_TEXT_CLASS = 'text-sm tracking-wide'
const ICON_CLASS = 'size-3.5'

/**
 * Chat input component with auto-growing textarea and toolbar.
 * File attachment logic is extracted to useFileAttachments hook.
 */
export function ChatInput({
  sessionId,
  onSend,
  onStop,
  disabled = false,
  sessionStatus,
  isStopping = false,
  isSending = false,
  showAttachments = false,
  showFolderMount = false,
  isControlling = false,
  pendingTakeoverFeedback = false,
  initialAttachments,
}: ChatInputProps) {
  const [value, setValue] = useState(() => (sessionId != null ? getInputDraft(sessionId) : ''))
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // File attachment state & handlers (extracted hook)
  const {
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
  } = useFileAttachments(initialAttachments)

  // Folder mounting state & handlers (extracted hook using server-side file browser)
  const {
    mountedFolder,
    folderDialogOpen,
    setFolderDialogOpen,
    pendingFolderName,
    folderBrowserOpen,
    setFolderBrowserOpen,
    handleSelectFolder,
    handleBrowserSelect,
    handleFolderAllow,
    handleFolderAlwaysAllow,
    handleFolderCancel,
    handleDeselectFolder,
  } = useFolderMount(sessionId)

  // =========================================================================
  // Input Draft Persistence
  // =========================================================================

  const prevSessionIdRef = useRef(sessionId)
  useEffect(() => {
    if (prevSessionIdRef.current === sessionId) return
    if (prevSessionIdRef.current != null && value) {
      setInputDraft(prevSessionIdRef.current, value)
    }
    setValue(sessionId != null ? getInputDraft(sessionId) : '')
    prevSessionIdRef.current = sessionId
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  // Ref for unmount cleanup — updated synchronously in handleValueChange
  const valueRef = useRef(value)

  const handleValueChange = useCallback(
    (newValue: string) => {
      setValue(newValue)
      valueRef.current = newValue
      if (sessionId != null) {
        setInputDraft(sessionId, newValue)
      }
    },
    [sessionId]
  )

  // Save draft on unmount
  useEffect(() => {
    return () => {
      const current = prevSessionIdRef.current
      if (current != null && valueRef.current) {
        setInputDraft(current, valueRef.current)
      }
    }
  }, [])

  // =========================================================================
  // Textarea Auto-resize
  // =========================================================================

  const recalculateHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 192)}px`
    }
  }, [])

  useEffect(() => {
    recalculateHeight()
  }, [value, recalculateHeight])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    const resizeObserver = new ResizeObserver(() => recalculateHeight())
    resizeObserver.observe(textarea)
    return () => resizeObserver.disconnect()
  }, [recalculateHeight])

  // =========================================================================
  // Session State Derived Values
  // =========================================================================

  // Suppress Stop/Continue buttons whenever the user is in (or just exited)
  // takeover — those buttons would conflict with the takeover/feedback flow.
  // Note: this is independent of the placeholder, which is driven by
  // `isControlling` alone (the post-release guidance lives in ChatInputBanner).
  const suppressTaskControls = isControlling || pendingTakeoverFeedback
  const showStopButton = sessionStatus === 'active' && !suppressTaskControls
  const showContinueButton = sessionStatus === 'paused' && !suppressTaskControls

  // Use the takeover placeholder only while the user is actively controlling
  // the browser. After release, ChatInputBanner above the input already shows
  // the same guidance, so fall through to the default placeholder to avoid
  // duplicating the message inside the textarea.
  const placeholder = isControlling
    ? PLACEHOLDER_TAKEOVER
    : showStopButton
      ? PLACEHOLDER_ACTIVE
      : showContinueButton
        ? PLACEHOLDER_PAUSED
        : PLACEHOLDER_DEFAULT

  // =========================================================================
  // Submit Handlers
  // =========================================================================

  const handleSubmit = () => {
    if ((value.trim() || attachments.length > 0) && onSend) {
      onSend(value.trim(), attachments.length > 0 ? attachments : undefined)
      setValue('')
      valueRef.current = ''
      clearAttachments()
      if (sessionId != null) clearInputDraft(sessionId)
    }
  }

  const handleContinue = () => {
    if (onSend) {
      onSend('Continue.', attachments.length > 0 ? attachments : undefined)
      setValue('')
      valueRef.current = ''
      clearAttachments()
      if (sessionId != null) clearInputDraft(sessionId)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const nativeEvent = e.nativeEvent as KeyboardEvent & { isComposing?: boolean }
    if (e.key === 'Enter' && !e.shiftKey && !nativeEvent.isComposing) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // =========================================================================
  // Render
  // =========================================================================

  return (
    <div
      className={cn(
        'border-border bg-background rounded-xl border shadow-sm',
        showAttachments &&
          isDragOver &&
          'border-primary shadow-[0_0_0_3px_var(--card-selected-ring)]'
      )}
      onDragOver={showAttachments ? handleDragOver : undefined}
      onDragLeave={showAttachments ? handleDragLeave : undefined}
      onDrop={showAttachments ? handleDrop : undefined}
    >
      {/* Textarea */}
      <div className="px-5 py-3">
        <label htmlFor="chat-input" className="sr-only">
          Message input
        </label>
        <textarea
          id="chat-input"
          ref={textareaRef}
          value={value}
          onChange={(e) => handleValueChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={showAttachments ? handlePaste : undefined}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="text-foreground placeholder:text-muted-foreground max-h-48 min-h-6 w-full resize-none bg-transparent text-base leading-6 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>

      {/* File attachments (below textarea, above toolbar) */}
      {showAttachments && attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3 pb-2">
          {attachments.map((attachment) => (
            <FileChip
              key={attachment.id}
              name={attachment.name}
              context="input"
              status={attachment.status}
              onRemove={() => removeAttachment(attachment.id)}
            />
          ))}
        </div>
      )}

      {/* Hidden file input */}
      {showAttachments && (
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileInputChange}
          aria-hidden="true"
          tabIndex={-1}
        />
      )}

      {/* Toolbar */}
      <div
        className={cn(
          'flex items-center px-3 pt-1.5 pb-3',
          showAttachments || showFolderMount ? 'justify-between' : 'justify-end'
        )}
      >
        {/* Left: Upload + Folder buttons */}
        {(showAttachments || showFolderMount) && (
          <div className="flex items-center gap-2">
            {showAttachments && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled}
                aria-label="Upload file"
              >
                <File className={ICON_CLASS} aria-hidden="true" />
                <span className={BUTTON_TEXT_CLASS}>Upload File</span>
              </Button>
            )}

            {showFolderMount &&
              (mountedFolder ? (
                // Selected state: folder name + chevron + purple ring
                <Tooltip>
                  <DropdownMenu>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="secondary"
                          className="border-primary border shadow-[0_0_0_3px_var(--card-selected-ring)]"
                          disabled={disabled}
                        >
                          <FolderClosed className={ICON_CLASS} aria-hidden="true" />
                          <span className={BUTTON_TEXT_CLASS}>{mountedFolder.name}</span>
                          <ChevronDown className={ICON_CLASS} aria-hidden="true" />
                        </Button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <DropdownMenuContent align="start">
                      <DropdownMenuItem onClick={handleSelectFolder}>
                        <FolderClosed className="size-4" />
                        Select another folder
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={handleDeselectFolder}>
                        <X className="size-4" />
                        Deselect folder
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <TooltipContent>Work in {mountedFolder.name} folder</TooltipContent>
                </Tooltip>
              ) : (
                // Unselected state: "Work in Folder" button
                <Button
                  type="button"
                  variant="secondary"
                  onClick={handleSelectFolder}
                  disabled={disabled}
                  aria-label="Work in folder"
                >
                  <FolderClosed className={ICON_CLASS} aria-hidden="true" />
                  <span className={BUTTON_TEXT_CLASS}>Work in Folder</span>
                </Button>
              ))}
          </div>
        )}

        {/* Right: Action buttons */}
        <div>
          {showStopButton ? (
            // Mid-run steer: empty input → Stop, has text → Send.
            value.trim() ? (
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={disabled || isSending}
                aria-label="Send message"
              >
                <Send className={ICON_CLASS} aria-hidden="true" />
                <span className={BUTTON_TEXT_CLASS}>{isSending ? 'Sending...' : 'Send'}</span>
              </Button>
            ) : (
              <Button
                type="button"
                variant="destructive"
                onClick={onStop}
                disabled={isStopping}
                aria-label="Stop task"
              >
                <CircleStop className={ICON_CLASS} aria-hidden="true" />
                <span className={BUTTON_TEXT_CLASS}>{isStopping ? 'Stopping...' : 'Stop'}</span>
              </Button>
            )
          ) : showContinueButton ? (
            value.trim() ? (
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={disabled || isSending}
                aria-label="Send message"
              >
                <Send className={ICON_CLASS} aria-hidden="true" />
                <span className={BUTTON_TEXT_CLASS}>{isSending ? 'Sending...' : 'Send'}</span>
              </Button>
            ) : (
              <Button
                type="button"
                onClick={handleContinue}
                disabled={disabled || isSending}
                aria-label="Continue task"
              >
                <CirclePlay className={ICON_CLASS} aria-hidden="true" />
                <span className={BUTTON_TEXT_CLASS}>
                  {isSending ? 'Continuing...' : 'Continue'}
                </span>
              </Button>
            )
          ) : (
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={disabled || (!value.trim() && attachments.length === 0) || isSending}
              aria-label="Send message"
            >
              <Send className={ICON_CLASS} aria-hidden="true" />
              <span className={BUTTON_TEXT_CLASS}>{isSending ? 'Sending...' : 'Send'}</span>
            </Button>
          )}
        </div>
      </div>

      {/* Folder mount confirmation dialog */}
      <FolderMountDialog
        open={folderDialogOpen}
        onOpenChange={setFolderDialogOpen}
        folderName={pendingFolderName}
        onAllow={handleFolderAllow}
        onAlwaysAllow={handleFolderAlwaysAllow}
        onCancel={handleFolderCancel}
      />

      {/* Folder browser dialog (browser mode only) */}
      <FolderBrowserDialog
        open={folderBrowserOpen}
        onOpenChange={setFolderBrowserOpen}
        onSelect={handleBrowserSelect}
      />
    </div>
  )
}
