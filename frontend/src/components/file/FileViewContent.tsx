/**
 * File Content Renderer
 *
 * Renders file content based on file type.
 * Reuses existing Markdown and CodeBlock components — zero new dependencies.
 */

import { useEffect, useReducer, useMemo } from 'react'
import { Markdown } from '@/components/common'
import { useTheme } from '@/hooks'
import { highlightCode, normalizeLanguage } from '@/lib/prismConfig'
import { getFileDownloadUrl, isMarkdownFile, isCodeFile, isImageFile } from '@/lib/fileUtils'
import type { FileInfo } from '@/types'

// =============================================================================
// Props
// =============================================================================

export interface FileViewContentProps {
  /** File to display */
  file: FileInfo
  /** Whether to wrap long lines (for text/code) */
  wrap?: boolean
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders file content by type:
 * - Markdown → <Markdown>
 * - Code → <CodeBlock> with Prism.js
 * - Plain text → <pre> monospace
 * - Image → <img> object-contain
 * - PDF → <iframe>
 * - Other → "Cannot preview" + download link
 */
export function FileViewContent({ file, wrap = false }: FileViewContentProps) {
  const url = getFileDownloadUrl(file)
  const ext = file.extension?.toLowerCase() || ''

  // Image: render directly
  if (isImageFile(ext)) {
    return (
      <div className="flex size-full items-center justify-center">
        <img src={url} alt={file.name} className="max-h-full max-w-full object-contain" />
      </div>
    )
  }

  // PDF: use browser's built-in viewer
  // navpanes=0 hides sidebar, toolbar=0 hides Chrome's PDF viewer toolbar
  if (ext === 'pdf') {
    return (
      <iframe
        src={`${url}#toolbar=0&navpanes=0`}
        title={file.name}
        className="size-full border-0"
      />
    )
  }

  // Text-based files: fetch content and render
  return <TextFileContent file={file} url={url} ext={ext} wrap={wrap} />
}

// =============================================================================
// Text File Content (fetch + render)
// =============================================================================

interface TextFileContentProps {
  file: FileInfo
  url: string
  ext: string
  wrap: boolean
}

function TextFileContent({ file, url, ext, wrap }: TextFileContentProps) {
  const isValidUrl = url && url.startsWith('/files/')

  // Fetch text content from the URL
  const fetchState = useTextFetch(isValidUrl ? url : null)

  if (!isValidUrl) {
    return <UnsupportedFile file={file} message="File not available for preview" />
  }

  if (fetchState.status === 'loading' || fetchState.status === 'idle') {
    return (
      <div className="flex size-full items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading...</span>
      </div>
    )
  }

  if (fetchState.status === 'error') {
    return <UnsupportedFile file={file} message={fetchState.error} />
  }

  const content = fetchState.content

  // Empty file
  if (!content.trim()) {
    return (
      <div className="flex size-full items-center justify-center">
        <span className="text-muted-foreground text-sm">This file is empty</span>
      </div>
    )
  }

  // Markdown
  if (isMarkdownFile(ext)) {
    return (
      <div className="overflow-auto p-5">
        <Markdown>{content}</Markdown>
      </div>
    )
  }

  // Code (with syntax highlighting — flat rendering, no card wrapper)
  if (isCodeFile(ext)) {
    return <HighlightedCode content={content} language={ext} wrap={wrap} />
  }

  // Plain text (txt, csv, log, etc.)
  return (
    <div className="overflow-auto p-5">
      <pre
        className={`text-foreground font-mono text-xs leading-relaxed ${wrap ? 'wrap-break-word whitespace-pre-wrap' : ''}`}
      >
        {content}
      </pre>
    </div>
  )
}

// =============================================================================
// Text Fetch Hook
// =============================================================================

type FetchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; content: string }
  | { status: 'error'; error: string }

type FetchAction =
  | { type: 'start' }
  | { type: 'success'; content: string }
  | { type: 'error'; error: string }

function fetchReducer(_: FetchState, action: FetchAction): FetchState {
  switch (action.type) {
    case 'start':
      return { status: 'loading' }
    case 'success':
      return { status: 'success', content: action.content }
    case 'error':
      return { status: 'error', error: action.error }
  }
}

/** Simple hook to fetch text content from a URL. Returns null url as no-op. */
function useTextFetch(url: string | null) {
  const [state, dispatch] = useReducer(fetchReducer, { status: url ? 'loading' : 'idle' })

  useEffect(() => {
    if (!url) return

    let cancelled = false
    const controller = new AbortController()
    dispatch({ type: 'start' })

    fetch(url, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.text()
      })
      .then((text) => {
        if (!cancelled) dispatch({ type: 'success', content: text })
      })
      .catch((err) => {
        if (!cancelled && err.name !== 'AbortError') {
          dispatch({ type: 'error', error: `Failed to load: ${err.message}` })
        }
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [url])

  return state
}

// =============================================================================
// Unsupported File
// =============================================================================

function UnsupportedFile({ file, message }: { file: FileInfo; message: string }) {
  const url = getFileDownloadUrl(file)
  return (
    <div className="text-muted-foreground flex size-full flex-col items-center justify-center gap-3">
      <p className="text-sm">{message}</p>
      {url && url.startsWith('/files/') && (
        <a
          href={url}
          download={file.name}
          className="text-primary text-sm underline hover:no-underline"
        >
          Download {file.name}
        </a>
      )}
    </div>
  )
}

// =============================================================================
// Highlighted Code (flat, no card wrapper)
// =============================================================================

function HighlightedCode({
  content,
  language,
  wrap,
}: {
  content: string
  language: string
  wrap: boolean
}) {
  const theme = useTheme()
  const lang = normalizeLanguage(language) || language

  const html = useMemo(() => highlightCode(content, language), [content, language])

  return (
    <div className="code-editor-wrapper p-5" data-theme={theme}>
      <pre
        className={`font-mono text-xs leading-relaxed ${wrap ? 'wrap-break-word whitespace-pre-wrap' : ''}`}
        style={{ margin: 0 }}
      >
        {html ? (
          <code className={`language-${lang}`} dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <code className="text-muted-foreground">{content}</code>
        )}
      </pre>
    </div>
  )
}
