/**
 * Markdown Renderer
 *
 * Configurable Markdown component with custom styling for chat messages.
 * Uses react-markdown with remark-gfm for GitHub Flavored Markdown support.
 *
 * Future extensions:
 * - Code syntax highlighting (Shiki)
 * - Copy button for code blocks
 * - Language labels for code blocks
 * - Collapsible sections
 */

import { useRef, type ComponentProps } from 'react'
import { cn } from '@/lib/utils'
import { WrapToggleButton } from './WrapToggleButton'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MAX_CONTENT_BLOCK_HEIGHT } from '@/lib/constants'
import { useWrapState } from '@/hooks'

/** Table cell that shows a tooltip with full text when content is truncated (computed on hover). */
function TruncatedTd(props: ComponentProps<'td'>) {
  const ref = useRef<HTMLTableCellElement>(null)

  const handleMouseEnter = () => {
    const el = ref.current
    if (el) {
      el.title = el.scrollWidth > el.clientWidth ? (el.textContent ?? '') : ''
    }
  }

  return (
    <td
      ref={ref}
      onMouseEnter={handleMouseEnter}
      className="max-w-xs truncate px-4 py-2"
      {...props}
    />
  )
}

/**
 * Pre block with hover-visible wrap toggle button (same UX as PreBlock).
 * Visual style (rounded-xl, p-4, border, shadow-sm) must stay consistent
 * with PreBlock and CodeBlock.
 */
function MarkdownPre({ children, ...props }: ComponentProps<'pre'>) {
  const [wrap, setWrap] = useWrapState()

  return (
    <div className="group/pre relative mb-3 last:mb-0">
      <WrapToggleButton wrap={wrap} onToggle={() => setWrap((w) => !w)} />
      <pre
        className={cn(
          'bg-muted border-border overflow-auto rounded-xl border p-4 shadow-sm',
          wrap && 'wrap-break-word whitespace-pre-wrap'
        )}
        style={{ maxHeight: MAX_CONTENT_BLOCK_HEIGHT }}
        {...props}
      >
        {children}
      </pre>
    </div>
  )
}

/**
 * Custom component mappings for Markdown elements.
 * Styled for chat context with compact spacing.
 */
const markdownComponents: Components = {
  // Links - open in new tab, same color as text with underline
  a: ({ href, children, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline hover:no-underline"
      {...props}
    >
      {children}
    </a>
  ),

  // Paragraphs - compact margins for chat
  p: ({ children, ...props }) => (
    <p className="mb-3 last:mb-0" {...props}>
      {children}
    </p>
  ),

  // Lists
  ul: ({ children, ...props }) => (
    <ul className="mb-3 list-disc pl-6 last:mb-0" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="mb-3 list-decimal pl-6 last:mb-0" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="mb-1" {...props}>
      {children}
    </li>
  ),

  // Code - basic styling, can enhance with Shiki later
  code: ({ className, children, ...props }) => {
    // className is "language-xxx" for code blocks, undefined for inline
    const isInline = !className
    return isInline ? (
      <code className="bg-muted rounded px-1.5 py-0.5 font-mono text-sm" {...props}>
        {children}
      </code>
    ) : (
      <code className={cn('font-mono text-sm', className)} {...props}>
        {children}
      </code>
    )
  },
  pre: MarkdownPre,

  // Blockquotes
  blockquote: ({ children, ...props }) => (
    <blockquote className="border-border mb-3 border-l-4 pl-4 italic last:mb-0" {...props}>
      {children}
    </blockquote>
  ),

  // Headings - sized for chat context (smaller than page headings)
  h1: ({ children, ...props }) => (
    <h1 className="mb-3 text-xl font-bold last:mb-0" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="mb-3 text-lg font-bold last:mb-0" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mb-2 text-base font-bold last:mb-0" {...props}>
      {children}
    </h3>
  ),

  // Tables - card-style with rounded corners and borders
  table: ({ children, ...props }) => (
    <div
      className="border-border mb-3 w-fit overflow-auto rounded-xl border shadow-sm last:mb-0"
      style={{ maxHeight: MAX_CONTENT_BLOCK_HEIGHT }}
    >
      <table className="border-collapse text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-muted sticky top-0 z-10" {...props}>
      {children}
    </thead>
  ),
  tbody: ({ children, ...props }) => <tbody {...props}>{children}</tbody>,
  th: ({ children, ...props }) => (
    <th className="px-4 pt-4 pb-3 text-left text-xs font-bold" {...props}>
      {children}
    </th>
  ),
  td: TruncatedTd,
  tr: ({ children, ...props }) => (
    <tr className="last:[&>td]:pb-4" {...props}>
      {children}
    </tr>
  ),
}

export interface MarkdownProps {
  /** Markdown content to render */
  children: string
  /** Additional CSS classes */
  className?: string
}

/**
 * Renders Markdown content with custom styling.
 *
 * @example
 * ```tsx
 * <Markdown>**Hello** world!</Markdown>
 * ```
 */
export function Markdown({ children, className }: MarkdownProps) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
