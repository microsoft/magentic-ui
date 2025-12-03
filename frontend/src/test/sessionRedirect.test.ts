/**
 * Tests for findInvalidSessionRedirect.
 *
 * Regression coverage for issue #582: pointing the URL at a non-existent
 * session ID would render the empty-state sample prompts. The fix is a
 * page-level redirect that funnels invalid IDs back to the top of the
 * sidebar (or the dashboard if the list is empty). This file tests that
 * decision logic in isolation, without bringing React Router / TanStack
 * Query / Zustand into the test setup.
 */
import { describe, it, expect } from 'vitest'
import { findInvalidSessionRedirect } from '@/lib/sessionRedirect'
import { DRAFT_SESSION_ID } from '@/lib/constants'
import type { UISession } from '@/types'

// =============================================================================
// Helpers
// =============================================================================

function realSession(id: number, title = `Session ${id}`): UISession {
  return { id, title, status: 'completed', updatedAt: '2025-01-01T00:00:00Z' }
}

function draftUISession(): UISession {
  return { id: DRAFT_SESSION_ID, title: 'Draft', status: 'created' }
}

const NO_ERROR = null

// =============================================================================
// Tests
// =============================================================================

describe('findInvalidSessionRedirect', () => {
  describe('no redirect cases', () => {
    it('returns null when no sessionId is in the URL', () => {
      expect(
        findInvalidSessionRedirect({
          sessionId: undefined,
          draftSession: null,
          sessions: [realSession(1)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBeNull()
    })

    it('returns null while the session list is still loading', () => {
      // Avoid redirecting away from a valid session just because it
      // hasn't been fetched yet.
      expect(
        findInvalidSessionRedirect({
          sessionId: 5,
          draftSession: null,
          sessions: [],
          isLoading: true,
          error: NO_ERROR,
        })
      ).toBeNull()
    })

    it('returns null when the real sessionId exists in the list', () => {
      expect(
        findInvalidSessionRedirect({
          sessionId: 2,
          draftSession: null,
          sessions: [realSession(1), realSession(2), realSession(3)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBeNull()
    })

    it('returns null when the URL points at a draft and the in-memory draft exists', () => {
      const draft = draftUISession()
      expect(
        findInvalidSessionRedirect({
          sessionId: DRAFT_SESSION_ID,
          draftSession: draft,
          // useSessionListWithDraft prepends the draft to the API list.
          sessions: [draft, realSession(1)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBeNull()
    })

    it('returns null when the session list query failed (real id)', () => {
      // If the list itself failed, `sessions` is empty for the wrong
      // reason. Bouncing the user to `/` would hide the error and lose
      // their typed URL — let SessionView render its error state instead.
      expect(
        findInvalidSessionRedirect({
          sessionId: 5,
          draftSession: null,
          sessions: [],
          isLoading: false,
          error: new Error('boom'),
        })
      ).toBeNull()
    })

    it('returns null when the session list query failed (draft sentinel)', () => {
      expect(
        findInvalidSessionRedirect({
          sessionId: DRAFT_SESSION_ID,
          draftSession: null,
          sessions: [],
          isLoading: false,
          error: new Error('boom'),
        })
      ).toBeNull()
    })
  })

  describe('redirect cases', () => {
    it('redirects to the most recent real session when the real sessionId is missing', () => {
      // Issue #582: hand-typed/stale ID 6 is not in the list — go to the
      // top of the sidebar (sessions are pre-sorted by latest activity).
      expect(
        findInvalidSessionRedirect({
          sessionId: 6,
          draftSession: null,
          sessions: [realSession(3), realSession(2), realSession(1)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBe('/sessions/3')
    })

    it('redirects to the dashboard when no sessions exist', () => {
      expect(
        findInvalidSessionRedirect({
          sessionId: 99,
          draftSession: null,
          sessions: [],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBe('/')
    })

    it('redirects to the first real session when the draft sentinel is in URL but the draft is gone', () => {
      // Existing scenario: page refresh dropped the in-memory draft, so
      // `sessions` no longer contains the draft entry either.
      expect(
        findInvalidSessionRedirect({
          sessionId: DRAFT_SESSION_ID,
          draftSession: null,
          sessions: [realSession(7), realSession(5)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBe('/sessions/7')
    })

    it('redirects to dashboard when draft is gone and no real sessions exist either', () => {
      expect(
        findInvalidSessionRedirect({
          sessionId: DRAFT_SESSION_ID,
          draftSession: null,
          sessions: [],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBe('/')
    })

    it('redirects to the draft entry when present at the top of the sidebar', () => {
      // useSessionListWithDraft puts the draft at index 0. When a user
      // hits an unknown real ID and a draft is in flight, sending them
      // to the draft (== the visible top of the sidebar) is preferable
      // to skipping over it: the draft is real UI state they can use.
      const draft = draftUISession()
      expect(
        findInvalidSessionRedirect({
          sessionId: 999,
          draftSession: draft,
          sessions: [draft, realSession(4), realSession(2)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBe(`/sessions/${DRAFT_SESSION_ID}`)
    })

    it('redirects when sessionId is NaN (e.g. URL like /sessions/abc)', () => {
      // parseInt('abc', 10) → NaN; isDraftSession(NaN)=false; NaN never
      // === any number, so the existence check correctly fails.
      expect(
        findInvalidSessionRedirect({
          sessionId: Number.NaN,
          draftSession: null,
          sessions: [realSession(1)],
          isLoading: false,
          error: NO_ERROR,
        })
      ).toBe('/sessions/1')
    })
  })
})
