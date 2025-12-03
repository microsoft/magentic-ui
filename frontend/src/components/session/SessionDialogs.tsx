/**
 * Session Dialogs
 *
 * Provides Rename and Delete confirmation dialogs for sessions.
 * Designed to be used at a parent level (Dashboard/SessionView) to manage state.
 */

/* eslint-disable react-refresh/only-export-components */
// useSessionDialogs is tightly coupled with RenameDialog/DeleteDialog - co-location is intentional

import React, { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Check, Trash2, X } from 'lucide-react'
import { useUpdateSession, useDeleteSession } from '@/api/sessions'
import { useNotificationStore, useUIStore } from '@/stores'
import { isDraftSession } from '@/lib/constants'
import { clearInputDraft } from '@/lib/inputDrafts'

// =============================================================================
// Rename Dialog Content (inner component that resets when key changes)
// =============================================================================

interface RenameDialogContentProps {
  sessionId: number
  currentName: string
  onClose: () => void
}

function RenameDialogContent({ sessionId, currentName, onClose }: RenameDialogContentProps) {
  const [name, setName] = useState(currentName)
  const updateSession = useUpdateSession()
  const updateSessionName = useNotificationStore((s) => s.updateSessionName)

  const handleRename = () => {
    if (!name.trim()) return

    updateSession.mutate(
      { sessionId, data: { name: name.trim() } },
      {
        onSuccess: () => {
          // Update session name in any existing notifications
          updateSessionName(sessionId, name.trim())
          onClose()
        },
      }
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleRename()
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Rename Session</DialogTitle>
        <DialogDescription>Enter a new name for this session.</DialogDescription>
      </DialogHeader>
      <Input
        value={name}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Session name"
        autoFocus
      />
      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          <X className="size-4" />
          Cancel
        </Button>
        <Button
          onClick={handleRename}
          disabled={!name.trim() || name.trim() === currentName || updateSession.isPending}
        >
          <Check className="size-4" />
          {updateSession.isPending ? 'Saving...' : 'Save'}
        </Button>
      </DialogFooter>
    </>
  )
}

// =============================================================================
// Rename Dialog
// =============================================================================

interface RenameDialogProps {
  open: boolean
  sessionId: number | null
  currentName: string
  onOpenChange: (open: boolean) => void
}

export function RenameDialog({ open, sessionId, currentName, onOpenChange }: RenameDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {/* Use key to reset internal state when sessionId changes */}
        {sessionId !== null && (
          <RenameDialogContent
            key={sessionId}
            sessionId={sessionId}
            currentName={currentName}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

// =============================================================================
// Delete Dialog
// =============================================================================

interface DeleteDialogProps {
  open: boolean
  sessionId: number | null
  sessionName: string
  onOpenChange: (open: boolean) => void
  /** Called after successful deletion (e.g., to navigate away) */
  onDeleted?: (sessionId: number) => void
  /** Optional custom delete handler (skips API call). Return a promise or void. */
  customDelete?: () => void | Promise<void>
}

export function DeleteDialog({
  open,
  sessionId,
  sessionName,
  onOpenChange,
  onDeleted,
  customDelete,
}: DeleteDialogProps) {
  const deleteSession = useDeleteSession()
  const removeSessionNotifications = useNotificationStore((s) => s.removeSessionNotifications)

  const handleDelete = async () => {
    if (!sessionId) return

    // Draft sessions: use custom handler (local-only, no API call)
    if (customDelete) {
      try {
        await customDelete()
        onOpenChange(false)
        onDeleted?.(sessionId)
      } catch (error) {
        console.error('Custom delete handler failed:', error)
      }
      return
    }

    deleteSession.mutate(sessionId, {
      onSuccess: () => {
        // Remove any notifications for this session
        removeSessionNotifications(sessionId)
        onOpenChange(false)
        onDeleted?.(sessionId)
      },
    })
  }

  const deleteButtonRef = React.useRef<HTMLButtonElement>(null)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        onOpenAutoFocus={(e) => {
          e.preventDefault()
          deleteButtonRef.current?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>Delete Session</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &quot;{sessionName}&quot;? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            <X className="size-4" />
            Cancel
          </Button>
          <Button
            ref={deleteButtonRef}
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteSession.isPending}
          >
            <Trash2 className="size-4" />
            {deleteSession.isPending ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// =============================================================================
// Hook for managing dialog state
// =============================================================================

interface DialogState {
  renameOpen: boolean
  deleteOpen: boolean
  sessionId: number | null
  sessionName: string
}

const initialDialogState: DialogState = {
  renameOpen: false,
  deleteOpen: false,
  sessionId: null,
  sessionName: '',
}

/**
 * Hook to manage rename/delete dialog state
 *
 * Usage:
 * ```tsx
 * const dialogs = useSessionDialogs()
 *
 * // In SessionCard
 * <SessionCard
 *   onRename={dialogs.openRename}
 *   onDelete={dialogs.openDelete}
 * />
 *
 * // Render dialogs
 * <RenameDialog {...dialogs.renameProps} />
 * <DeleteDialog {...dialogs.deleteProps} />
 * ```
 */
export function useSessionDialogs(onDeleted?: (sessionId: number) => void) {
  const clearDraftSession = useUIStore((s) => s.clearDraftSession)
  const [state, setState] = useState<DialogState>(initialDialogState)

  const openRename = (sessionId: number, currentName: string) => {
    setState({
      renameOpen: true,
      deleteOpen: false,
      sessionId,
      sessionName: currentName,
    })
  }

  const openDelete = (sessionId: number, name: string) => {
    setState({
      renameOpen: false,
      deleteOpen: true,
      sessionId,
      sessionName: name,
    })
  }

  const setRenameOpen = (open: boolean) => {
    setState((prev) => ({ ...prev, renameOpen: open }))
  }

  const setDeleteOpen = (open: boolean) => {
    setState((prev) => ({ ...prev, deleteOpen: open }))
  }

  return {
    openRename,
    openDelete,
    renameProps: {
      open: state.renameOpen,
      sessionId: state.sessionId,
      currentName: state.sessionName,
      onOpenChange: setRenameOpen,
    },
    deleteProps: {
      open: state.deleteOpen,
      sessionId: state.sessionId,
      sessionName: state.sessionName,
      onOpenChange: setDeleteOpen,
      onDeleted,
      customDelete:
        state.sessionId !== null && isDraftSession(state.sessionId)
          ? () => {
              clearInputDraft(state.sessionId!)
              clearDraftSession()
            }
          : undefined,
    },
  }
}
