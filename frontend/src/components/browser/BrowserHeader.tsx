/**
 * BrowserHeader Component
 *
 * Toolbar with Globe icon + centered title and action buttons.
 * Aligned with FileViewHeader layout pattern.
 *
 * Button layout by mode:
 * - embedded:  [Expand]
 * - expanded:  [Maximize] [Close]
 * - maximized: [Side-by-side] [Close]
 */
import { Globe, Maximize, Columns2, X, Expand } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useResponsiveLayout } from '@/hooks'
import type { BrowserViewMode } from '@/types'

// =============================================================================
// Types
// =============================================================================

interface BrowserHeaderProps {
  /** Current view mode */
  mode: BrowserViewMode
  /** Called when mode changes via toolbar buttons */
  onModeChange: (mode: BrowserViewMode) => void
  /** Centered title text (e.g., "Browser (Live)", "Browser (History)") */
  title?: string
}

// =============================================================================
// Component
// =============================================================================

export function BrowserHeader({ mode, onModeChange, title }: BrowserHeaderProps) {
  const isExpanded = mode !== 'embedded'
  const isMaximized = mode === 'maximized'
  const { allowSideBySide } = useResponsiveLayout()

  return (
    <div className="relative flex items-center justify-end gap-2 p-2">
      {/* Centered title with Globe icon */}
      {title && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center gap-1">
          <Globe className="text-foreground size-4 shrink-0" />
          <span className="text-base leading-6 font-bold">{title}</span>
        </div>
      )}

      {/* Right side action buttons */}
      {isExpanded ? (
        <>
          {/* Maximize / Side-by-side toggle — hidden on narrow screens in maximized mode */}
          {(!isMaximized || allowSideBySide) && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon-sm"
                  onClick={() => onModeChange(isMaximized ? 'expanded' : 'maximized')}
                  aria-label={isMaximized ? 'Side-by-side view' : 'Maximize view'}
                >
                  {isMaximized ? (
                    <Columns2 className="size-3.5" />
                  ) : (
                    <Maximize className="size-3.5" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{isMaximized ? 'Side-by-side view' : 'Maximize view'}</TooltipContent>
            </Tooltip>
          )}

          {/* Close button */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="secondary"
                size="icon-sm"
                onClick={() => onModeChange('embedded')}
                aria-label="Close"
              >
                <X className="size-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Close</TooltipContent>
          </Tooltip>
        </>
      ) : (
        /* Embedded: single expand button */
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="icon-sm"
              onClick={() => onModeChange('expanded')}
              aria-label="Expand"
            >
              <Expand className="size-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Expand</TooltipContent>
        </Tooltip>
      )}
    </div>
  )
}
