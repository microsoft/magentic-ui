import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

// =============================================================================
// CSS Utilities
// =============================================================================

/**
 * Combines multiple class names into a single string, intelligently merging Tailwind CSS classes.
 *
 * This utility function is the backbone of shadcn/ui's styling system. It combines:
 * - `clsx`: Conditionally constructs className strings
 * - `twMerge`: Merges Tailwind classes, resolving conflicts (e.g., "px-2 px-4" becomes "px-4")
 *
 * @param inputs - Any number of class values (strings, objects, arrays, etc.)
 * @returns A single optimized className string
 *
 * @example
 * ```tsx
 * // Basic usage
 * cn('px-2 py-1', 'bg-blue-500')
 * // => 'px-2 py-1 bg-blue-500'
 *
 * // Conditional classes
 * cn('px-2 py-1', isActive && 'bg-blue-500', !isActive && 'bg-gray-500')
 * // => 'px-2 py-1 bg-blue-500' (when isActive is true)
 *
 * // Tailwind conflict resolution
 * cn('px-2 py-1', 'px-4')
 * // => 'py-1 px-4' (px-2 is replaced by px-4)
 *
 * // With component props
 * <Button className={cn('px-4 py-2', props.className)} />
 * ```
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// =============================================================================
// VNC Utilities
// =============================================================================

/**
 * Build noVNC WebSocket URL from port number.
 * Uses current hostname and protocol for deployment flexibility.
 *
 * @param port - The noVNC port number
 * @returns WebSocket URL for VNC connection
 */
export function buildNovncUrl(port: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.hostname}:${port}/websockify`
}
