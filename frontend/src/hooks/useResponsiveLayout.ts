/**
 * Responsive Layout Hook
 *
 * Provides dynamic layout state based on window width and sidebar visibility.
 *
 * Layout rules:
 * - Non side-by-side: Chat needs at least CHAT_MIN width
 *   → If window < SIDEBAR + CHAT_MIN, auto-hide sidebar
 * - Side-by-side: Chat + Browser share space (chat max CHAT_MAX, rest to browser)
 *   → If window < SIDEBAR + SIDE_BY_SIDE_MIN (or < SIDE_BY_SIDE_MIN without sidebar),
 *     switch to maximized mode
 */
import { useUIStore } from '@/stores'
import { useMediaQuery } from './useMediaQuery'
import { LAYOUT_WIDTHS } from '@/lib/constants'

interface ResponsiveLayoutState {
  /** Whether window is wide enough for sidebar (>= SIDEBAR + CHAT_MIN) */
  allowSidebar: boolean
  /** Whether side-by-side mode is allowed (window wide enough for chat + browser) */
  allowSideBySide: boolean
}

export function useResponsiveLayout(): ResponsiveLayoutState {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen)

  // Allow sidebar when window >= SIDEBAR + CHAT_MIN
  const allowSidebar = useMediaQuery(
    `(min-width: ${LAYOUT_WIDTHS.SIDEBAR + LAYOUT_WIDTHS.CHAT_MIN}px)`
  )

  // Side-by-side breakpoint depends on sidebar state
  const sideBySideBreakpoint = sidebarOpen
    ? LAYOUT_WIDTHS.SIDEBAR + LAYOUT_WIDTHS.SIDE_BY_SIDE_MIN
    : LAYOUT_WIDTHS.SIDE_BY_SIDE_MIN

  const allowSideBySide = useMediaQuery(`(min-width: ${sideBySideBreakpoint}px)`)

  return { allowSidebar, allowSideBySide }
}
