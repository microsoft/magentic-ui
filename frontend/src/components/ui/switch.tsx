import * as React from 'react'
import * as SwitchPrimitives from '@radix-ui/react-switch'

import { cn } from '@/lib/utils'

// Style the Root track using aria-checked instead of data-[state=...] because
// Radix Tooltip's TooltipTrigger (asChild) injects its own data-state onto the
// host element, overriding Switch's data-state and breaking the visual toggle.
// aria-checked is set by Radix Switch and is never overwritten by Tooltip.
// The Thumb is unaffected (Tooltip only decorates the trigger, not children).
//
// Disabled style: uses cursor-default (not cursor-not-allowed) for a subtle
// disabled appearance — tooltip remains functional.
const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitives.Root
    className={cn(
      'peer focus-visible:ring-ring focus-visible:ring-offset-background bg-input aria-checked:bg-primary/75 inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-sm transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-default disabled:opacity-50',
      className
    )}
    {...props}
    ref={ref}
  >
    <SwitchPrimitives.Thumb
      className={cn(
        'bg-background pointer-events-none block h-4 w-4 rounded-full shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0'
      )}
    />
  </SwitchPrimitives.Root>
))
Switch.displayName = SwitchPrimitives.Root.displayName

export { Switch }
