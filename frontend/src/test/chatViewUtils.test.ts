/**
 * Tests for chatViewUtils
 *
 * Tests the routing decision in `shouldUseInputResponse`, which decides
 * whether a user-submitted chat message should be sent as an `input_response`
 * (vs. a `start` message that begins a new task).
 *
 * Routing matrix (see chatViewUtils.ts JSDoc for the canonical statement):
 *
 *   hasInputRequest=true   -> input_response (existing prompt: text/approval/takeover)
 *   controlState='user'    -> input_response (post-takeover feedback)
 *   sessionStatus='active' -> input_response (mid-run steer; backend inbox)
 *   sessionStatus='paused' -> input_response (mid-run steer; agent drains on resume)
 *   else                   -> start a new task
 */

import { describe, it, expect } from 'vitest'
import { shouldUseInputResponse } from '@/components/chat/chatViewUtils'
import type { ControlState, SessionStatus } from '@/types'

const ALL_STATUSES: SessionStatus[] = [
  'created',
  'active',
  'awaiting-input',
  'paused',
  'stopped',
  'completed',
  'error',
]

const ALL_CONTROL_STATES: ControlState[] = ['agent', 'user-pending', 'user']

const STATUSES_FORCING_INPUT_RESPONSE: SessionStatus[] = ['active', 'paused']
const TERMINAL_OR_FRESH_STATUSES: SessionStatus[] = ['created', 'stopped', 'completed', 'error']

describe('shouldUseInputResponse', () => {
  describe('hasInputRequest=true', () => {
    it.each(ALL_STATUSES)(
      'returns true regardless of session status (%s) when InputRequest is pending',
      (sessionStatus) => {
        expect(
          shouldUseInputResponse({
            hasInputRequest: true,
            controlState: 'agent',
            sessionStatus,
          })
        ).toBe(true)
      }
    )

    it.each(ALL_CONTROL_STATES)(
      'returns true regardless of control state (%s) when InputRequest is pending',
      (controlState) => {
        expect(
          shouldUseInputResponse({
            hasInputRequest: true,
            controlState,
            sessionStatus: 'awaiting-input',
          })
        ).toBe(true)
      }
    )
  })

  describe("controlState='user' (browser takeover feedback)", () => {
    it.each(ALL_STATUSES)(
      'returns true regardless of session status (%s) during takeover',
      (sessionStatus) => {
        expect(
          shouldUseInputResponse({
            hasInputRequest: false,
            controlState: 'user',
            sessionStatus,
          })
        ).toBe(true)
      }
    )

    it("does not trigger input_response routing for 'user-pending' (still awaiting backend)", () => {
      expect(
        shouldUseInputResponse({
          hasInputRequest: false,
          controlState: 'user-pending',
          sessionStatus: 'completed',
        })
      ).toBe(false)
    })
  })

  describe('mid-run steer (sessionStatus active or paused)', () => {
    it.each(STATUSES_FORCING_INPUT_RESPONSE)(
      'routes %s -> input_response (mid-run inbox queue) even without an InputRequest',
      (sessionStatus) => {
        expect(
          shouldUseInputResponse({
            hasInputRequest: false,
            controlState: 'agent',
            sessionStatus,
          })
        ).toBe(true)
      }
    )
  })

  describe('terminal / fresh statuses route to start', () => {
    it.each(TERMINAL_OR_FRESH_STATUSES)(
      'routes %s -> start (new task) when no InputRequest and no takeover',
      (sessionStatus) => {
        expect(
          shouldUseInputResponse({
            hasInputRequest: false,
            controlState: 'agent',
            sessionStatus,
          })
        ).toBe(false)
      }
    )

    // 'awaiting-input' is also a "no special path" case when explicit hasInputRequest
    // is false (defensive: store and status can briefly disagree). It should still
    // fall through to start, because the routing intentionally relies on
    // hasInputRequest, not the derived sessionStatus.
    it("routes 'awaiting-input' -> start when hasInputRequest is false (store source of truth)", () => {
      expect(
        shouldUseInputResponse({
          hasInputRequest: false,
          controlState: 'agent',
          sessionStatus: 'awaiting-input',
        })
      ).toBe(false)
    })
  })

  describe('regression: pre-PR #614 behavior preserved when InputRequest present', () => {
    it('returns true for awaiting-input + hasInputRequest (classic prompt response)', () => {
      expect(
        shouldUseInputResponse({
          hasInputRequest: true,
          controlState: 'agent',
          sessionStatus: 'awaiting-input',
        })
      ).toBe(true)
    })
  })
})
