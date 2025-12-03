/**
 * WrapToggleButton
 *
 * Hover-visible wrap toggle button for code/pre blocks.
 * Shared by PreBlock, CodeBlock, and Markdown's <pre>.
 *
 * Must be placed inside a container with `group/pre` or `group/code` class
 * and `relative` positioning.
 */

import { WrapText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface WrapToggleButtonProps {
  wrap: boolean
  onToggle: () => void
  /** Tailwind group name for hover visibility (default: 'pre') */
  groupName?: string
}

export function WrapToggleButton({ wrap, onToggle, groupName = 'pre' }: WrapToggleButtonProps) {
  const hoverClass =
    groupName === 'pre'
      ? 'opacity-0 group-hover/pre:opacity-100'
      : 'opacity-0 group-hover/code:opacity-100'

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className={cn(
            'absolute top-3 right-3 z-10 size-8 transition-colors',
            hoverClass,
            wrap
              ? 'bg-accent text-accent-foreground'
              : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
          )}
          aria-label={wrap ? 'Disable line wrap' : 'Enable line wrap'}
        >
          <WrapText />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="left">{wrap ? 'Disable line wrap' : 'Enable line wrap'}</TooltipContent>
    </Tooltip>
  )
}
