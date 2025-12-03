/**
 * Notification Store
 *
 * Manages notifications for important events:
 * - input_request: Agent needs user input/approval
 * - error: Run encountered an error
 * - completion: Run completed successfully
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useShallow } from 'zustand/shallow'
import type { NotificationType, Notification } from '@/types'
import { MAX_NOTIFICATIONS } from '@/lib/constants'

interface NotificationState {
  notifications: Notification[]
}

interface NotificationActions {
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void
  updateSessionName: (sessionId: number, newName: string) => void
  removeSessionNotifications: (sessionId: number, type?: NotificationType) => void
  cleanupInvalidSessions: (validSessionIds: number[]) => void
  clearAll: () => void
  getCount: () => number
}

type NotificationStore = NotificationState & NotificationActions

const initialState: NotificationState = {
  notifications: [],
}

// Priority: higher = more severe, should be kept over lower priority
const NOTIFICATION_PRIORITY: Record<NotificationType, number> = {
  error: 3,
  input_request: 2,
  completion: 1,
}

export const useNotificationStore = create<NotificationStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      addNotification: (notification) => {
        const id = `${notification.sessionId}-${notification.type}-${Date.now()}`
        const newNotification: Notification = {
          ...notification,
          id,
          timestamp: Date.now(),
        }

        set((state) => {
          // Find existing notification for this session (one per session)
          const existingIndex = state.notifications.findIndex(
            (n) => n.sessionId === notification.sessionId
          )

          let newNotifications: Notification[]

          if (existingIndex >= 0) {
            const existing = state.notifications[existingIndex]
            const newPriority = NOTIFICATION_PRIORITY[notification.type]
            const existingPriority = NOTIFICATION_PRIORITY[existing.type]

            // Only replace if new notification is equally or more severe
            if (newPriority >= existingPriority) {
              newNotifications = [...state.notifications]
              newNotifications[existingIndex] = newNotification
            } else {
              // Keep existing (more severe), ignore new one
              return state
            }
          } else {
            // No existing notification for this session, add new
            newNotifications = [newNotification, ...state.notifications]
          }

          // Trim to max size (keep newest)
          if (newNotifications.length > MAX_NOTIFICATIONS) {
            newNotifications = newNotifications.slice(0, MAX_NOTIFICATIONS)
          }

          return { notifications: newNotifications }
        })
      },

      removeSessionNotifications: (sessionId, type) => {
        set((state) => ({
          notifications: state.notifications.filter(
            (n) => !(n.sessionId === sessionId && (type === undefined || n.type === type))
          ),
        }))
      },

      updateSessionName: (sessionId, newName) => {
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.sessionId === sessionId ? { ...n, sessionName: newName } : n
          ),
        }))
      },

      cleanupInvalidSessions: (validSessionIds) => {
        set((state) => ({
          notifications: state.notifications.filter((n) => validSessionIds.includes(n.sessionId)),
        }))
      },

      clearAll: () => {
        set({ notifications: [] })
      },

      getCount: () => {
        return get().notifications.length
      },
    }),
    {
      name: 'magentic-ui-notifications',
      // Only persist essential data, same limit as in-memory
      partialize: (state) => ({
        notifications: state.notifications.slice(0, MAX_NOTIFICATIONS),
      }),
    }
  )
)

// Selector hooks for common use cases
export function useUnseenNotificationCount(): number {
  return useNotificationStore((state) => state.notifications.length)
}

// For array selectors, use useShallow to prevent infinite loops
export function useUnseenNotifications(): Notification[] {
  return useNotificationStore(useShallow((state) => state.notifications))
}

/**
 * Check if a specific session has any unseen notifications
 */
export function useHasNotification(sessionId: number): boolean {
  return useNotificationStore((state) => state.notifications.some((n) => n.sessionId === sessionId))
}
