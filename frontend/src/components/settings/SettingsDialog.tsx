/**
 * Settings dialog with General and Models tabs.
 *
 * General tab: Dark Mode + Verbose Mode toggles (immediate, no save needed).
 * Models tab: Model endpoint cards with verify & save. Blocks close/tab-switch
 * when there are unsaved changes (dirty check).
 *
 * Uses a key-based remount pattern so that local state is freshly
 * initialized each time the dialog opens.
 */
import { useState, useCallback, useEffect, useImperativeHandle, useRef } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { ConnectionStatusBanner } from '@/components/common'
import { useFolderPreferencesStore } from '@/stores'
import { ConfirmDialog } from './ConfirmDialog'
import { FolderSettings } from './FolderSettings'
import { GeneralSettings } from './GeneralSettings'
import { ModelSettings } from './ModelSettings'

type SettingsTab = 'general' | 'models' | 'folders'

// =============================================================================
// Inner content component — remounted via key each time dialog opens
// =============================================================================

interface SettingsContentHandle {
  requestClose: () => void
}

function SettingsDialogContent({
  onClose,
  ref,
}: {
  onClose: () => void
  ref?: React.Ref<SettingsContentHandle>
}) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const [modelsDirty, setModelsDirty] = useState(false)

  // Refresh trusted folders from backend when dialog opens (non-blocking)
  useEffect(() => {
    useFolderPreferencesStore.getState().fetchTrustedFolders()
  }, [])

  const [pendingAction, setPendingAction] = useState<'close' | SettingsTab | null>(null)

  const handleTabChange = useCallback(
    (tab: SettingsTab) => {
      if (activeTab === 'models' && tab !== 'models' && modelsDirty) {
        setPendingAction(tab)
      } else {
        setActiveTab(tab)
      }
    },
    [activeTab, modelsDirty]
  )

  const handleCloseAttempt = useCallback(() => {
    if (activeTab === 'models' && modelsDirty) {
      setPendingAction('close')
    } else {
      onClose()
    }
  }, [activeTab, modelsDirty, onClose])

  const handleDiscardConfirmed = useCallback(() => {
    if (pendingAction === 'close') {
      onClose()
    } else if (pendingAction) {
      setActiveTab(pendingAction)
    }
    setPendingAction(null)
  }, [pendingAction, onClose])

  useImperativeHandle(ref, () => ({ requestClose: handleCloseAttempt }), [handleCloseAttempt])

  return (
    <>
      <DialogHeader className="shrink-0 p-4 text-center!">
        <DialogTitle className="text-lg font-semibold">Settings</DialogTitle>
      </DialogHeader>

      {/* Mirror the global banner — the dialog overlay dims the page banner. */}
      <ConnectionStatusBanner />

      <div className="flex min-h-0 flex-1">
        {/* Left nav */}
        <nav className="flex w-40 shrink-0 flex-col gap-2 py-4 pl-4" role="tablist">
          <button
            type="button"
            role="tab"
            id="settings-tab-general"
            aria-selected={activeTab === 'general'}
            aria-controls="settings-panel-general"
            className={cn(
              'rounded-md px-3 py-2 text-left text-sm font-medium',
              activeTab === 'general' ? 'bg-accent text-foreground' : 'text-muted-foreground'
            )}
            onClick={() => handleTabChange('general')}
          >
            General
          </button>
          <button
            type="button"
            role="tab"
            id="settings-tab-models"
            aria-selected={activeTab === 'models'}
            aria-controls="settings-panel-models"
            className={cn(
              'rounded-md px-3 py-2 text-left text-sm font-medium',
              activeTab === 'models' ? 'bg-accent text-foreground' : 'text-muted-foreground'
            )}
            onClick={() => handleTabChange('models')}
          >
            Models
          </button>
          <button
            type="button"
            role="tab"
            id="settings-tab-folders"
            aria-selected={activeTab === 'folders'}
            aria-controls="settings-panel-folders"
            className={cn(
              'rounded-md px-3 py-2 text-left text-sm font-medium',
              activeTab === 'folders' ? 'bg-accent text-foreground' : 'text-muted-foreground'
            )}
            onClick={() => handleTabChange('folders')}
          >
            Folders
          </button>
        </nav>

        {/* Right content */}
        <div className="flex min-h-0 flex-1 flex-col">
          <div
            role="tabpanel"
            id={`settings-panel-${activeTab}`}
            aria-labelledby={`settings-tab-${activeTab}`}
            className="min-h-0 flex-1 overflow-y-auto px-6 pt-4 pb-2"
          >
            {activeTab === 'general' ? (
              <GeneralSettings />
            ) : activeTab === 'models' ? (
              <ModelSettings onDirtyChange={setModelsDirty} />
            ) : (
              <FolderSettings />
            )}
          </div>
        </div>
      </div>

      {/* Discard changes confirmation */}
      <ConfirmDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null)
        }}
        onConfirm={handleDiscardConfirmed}
        title="Discard unsaved changes?"
        description="Your model endpoint changes have not been verified. They will be lost if you leave."
        confirmLabel="Discard Changes"
      />
    </>
  )
}

// =============================================================================
// Outer dialog shell — uses key to remount content each time it opens
// =============================================================================

/** Controlled settings dialog. Render once at a stable level (e.g. App or Header root). */
export function SettingsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  // Increment key each time dialog opens so inner content remounts with fresh state
  const [openCount, setOpenCount] = useState(0)
  const contentRef = useRef<SettingsContentHandle>(null)

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (nextOpen) {
        setOpenCount((c) => c + 1)
        onOpenChange(true)
      } else {
        // Close triggers (X, overlay, ESC) go through dirty check
        contentRef.current?.requestClose()
      }
    },
    [onOpenChange]
  )

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-describedby={undefined}
        className="flex h-[min(800px,90vh)] w-[min(800px,80vw)] max-w-none flex-col gap-0 rounded-xl p-0"
      >
        <SettingsDialogContent
          key={openCount}
          ref={contentRef}
          onClose={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  )
}
