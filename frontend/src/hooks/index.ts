export { useScrollRestoration } from './useScrollRestoration'
export { useScrollToImportantBackgroundMessage } from './useScrollToImportantBackgroundMessage'
export { useTheme } from './useTheme'
export { useWebSocketManager, WebSocketManagerProvider } from './useWebSocketManager'
export { useAutoScrollToBottom } from './useAutoScrollToBottom'
export { useEnsureSessionData } from './useEnsureSessionData'
export { useCollapsibleGroup, type CollapsibleGroupType } from './useCollapsibleGroup'
export { useResponsiveLayout } from './useResponsiveLayout'
export { useWrapState } from './useWrapState'
export { useFileAttachments } from './useFileAttachments'
export { useSessionPlayback } from './useSessionPlayback'
export { useNow } from './useNow'
export { useConnectionIssue } from './useConnectionIssue'
export { useBackendHealthPolling } from './useBackendHealthPolling'

// Re-export ActiveRun type (defined in @/types/websocket.ts, re-exported by useWebSocketManager)
export type { ActiveRun } from './useWebSocketManager'

// Session hooks are exported directly from @/api/sessions
