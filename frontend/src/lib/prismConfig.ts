/**
 * Prism Language Configuration
 *
 * Shared Prism.js language imports and alias mappings.
 * Used by both CodeBlock (chat messages) and FileViewContent (file preview).
 *
 * Prism core includes: markup (html/xml), css, clike, javascript.
 * php excluded — its markup-templating dependency breaks other language highlighting.
 */

import Prism from 'prismjs'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-markdown'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-jsx'
import 'prismjs/components/prism-tsx'
import 'prismjs/components/prism-yaml'
import 'prismjs/components/prism-sql'
import 'prismjs/components/prism-java'
import 'prismjs/components/prism-c'
import 'prismjs/components/prism-cpp'
import 'prismjs/components/prism-csharp'
import 'prismjs/components/prism-go'
import 'prismjs/components/prism-ruby'
import 'prismjs/components/prism-rust'
import 'prismjs/components/prism-swift'
import 'prismjs/components/prism-kotlin'
import 'prismjs/components/prism-scala'
import 'prismjs/components/prism-r'
import 'prismjs/components/prism-toml'
import 'prismjs/components/prism-docker'
import 'prismjs/components/prism-diff'

/**
 * Map of file extension aliases to Prism language names.
 */
export const LANG_ALIASES: Record<string, string> = {
  py: 'python',
  sh: 'bash',
  shell: 'bash',
  md: 'markdown',
  ts: 'typescript',
  js: 'javascript',
  yml: 'yaml',
  cs: 'csharp',
  rb: 'ruby',
  rs: 'rust',
  kt: 'kotlin',
  html: 'markup',
  xml: 'markup',
  dockerfile: 'docker',
}

/**
 * Normalize a language string to a Prism-supported name.
 * Returns undefined if input is empty.
 */
export function normalizeLanguage(lang?: string): string | undefined {
  if (!lang) return undefined
  const normalized = lang.toLowerCase().trim()
  return LANG_ALIASES[normalized] || normalized
}

/**
 * Highlight code using Prism.js.
 * Returns HTML string with <span class="token ..."> for styling, or null if language not supported.
 */
export function highlightCode(code: string, language?: string): string | null {
  const lang = normalizeLanguage(language)
  if (!lang) return null

  const grammar = Prism.languages[lang]
  if (!grammar) return null

  try {
    return Prism.highlight(code, grammar, lang)
  } catch {
    return null
  }
}

// Re-export Prism for direct access if needed
export { Prism }
