/**
 * Folder Mount Confirmation Dialog
 *
 * Prompts the user to authorize MagenticLite to access files in a selected folder.
 * Offers Cancel / Allow (with "Always Allow" dropdown option).
 */
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { X, ChevronDown, Check } from 'lucide-react'

interface FolderMountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  folderName: string
  onAllow: () => void
  onAlwaysAllow: () => void
  onCancel: () => void
}

export function FolderMountDialog({
  open,
  onOpenChange,
  folderName,
  onAllow,
  onAlwaysAllow,
  onCancel,
}: FolderMountDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Allow MagenticLite to access files in &ldquo;{folderName}&rdquo;?
          </DialogTitle>
          <DialogDescription>
            MagenticLite can read, edit, and delete files. Be mindful of sharing sensitive
            information.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={onCancel}>
            <X className="size-4" />
            Cancel
          </Button>
          {/* Split button: Allow + dropdown for Always Allow */}
          <div className="flex gap-px">
            <Button onClick={onAllow} className="rounded-r-none" autoFocus>
              <Check className="size-4" />
              Allow
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button className="rounded-l-none pr-2.5 pl-2">
                  <ChevronDown className="h-4 w-4" />
                  <span className="sr-only">More allow options</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={onAlwaysAllow}>
                  Always allow access to this folder
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
