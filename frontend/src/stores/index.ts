/**
 * Stores Module Exports
 */
export {
  useChatStore,
  useSessionMessages,
  useSessionStatus,
  useNovncUrl,
  useNovncPassword,
  useBrowserViewMode,
  usePlaybackState,
  useMountedFolder,
  useSessionAgentMode,
  useIsCuaActive,
  resetStore,
} from './chatStore'

export { useUIStore } from './uiStore'

export {
  useNotificationStore,
  useUnseenNotificationCount,
  useUnseenNotifications,
  useHasNotification,
} from './notificationStore'

export { useFolderPreferencesStore } from './folderPreferencesStore'
export { useOnboardingStore } from './onboardingStore'
export { useBackendHealthStore } from './backendHealthStore'

// Re-export types needed by consumers of stores
export type { Notification, NotificationType, BrowserViewMode } from '@/types'
