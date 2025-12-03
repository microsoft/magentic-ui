/**
 * App header component with layout controls.
 * Supports dashboard view (centered logo) and session view (with sidebar toggle).
 */
import { useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { SettingsDialog, SettingsTrigger } from '@/components/settings'
import { NotificationCenter } from './NotificationCenter'
import { useResponsiveLayout } from '@/hooks'
import { PanelLeftClose, PanelLeftOpen, LayoutGrid, Plus } from 'lucide-react'

export type AppLayout = 'dashboard' | 'sidebar-show' | 'sidebar-hide'

export interface HeaderProps {
  layout: AppLayout
  /** Optional slot for bottom content (e.g., tabs in dashboard) */
  bottomSlot?: ReactNode
  onNewSession: () => void
  /** Disable the New Session button (e.g., when a draft session is already selected) */
  newSessionDisabled?: boolean
  onToggleSidebar?: () => void
  onBackToDashboard?: () => void
}

export function Header({
  layout,
  bottomSlot,
  onNewSession,
  newSessionDisabled,
  onToggleSidebar,
  onBackToDashboard,
}: HeaderProps) {
  const isDashboard = layout === 'dashboard'
  const isSidebarVisible = layout === 'sidebar-show'
  const hasBottomSlot = !!bottomSlot

  // Use same breakpoint as sidebar visibility (820px = SIDEBAR + CHAT_MIN)
  const { allowSidebar } = useResponsiveLayout()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const openSettings = () => setSettingsOpen(true)

  const AppTitle = (
    <div className="flex shrink-0 items-center gap-2">
      <img src="/magentic-logo.svg" alt="MagenticLite" className="h-8 w-auto" />
      <span className="text-foreground pt-1 text-2xl leading-none tracking-tight">
        <span className="font-bold">Magentic</span>
        <span className="font-light">Lite</span>
      </span>
    </div>
  )

  const SidebarToggleButton = !isDashboard ? (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="secondary"
          size="icon"
          className="size-9"
          onClick={onToggleSidebar}
          aria-label={isSidebarVisible ? 'Hide sidebar' : 'Show sidebar'}
        >
          {isSidebarVisible ? (
            <PanelLeftClose className="size-4" />
          ) : (
            <PanelLeftOpen className="size-4" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{isSidebarVisible ? 'Hide sidebar' : 'Show sidebar'}</TooltipContent>
    </Tooltip>
  ) : null

  const DashboardButton = !isDashboard ? (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="secondary"
          size="icon"
          className="size-9"
          onClick={onBackToDashboard}
          aria-label="Back to dashboard"
        >
          <LayoutGrid className="size-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Back to dashboard</TooltipContent>
    </Tooltip>
  ) : null

  const NewSessionButton = (
    <Button onClick={onNewSession} disabled={newSessionDisabled}>
      <Plus className="size-4" />
      New Session
    </Button>
  )

  return (
    <header
      className={cn(
        'border-sidebar-border bg-sidebar w-full border-b',
        hasBottomSlot ? 'h-[120px]' : 'h-[68px]'
      )}
    >
      {/* Wide screen: absolute positioning for perfect center alignment */}
      {allowSidebar && (
        <div className="relative h-full">
          <div className="absolute top-4 left-5 flex items-center gap-4">
            {SidebarToggleButton}
            {DashboardButton}
          </div>

          <div className="absolute top-[18px] left-1/2 -translate-x-1/2">{AppTitle}</div>

          {hasBottomSlot && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2">{bottomSlot}</div>
          )}

          <div className="absolute top-4 right-5 flex items-center gap-3">
            {NewSessionButton}
            <NotificationCenter />
            <SettingsTrigger onClick={openSettings} />
          </div>
        </div>
      )}

      {/* Narrow screen: flexbox layout */}
      {!allowSidebar && (
        <div className="flex h-full flex-col">
          <div className="flex h-[68px] shrink-0 items-center justify-between px-5">
            {AppTitle}
            <div className="flex shrink-0 items-center gap-3">
              {DashboardButton}
              {NewSessionButton}
              <NotificationCenter />
              <SettingsTrigger onClick={openSettings} />
            </div>
          </div>

          {hasBottomSlot && (
            <div className="flex shrink-0 items-center justify-center pb-4">{bottomSlot}</div>
          )}
        </div>
      )}

      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </header>
  )
}
