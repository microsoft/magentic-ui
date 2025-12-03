/**
 * Collapsible Header Component
 *
 * Reusable header button for collapsible message sections.
 * Used by: CodeExecutionMessage and future tool call displays.
 */

import { ChevronDown, ChevronUp } from 'lucide-react'

const SHIMMER_CYCLE_MS = 3000
const SHIMMER_PHASE_OFFSET_MS = Date.now() % SHIMMER_CYCLE_MS

interface CollapsibleHeaderBaseProps {
  icon: React.ReactNode
  label: string
  isExpanded: boolean
  /** When true, label uses shimmer effect to indicate in-progress state */
  isActive?: boolean
}

/** Interactive header — onToggle is required */
interface CollapsibleHeaderInteractiveProps extends CollapsibleHeaderBaseProps {
  disabled?: false
  onToggle: () => void
}

/** Non-interactive header — onToggle is not needed */
interface CollapsibleHeaderDisabledProps extends CollapsibleHeaderBaseProps {
  disabled: true
  onToggle?: never
}

export type CollapsibleHeaderProps =
  | CollapsibleHeaderInteractiveProps
  | CollapsibleHeaderDisabledProps

/**
 * Renders a clickable header with icon, label, and expand/collapse chevron.
 * Follows consistent styling across all collapsible message types.
 * When disabled, renders as a non-interactive placeholder (invisible chevron for layout).
 */
export function CollapsibleHeader({
  icon,
  label,
  isExpanded,
  onToggle,
  disabled = false,
  isActive = false,
}: CollapsibleHeaderProps) {
  const shimmerDelay = `-${SHIMMER_PHASE_OFFSET_MS}ms`

  const labelClass = isActive
    ? 'text-sm leading-5 font-bold shimmer-text'
    : 'text-sm leading-5 font-bold'

  const labelStyle = isActive
    ? ({ animationDelay: shimmerDelay } as React.CSSProperties)
    : undefined

  // Disabled state: render as static div without chevron
  if (disabled) {
    return (
      <div className="text-foreground flex items-center gap-2">
        {icon}
        <span className={labelClass} style={labelStyle}>
          {label}
        </span>
        <ChevronDown className="size-4 shrink-0 opacity-0" aria-hidden="true" />
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      className="text-foreground flex cursor-pointer items-center gap-2"
    >
      {icon}
      <span className={labelClass} style={labelStyle}>
        {label}
      </span>
      {isExpanded ? (
        <ChevronUp className="size-4 shrink-0" />
      ) : (
        <ChevronDown className="size-4 shrink-0" />
      )}
    </button>
  )
}
