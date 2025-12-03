/**
 * Tests for notificationStore
 *
 * Design: One notification per session. Existence = unseen, deletion = read.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useNotificationStore } from '@/stores/notificationStore'

describe('notificationStore', () => {
  // Reset store before each test
  beforeEach(() => {
    useNotificationStore.setState({
      notifications: [],
    })
  })

  // ---------------------------------------------------------------------------
  // addNotification
  // ---------------------------------------------------------------------------

  describe('addNotification', () => {
    it('adds a notification with generated id and timestamp', () => {
      const store = useNotificationStore.getState()
      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'input_request',
        message: 'Agent needs input',
      })

      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(1)
      expect(notifications[0].sessionId).toBe(1)
      expect(notifications[0].type).toBe('input_request')
      expect(notifications[0].id).toMatch(/^1-input_request-\d+$/)
      expect(notifications[0].timestamp).toBeGreaterThan(0)
    })

    it('replaces existing notification for same session (same type)', () => {
      const store = useNotificationStore.getState()

      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'input_request',
        message: 'First message',
      })

      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'input_request',
        message: 'Second message',
      })

      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(1)
      expect(notifications[0].message).toBe('Second message')
    })

    it('does not replace notification for different session', () => {
      const store = useNotificationStore.getState()

      store.addNotification({
        sessionId: 1,
        sessionName: 'Session 1',
        type: 'input_request',
        message: 'Message 1',
      })

      store.addNotification({
        sessionId: 2,
        sessionName: 'Session 2',
        type: 'input_request',
        message: 'Message 2',
      })

      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(2)
    })

    it('keeps error over completion for same session (priority)', () => {
      const store = useNotificationStore.getState()

      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'error',
        message: 'Error',
      })

      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'completion',
        message: 'Completed',
      })

      // Error is more severe, should be kept
      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(1)
      expect(notifications[0].type).toBe('error')
    })

    it('replaces completion with error for same session (priority)', () => {
      const store = useNotificationStore.getState()

      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'completion',
        message: 'Completed',
      })

      store.addNotification({
        sessionId: 1,
        sessionName: 'Test Session',
        type: 'error',
        message: 'Error',
      })

      // Error replaces completion (more severe)
      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(1)
      expect(notifications[0].type).toBe('error')
    })

    it('orders newest notifications first', () => {
      const store = useNotificationStore.getState()

      store.addNotification({
        sessionId: 1,
        sessionName: 'Session 1',
        type: 'completion',
        message: 'First',
      })

      store.addNotification({
        sessionId: 2,
        sessionName: 'Session 2',
        type: 'completion',
        message: 'Second',
      })

      const { notifications } = useNotificationStore.getState()
      expect(notifications[0].message).toBe('Second')
      expect(notifications[1].message).toBe('First')
    })
  })

  // ---------------------------------------------------------------------------
  // removeSessionNotifications
  // ---------------------------------------------------------------------------

  describe('removeSessionNotifications', () => {
    it('removes notification for a session', () => {
      const store = useNotificationStore.getState()
      store.addNotification({ sessionId: 1, sessionName: 'S1', type: 'error', message: 'E1' })
      store.addNotification({ sessionId: 2, sessionName: 'S2', type: 'error', message: 'E2' })

      store.removeSessionNotifications(1)

      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(1)
      expect(notifications[0].sessionId).toBe(2)
    })

    it('removes only specific type when provided', () => {
      const store = useNotificationStore.getState()

      // Add error first
      store.addNotification({ sessionId: 1, sessionName: 'S1', type: 'error', message: 'E1' })

      // Try to remove input_request (doesn't exist)
      store.removeSessionNotifications(1, 'input_request')

      // Error should still be there
      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(1)
      expect(notifications[0].type).toBe('error')
    })

    it('removes matching type when provided', () => {
      const store = useNotificationStore.getState()

      store.addNotification({
        sessionId: 1,
        sessionName: 'S1',
        type: 'input_request',
        message: 'I1',
      })

      store.removeSessionNotifications(1, 'input_request')

      const { notifications } = useNotificationStore.getState()
      expect(notifications).toHaveLength(0)
    })
  })

  // ---------------------------------------------------------------------------
  // getCount
  // ---------------------------------------------------------------------------

  describe('getCount', () => {
    it('returns total notification count', () => {
      const store = useNotificationStore.getState()
      store.addNotification({ sessionId: 1, sessionName: 'S1', type: 'error', message: 'E1' })
      store.addNotification({ sessionId: 2, sessionName: 'S2', type: 'error', message: 'E2' })

      expect(store.getCount()).toBe(2)
    })

    it('returns 0 when no notifications', () => {
      const store = useNotificationStore.getState()
      expect(store.getCount()).toBe(0)
    })
  })

  // ---------------------------------------------------------------------------
  // clearAll
  // ---------------------------------------------------------------------------

  describe('clearAll', () => {
    it('removes all notifications', () => {
      const store = useNotificationStore.getState()
      store.addNotification({ sessionId: 1, sessionName: 'S1', type: 'error', message: 'E1' })
      store.addNotification({ sessionId: 2, sessionName: 'S2', type: 'error', message: 'E2' })

      store.clearAll()

      expect(useNotificationStore.getState().notifications).toHaveLength(0)
    })
  })
})
