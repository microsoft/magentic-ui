/**
 * Message Utilities
 *
 * Helper functions for message content extraction and formatting.
 */

// =============================================================================
// Content Extraction
// =============================================================================

/**
 * Content item in message array format
 */
interface TextContentItem {
  type: 'text'
  text: string
}

interface ImageContentItem {
  type: 'image'
  url: string
}

type ContentItem = TextContentItem | ImageContentItem | string

/**
 * Extract text from message content (string or array).
 * Handles both `string` content and `ContentItem[]` array format uniformly.
 */
export function extractText(content: string | ContentItem[] | unknown): string {
  if (typeof content === 'string') return content
  if (Array.isArray(content)) return extractTextFromArray(content)
  return content != null ? String(content) : ''
}

/**
 * Extract text from message content array.
 * Assumes content is array format [{type: 'text', text: '...'}].
 */
export function extractTextFromArray(content: ContentItem[]): string {
  return content
    .map((item) => {
      if (typeof item === 'string') return item
      if (item.type === 'text') return item.text
      return null
    })
    .filter(Boolean)
    .join('\n')
}

/**
 * Extract image URL from message content array.
 * Returns the first image URL found, or null if none.
 */
export function extractImageUrl(content: ContentItem[]): string | null {
  for (const item of content) {
    if (typeof item === 'object' && item.type === 'image') {
      return item.url
    }
  }
  return null
}

/**
 * Unwrap JSON-wrapped user message content.
 * User messages have content like: '{"content": "actual text"}'
 */
export function unwrapUserContent(content: string): string {
  try {
    const parsed = JSON.parse(content)
    if (parsed?.content?.content) return String(parsed.content.content)
    if (parsed?.content) return String(parsed.content)
    return content
  } catch {
    return content
  }
}

// =============================================================================
// Content Formatting
// =============================================================================
