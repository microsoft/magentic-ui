/**
 * Folder Settings
 *
 * Displays the list of trusted ("Always Allow") folders.
 * Users can remove folders from the trusted list.
 * All changes are immediate (no Save/Discard flow needed).
 */
import { FolderClosed, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useFolderPreferencesStore, useBackendHealthStore } from '@/stores'

export function FolderSettings() {
  const trustedFolders = useFolderPreferencesStore((s) => s.trustedFolders)
  const removeTrustedFolder = useFolderPreferencesStore((s) => s.removeTrustedFolder)
  // Removing a folder hits the backend; freeze when unreachable.
  const reachable = useBackendHealthStore((s) => s.reachable)

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Header — fixed */}
      <div className="flex shrink-0 flex-col gap-1">
        <h3 className="text-sm font-bold">Always Allowed Folders</h3>
        <p className="text-muted-foreground text-xs">
          These folders won&apos;t require confirmation when you select them with the &ldquo;Work in
          Folder&rdquo; button.
        </p>
      </div>

      <div className="border-border shrink-0 border-t" />

      {/* Folder list — scrollable */}
      {trustedFolders.length === 0 ? (
        <p className="text-muted-foreground py-4 text-center text-sm">
          No folders have been allowed yet.
        </p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex flex-col gap-1">
            {trustedFolders.map((folder) => (
              <div key={folder.path} className="flex items-center gap-3 rounded-md px-1 py-2">
                <FolderClosed className="text-primary size-5 shrink-0" aria-hidden="true" />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="text-sm font-bold break-all">{folder.name}</span>
                  <span className="text-muted-foreground text-xs break-all">{folder.path}</span>
                </div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      // Show cursor-not-allowed on hover when disabled
                      // (default Button suppresses pointer events).
                      className="hover:bg-destructive/10 hover:text-destructive size-8 shrink-0 rounded-full disabled:pointer-events-auto disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-current"
                      onClick={() => removeTrustedFolder(folder.path)}
                      disabled={!reachable}
                      aria-label={`Remove ${folder.name} from allowed folders`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Remove from the list</TooltipContent>
                </Tooltip>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
