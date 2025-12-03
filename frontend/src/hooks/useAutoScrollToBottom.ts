import { useRef, useEffect, useCallback } from 'react'

interface UseAutoScrollToBottomOptions {
  /** External scroll container ref (optional - will create one if not provided) */
  scrollRef?: React.RefObject<HTMLDivElement | null>
  /** Number of items to track for auto-scroll */
  itemCount: number
  /** Whether the component is currently active/visible */
  isActive?: boolean
  /** Threshold in pixels - how close to bottom to consider "at bottom" (default: 100) */
  threshold?: number
}

interface UseAutoScrollToBottomReturn {
  /** Ref to attach to the scroll container (same as input if provided) */
  scrollRef: React.RefObject<HTMLDivElement | null>
  /** Call this to scroll to bottom programmatically */
  scrollToBottom: () => void
  /** Whether user is currently at the bottom */
  isAtBottom: () => boolean
}

/**
 * Hook for auto-scrolling to bottom when new items arrive.
 *
 * Behavior:
 * - If user is at/near the bottom, automatically scroll to bottom when new items arrive
 * - If user has scrolled up to view history, don't auto-scroll (preserve their position)
 *
 * @example
 * ```tsx
 * const { scrollRef, scrollToBottom } = useAutoScrollToBottom({
 *   itemCount: messages.length,
 *   isActive: true,
 * })
 *
 * return (
 *   <div ref={scrollRef} className="overflow-y-auto">
 *     {messages.map(...)}
 *   </div>
 * )
 * ```
 */
export function useAutoScrollToBottom({
  scrollRef: externalScrollRef,
  itemCount,
  isActive = true,
  threshold = 100,
}: UseAutoScrollToBottomOptions): UseAutoScrollToBottomReturn {
  const internalScrollRef = useRef<HTMLDivElement>(null)
  const scrollRef = externalScrollRef ?? internalScrollRef
  const prevItemCountRef = useRef(itemCount)
  const wasAtBottomRef = useRef(true) // Assume at bottom initially

  /**
   * Check if user is at or near the bottom of the scroll container
   * Note: scrollRef is stable (created via useRef) and doesn't need to be in deps
   */
  const isAtBottom = useCallback(() => {
    const container = scrollRef.current
    if (!container) return true

    const { scrollTop, scrollHeight, clientHeight } = container
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight

    return distanceFromBottom <= threshold
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold])

  /**
   * Scroll to the bottom of the container
   * Note: scrollRef is stable (created via useRef) and doesn't need to be in deps
   */
  const scrollToBottom = useCallback(() => {
    const container = scrollRef.current
    if (!container) return

    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth',
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * Track scroll position to know if user is at bottom
   * Note: scrollRef is stable (created via useRef) and doesn't need to be in deps
   */
  useEffect(() => {
    const container = scrollRef.current
    if (!container) return

    const handleScroll = () => {
      wasAtBottomRef.current = isAtBottom()
    }

    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAtBottom])

  /**
   * Auto-scroll when new items arrive and user was at bottom
   * Note: scrollRef is stable (created via useRef) and doesn't need to be in deps
   */
  useEffect(() => {
    if (!isActive) return

    const prevCount = prevItemCountRef.current
    const hasNewItems = itemCount > prevCount
    prevItemCountRef.current = itemCount

    if (hasNewItems && wasAtBottomRef.current) {
      const container = scrollRef.current
      if (!container) return

      // If this is the initial load (from 0 items), use instant scroll
      // Otherwise use smooth scroll for new messages
      if (prevCount === 0) {
        container.scrollTop = container.scrollHeight
      } else {
        // Use requestAnimationFrame to ensure DOM has updated
        requestAnimationFrame(() => {
          scrollToBottom()
        })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemCount, isActive, scrollToBottom])

  return { scrollRef, scrollToBottom, isAtBottom }
}
