/**
 * Code Block Component
 *
 * Displays code with syntax highlighting using Prism.js.
 * Theme-aware: adapts to light/dark mode via CSS in index.css.
 *
 * Visual style (rounded-xl, border, shadow-sm) must stay consistent
 * with PreBlock and Markdown's <pre> (MarkdownPre).
 */

import { useMemo } from 'react'
import { useTheme, useWrapState } from '@/hooks'
import { WrapToggleButton } from '@/components/common'
import { MAX_CONTENT_BLOCK_HEIGHT } from '@/lib/constants'
import { highlightCode } from '@/lib/prismConfig'

export interface CodeBlockProps {
  /** Code content to display */
  children: string
  /** Language for syntax highlighting (e.g., 'json', 'python', 'bash') */
  language?: string
  /** Whether to wrap long lines (default: false, use horizontal scroll) */
  wrap?: boolean
  /** Maximum height before scrolling (default: 500px) */
  maxHeight?: number
}

/**
 * Renders code content with syntax highlighting.
 * Falls back to plain text if language is not recognized.
 */
export function CodeBlock({
  children,
  language,
  wrap,
  maxHeight = MAX_CONTENT_BLOCK_HEIGHT,
}: CodeBlockProps) {
  const theme = useTheme()
  const [localWrap, setLocalWrap] = useWrapState(wrap)

  const highlightedHtml = useMemo(() => highlightCode(children, language), [children, language])

  // Whitespace styles based on wrap state
  const preStyle = {
    margin: 0,
    ...(localWrap && { whiteSpace: 'pre-wrap' as const, wordBreak: 'break-word' as const }),
  }

  return (
    <div className="group/code relative">
      <WrapToggleButton
        wrap={localWrap}
        onToggle={() => setLocalWrap((w) => !w)}
        groupName="code"
      />
      <div
        className="code-editor-wrapper border-border overflow-auto rounded-xl border shadow-sm"
        data-theme={theme}
        style={{ maxHeight }}
      >
        {highlightedHtml ? (
          <pre className="p-4" style={preStyle}>
            <code
              className="font-mono text-xs leading-none"
              dangerouslySetInnerHTML={{ __html: highlightedHtml }}
            />
          </pre>
        ) : (
          // Fallback: plain monospace text
          <pre className="p-4" style={preStyle}>
            <code className="font-mono text-xs leading-none">{children}</code>
          </pre>
        )}
      </div>
    </div>
  )
}
