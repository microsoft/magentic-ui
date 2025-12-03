/**
 * useCollapsibleGroup Hook
 *
 * Manages expand/collapse state for collapsible message groups.
 * Used by CuaMessage, CodeExecutionMessage, and other collapsible components.
 *
 * Features:
 * - Default expanded state based on per-type detail toggles
 * - User override persistence between session switches
 * - Cleared when any detail toggle changes
 */
import { useCallback } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { useChatStore, useExpandedState } from '@/stores/chatStore'

/** Which detail toggle controls this collapsible group */
export type CollapsibleGroupType = 'reasoning' | 'toolCall'

export interface UseCollapsibleGroupResult {
  /** Whether the group is currently expanded */
  isExpanded: boolean
  /** Toggle the expanded state */
  toggle: () => void
}

/**
 * Hook for managing collapsible group state.
 *
 * @param sessionId - Session ID for state isolation
 * @param groupId - Unique identifier for the collapsible group
 * @param groupType - Which detail toggle controls this group
 * @returns Expanded state and toggle function
 *
 * @example
 * ```tsx
 * const { isExpanded, toggle } = useCollapsibleGroup(sessionId, groupId, 'toolCall')
 *
 * return (
 *   <CollapsibleHeader isExpanded={isExpanded} onToggle={toggle} />
 * )
 * ```
 */
export function useCollapsibleGroup(
  sessionId: number,
  groupId: string,
  groupType: CollapsibleGroupType
): UseCollapsibleGroupResult {
  const defaultExpanded = useUIStore((s) =>
    groupType === 'reasoning' ? s.showReasoningDetails : s.showToolCallDetails
  )
  const setExpandedOverride = useChatStore((s) => s.setExpandedOverride)

  // Get the current expanded state (considering user overrides)
  const isExpanded = useExpandedState(sessionId, groupId, defaultExpanded)

  // Handle user toggle
  const toggle = useCallback(() => {
    setExpandedOverride(sessionId, groupId, !isExpanded)
  }, [sessionId, groupId, isExpanded, setExpandedOverride])

  return { isExpanded, toggle }
}
