/**
 * useWrapState Hook
 *
 * Manages line wrap state for code/pre blocks.
 * Initializes from optional prop override or global wrapMode setting.
 * Resets all local overrides when global setting changes (same pattern as verboseMode).
 */

import { useState } from 'react'
import { useUIStore } from '@/stores/uiStore'

/**
 * @param propWrap - Optional prop-level override (e.g., CodeBlock's `wrap` prop)
 * @returns [wrap, setWrap] — local wrap state that syncs with global wrapMode
 */
export function useWrapState(
  propWrap?: boolean
): [boolean, React.Dispatch<React.SetStateAction<boolean>>] {
  const defaultWrap = useUIStore((s) => s.wrapMode)
  const [wrap, setWrap] = useState(propWrap ?? defaultWrap)
  const [prevDefault, setPrevDefault] = useState(defaultWrap)

  // Reset local state when global setting changes
  // (React-recommended pattern: storing info from previous renders)
  if (prevDefault !== defaultWrap) {
    setPrevDefault(defaultWrap)
    setWrap(propWrap ?? defaultWrap)
  }

  return [wrap, setWrap]
}
