/**
 * Confirm Dialog
 *
 * Reusable destructive confirmation dialog. Used for discard-changes
 * and reset-to-default flows in the Settings dialog.
 * Follows the same pattern as DeleteDialog.
 */
import { useRef, type ReactNode } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { X, Trash2 } from 'lucide-react'

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  title?: string
  description?: string
  confirmLabel?: string
  /** Icon shown in the confirm button. Defaults to Trash2. */
  icon?: ReactNode
}

export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title = 'Discard changes?',
  description = 'You have unsaved changes to your model config. Discard them?',
  confirmLabel = 'Discard',
  icon = <Trash2 className="size-4" />,
}: ConfirmDialogProps) {
  const confirmButtonRef = useRef<HTMLButtonElement>(null)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        onOpenAutoFocus={(e) => {
          e.preventDefault()
          confirmButtonRef.current?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            <X className="size-4" />
            Cancel
          </Button>
          <Button variant="destructive" ref={confirmButtonRef} onClick={onConfirm}>
            {icon}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
