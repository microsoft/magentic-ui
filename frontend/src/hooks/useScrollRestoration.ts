import { useRef, useEffect, useCallback } from 'react'

interface ScrollState {
  /** ID of the first visible item */
  itemId: string
  /** Offset from the top of the item to the top of the viewport (for sub-item precision) */
  offsetFromTop: number
}

// Store scroll states outside hook to persist across re-renders and component instances
// Uses LRU eviction: Map maintains insertion order, so we delete oldest entries when full
const scrollStates = new Map<string, ScrollState>()
const MAX_SCROLL_STATES = 100

interface UseScrollRestorationOptions {
  /** Unique key to identify this scroll context (e.g., sessionId) */
  key: string | undefined
  /**
   * Whether this scroll container is currently active/visible.
   * - When changing from true → false: saves current scroll position
   * - When changing from false → true: restores saved scroll position
   */
  isActive: boolean
}

interface UseScrollRestorationReturn {
  /** Ref to attach to the scroll container */
  scrollRef: React.RefObject<HTMLDivElement | null>
  /** Callback to register item element refs for scroll tracking */
  handleItemRef: (id: string, element: HTMLDivElement | null) => void
}

/**
 * Hook for preserving scroll position at item-level when switching sessions.
 * Uses IntersectionObserver to track the first visible item and restores
 * scroll position accurately even after window resizes or content changes.
 *
 * @example
 * ```tsx
 * const { scrollRef, handleItemRef } = useScrollRestoration({
 *   key: sessionId,
 *   isActive: isSelected,
 * })
 *
 * return (
 *   <div ref={scrollRef} className="overflow-y-auto">
 *     {items.map(item => (
 *       <div key={item.id} ref={el => handleItemRef(item.id, el)}>
 *         {item.content}
 *       </div>
 *     ))}
 *   </div>
 * )
 * ```
 */
export function useScrollRestoration({
  key,
  isActive,
}: UseScrollRestorationOptions): UseScrollRestorationReturn {
  const scrollRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const observerRef = useRef<IntersectionObserver | null>(null)
  const observedElementsRef = useRef<Set<HTMLDivElement>>(new Set())
  // Track visible items with their top positions
  const visibleItemsRef = useRef<Map<string, number>>(new Map())

  // Track item element refs and observe new elements
  const handleItemRef = useCallback((id: string, element: HTMLDivElement | null) => {
    if (element) {
      itemRefs.current.set(id, element)
      element.setAttribute('data-scroll-id', id)

      // Observe if observer exists and not already observed
      if (observerRef.current && !observedElementsRef.current.has(element)) {
        observerRef.current.observe(element)
        observedElementsRef.current.add(element)
      }
    } else {
      const existingElement = itemRefs.current.get(id)
      if (existingElement) {
        observerRef.current?.unobserve(existingElement)
        observedElementsRef.current.delete(existingElement)
        visibleItemsRef.current.delete(id)
      }
      itemRefs.current.delete(id)
    }
  }, [])

  // Set up IntersectionObserver to track visible items
  useEffect(() => {
    if (!scrollRef.current) return

    const scrollContainer = scrollRef.current

    observerRef.current = new IntersectionObserver(
      (entries) => {
        // Update visible items map based on intersection changes
        entries.forEach((entry) => {
          const id = entry.target.getAttribute('data-scroll-id')
          if (!id) return

          if (entry.isIntersecting) {
            visibleItemsRef.current.set(id, entry.boundingClientRect.top)
          } else {
            visibleItemsRef.current.delete(id)
          }
        })
      },
      {
        root: scrollContainer,
        threshold: 0, // Single threshold is enough - just need to know if visible
      }
    )

    // Observe all existing elements that were registered before observer was created
    const observedElements = observedElementsRef.current
    const visibleItems = visibleItemsRef.current

    itemRefs.current.forEach((element) => {
      if (!observedElements.has(element)) {
        observerRef.current?.observe(element)
        observedElements.add(element)
      }
    })

    return () => {
      observerRef.current?.disconnect()
      observerRef.current = null
      observedElements.clear()
      visibleItems.clear()
    }
  }, [key])

  // Save scroll state when becoming inactive
  useEffect(() => {
    if (!isActive && key && scrollRef.current) {
      // Find the first visible item (topmost)
      let firstVisibleId: string | null = null
      let minTop = Infinity

      // First try using tracked visible items
      if (visibleItemsRef.current.size > 0) {
        visibleItemsRef.current.forEach((_, id) => {
          // Get fresh position since stored value might be stale
          const element = itemRefs.current.get(id)
          if (element) {
            const rect = element.getBoundingClientRect()
            if (rect.top < minTop) {
              minTop = rect.top
              firstVisibleId = id
            }
          }
        })
      }

      // Fallback: if no visible items tracked, scan all items
      if (!firstVisibleId && itemRefs.current.size > 0) {
        const containerRect = scrollRef.current.getBoundingClientRect()
        itemRefs.current.forEach((element, id) => {
          const rect = element.getBoundingClientRect()
          // Check if item is visible in the scroll container
          if (rect.bottom > containerRect.top && rect.top < containerRect.bottom) {
            if (rect.top < minTop) {
              minTop = rect.top
              firstVisibleId = id
            }
          }
        })
      }

      if (firstVisibleId) {
        const itemElement = itemRefs.current.get(firstVisibleId)
        if (itemElement && scrollRef.current) {
          const containerRect = scrollRef.current.getBoundingClientRect()
          const itemRect = itemElement.getBoundingClientRect()
          const offsetFromTop = itemRect.top - containerRect.top

          // LRU: delete existing entry to move it to end (Map maintains insertion order)
          if (scrollStates.has(key)) {
            scrollStates.delete(key)
          }
          // Evict oldest entry if at capacity
          if (scrollStates.size >= MAX_SCROLL_STATES) {
            const oldestKey = scrollStates.keys().next().value
            if (oldestKey) scrollStates.delete(oldestKey)
          }
          scrollStates.set(key, { itemId: firstVisibleId, offsetFromTop })
        }
      }
    }
  }, [isActive, key])

  // Restore scroll state when becoming active
  useEffect(() => {
    if (isActive && key && scrollRef.current) {
      const savedState = scrollStates.get(key)

      if (savedState) {
        // Use requestAnimationFrame to ensure DOM is ready
        requestAnimationFrame(() => {
          const itemElement = itemRefs.current.get(savedState.itemId)

          if (itemElement && scrollRef.current) {
            const containerRect = scrollRef.current.getBoundingClientRect()
            const itemRect = itemElement.getBoundingClientRect()
            const currentOffset = itemRect.top - containerRect.top
            const scrollAdjustment = currentOffset - savedState.offsetFromTop

            scrollRef.current.scrollTop += scrollAdjustment
          }
        })
      }
    }
  }, [isActive, key])

  return { scrollRef, handleItemRef }
}
