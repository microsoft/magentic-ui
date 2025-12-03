/**
 * Tests for browser-side session auth (api/auth.ts).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  getSessionToken,
  getAuthHeaders,
  createAuthenticatedWebSocket,
  WS_PROTOCOL_TAG,
} from '@/api/auth'

const TOKEN = 'test-session-token-abc123'

describe('api/auth', () => {
  beforeEach(() => {
    // Each test controls whether the token is present.
    delete window.__MAGUI_TOKEN__
  })

  describe('getSessionToken', () => {
    it('returns the injected token', () => {
      window.__MAGUI_TOKEN__ = TOKEN
      expect(getSessionToken()).toBe(TOKEN)
    })

    it('returns empty string when no token is injected', () => {
      expect(getSessionToken()).toBe('')
    })
  })

  describe('getAuthHeaders', () => {
    it('returns Authorization header when token is present', () => {
      window.__MAGUI_TOKEN__ = TOKEN
      expect(getAuthHeaders()).toEqual({ Authorization: `Bearer ${TOKEN}` })
    })

    it('returns empty object when no token is present (dev mode)', () => {
      expect(getAuthHeaders()).toEqual({})
    })
  })

  describe('createAuthenticatedWebSocket', () => {
    const wsCtor = vi.fn()

    beforeEach(() => {
      wsCtor.mockReset()
      vi.stubGlobal('WebSocket', wsCtor as unknown as typeof WebSocket)
    })

    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('passes the token via Sec-WebSocket-Protocol when present', () => {
      window.__MAGUI_TOKEN__ = TOKEN
      createAuthenticatedWebSocket('ws://localhost/api/ws/runs/1')
      expect(wsCtor).toHaveBeenCalledWith('ws://localhost/api/ws/runs/1', [WS_PROTOCOL_TAG, TOKEN])
    })

    it('omits the subprotocol when no token is present (dev mode)', () => {
      createAuthenticatedWebSocket('ws://localhost/api/ws/runs/1')
      expect(wsCtor).toHaveBeenCalledWith('ws://localhost/api/ws/runs/1')
      expect(wsCtor.mock.calls[0]).toHaveLength(1)
    })
  })
})
