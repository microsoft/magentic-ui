/**
 * Folder Browser Dialog
 *
 * A server-side folder browser that lets users navigate directories
 * and select a folder. Works in any browser.
 * The backend provides directory listings via /api/filesystem/*.
 * Browsing is restricted to the user's home directory and below.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Folder, ChevronRight, Home, Loader2, TriangleAlert, X, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { getRoots, listDirectory } from '@/api/filesystem'
import type { DirectoryEntry } from '@/api/filesystem'

interface FolderBrowserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (name: string, path: string) => void
}

export function FolderBrowserDialog({ open, onOpenChange, onSelect }: FolderBrowserDialogProps) {
  const [currentPath, setCurrentPath] = useState<string | null>(null)
  const [entries, setEntries] = useState<DirectoryEntry[]>([])
  const [homePath, setHomePath] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requestIdRef = useRef(0)

  const navigateTo = useCallback((path: string) => {
    const id = ++requestIdRef.current
    setLoading(true)
    setError(null)
    setCurrentPath(path)
    setEntries([])
    listDirectory(path)
      .then((data) => {
        if (requestIdRef.current !== id) return // stale response
        setCurrentPath(data.path)
        setEntries(data.entries)
      })
      .catch((err) => {
        if (requestIdRef.current !== id) return
        setError(err.message || 'Failed to list directory')
      })
      .finally(() => {
        if (requestIdRef.current !== id) return
        setLoading(false)
      })
  }, [])

  // Always start from home when dialog opens
  useEffect(() => {
    if (!open) return
    if (homePath) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- re-fetch on dialog open
      navigateTo(homePath)
      return
    }
    getRoots()
      .then((data) => {
        setHomePath(data.home)
        navigateTo(data.home)
      })
      .catch((err) => {
        setError(err.message || 'Failed to load')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const handleEntryClick = useCallback(
    (entry: DirectoryEntry) => {
      if (entry.type === 'directory' && currentPath) {
        const newPath = currentPath === '/' ? `/${entry.name}` : `${currentPath}/${entry.name}`
        navigateTo(newPath)
      }
    },
    [currentPath, navigateTo]
  )

  const handleSelect = useCallback(() => {
    if (!currentPath) return
    const name = currentPath.split('/').pop() || currentPath
    onSelect(name, currentPath)
    onOpenChange(false)
  }, [currentPath, onSelect, onOpenChange])

  // Breadcrumb: show home as a single root, then sub-segments below it
  const normalizedHome = homePath && homePath !== '/' ? homePath.replace(/\/+$/, '') : homePath
  const isWithinHome =
    !!normalizedHome &&
    !!currentPath &&
    (currentPath === normalizedHome || currentPath.startsWith(`${normalizedHome}/`))
  const subPath = isWithinHome && normalizedHome ? currentPath.slice(normalizedHome.length) : null
  const breadcrumbs = subPath
    ? subPath
        .split('/')
        .filter(Boolean)
        .map((segment, i, arr) => ({
          name: segment,
          path: normalizedHome + '/' + arr.slice(0, i + 1).join('/'),
        }))
    : []
  const isAtHome = currentPath === homePath
  const directories = entries.filter((e) => e.type === 'directory')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(520px,80vh)] max-w-2xl flex-col">
        <DialogHeader>
          <DialogTitle>Select a Folder</DialogTitle>
          <DialogDescription>Choose a folder for the agent to work in.</DialogDescription>
        </DialogHeader>

        {/* Breadcrumb: Home as root, then sub-folders */}
        <div className="text-muted-foreground flex scrollbar-none items-center gap-0.5 overflow-x-auto pb-1 text-sm">
          {homePath && (
            <button
              onClick={() => navigateTo(homePath)}
              className={cn(
                'flex shrink-0 items-center gap-1.5 transition-colors',
                isAtHome && breadcrumbs.length === 0
                  ? 'text-foreground font-medium'
                  : 'hover:text-foreground'
              )}
            >
              <Home className="size-3.5" />
              {homePath}
            </button>
          )}
          {breadcrumbs.map((crumb, i) => (
            <span key={crumb.path} className="flex shrink-0 items-center gap-0.5">
              <ChevronRight className="size-3 shrink-0" />
              <button
                onClick={() => navigateTo(crumb.path)}
                className={cn(
                  'shrink-0 transition-colors',
                  i === breadcrumbs.length - 1
                    ? 'text-foreground font-medium'
                    : 'hover:text-foreground'
                )}
              >
                {crumb.name}
              </button>
            </span>
          ))}
        </div>

        {/* Error alert */}
        {error && (
          <Alert variant="destructive" className="shrink-0 [&>svg+div]:-translate-y-px">
            <TriangleAlert className="size-4" />
            <AlertDescription className="text-sm">{error}</AlertDescription>
          </Alert>
        )}

        {/* Directory listing */}
        <div className="border-border min-h-0 flex-1 overflow-y-auto rounded-lg border">
          {loading ? (
            <div className="text-muted-foreground flex h-full items-center justify-center gap-2">
              <Loader2 className="size-4 animate-spin" />
              <span className="text-sm">Loading...</span>
            </div>
          ) : directories.length === 0 ? (
            <div className="text-muted-foreground flex h-full items-center justify-center">
              <span className="text-sm">No subfolders</span>
            </div>
          ) : (
            <ul role="listbox" className="p-1">
              {directories.map((entry) => (
                <li
                  key={entry.name}
                  role="option"
                  aria-selected={false}
                  tabIndex={0}
                  onClick={() => handleEntryClick(entry)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleEntryClick(entry)
                  }}
                  className="hover:bg-accent flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm"
                >
                  <Folder className="text-primary size-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate">{entry.name}</span>
                  <ChevronRight className="text-muted-foreground size-3.5 shrink-0" />
                </li>
              ))}
            </ul>
          )}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            <X className="size-4" />
            Cancel
          </Button>
          <Button onClick={handleSelect} disabled={!currentPath}>
            <Check className="size-4" />
            Select This Folder
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
