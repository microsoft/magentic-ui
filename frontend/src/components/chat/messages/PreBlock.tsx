/**
 * PreBlock — shared content block component
 *
 * Used by OrchestratorToolMessage and ToolResultMessage for displaying
 * multi-line text (args, results) with:
 * - Monospace font, scrollable, max-height constrained
 * - Hover-to-show wrap toggle button (shadcn Button + Tooltip)
 *
 * Visual style (rounded-xl, p-4, border, shadow-sm) must stay consistent
 * with CodeBlock and Markdown's <pre> (MarkdownPre).
 */

import { cn } from '@/lib/utils'
import { WrapToggleButton } from '@/components/common'
import { MAX_CONTENT_BLOCK_HEIGHT } from '@/lib/constants'
import { useWrapState } from '@/hooks'

// =============================================================================
// PreBlock
// =============================================================================

/**
 * Scrollable pre block for multi-line string values.
 * Rounded rectangle with muted background, monospace font, max-height scroll.
 * Includes a hover-visible wrap toggle button (rounded, icon-only).
 */
export function PreBlock({ children }: { children: string }) {
  const [wrap, setWrap] = useWrapState()

  return (
    <div className="group/pre relative">
      <WrapToggleButton wrap={wrap} onToggle={() => setWrap((w) => !w)} />
      <pre
        className={cn(
          'bg-muted border-border overflow-auto rounded-xl border p-4 font-mono text-xs leading-relaxed shadow-sm',
          wrap && 'wrap-break-word whitespace-pre-wrap'
        )}
        style={{ maxHeight: MAX_CONTENT_BLOCK_HEIGHT }}
      >
        {children}
      </pre>
    </div>
  )
}
