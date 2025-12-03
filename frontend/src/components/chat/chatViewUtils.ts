/**
 * ChatView utility functions
 *
 * Pure functions extracted from ChatView.tsx for testing.
 */

import type { ControlState, SessionStatus } from '@/types'

/**
 * Decide whether a user-submitted chat message should be sent as an
 * `input_response` (vs. starting a new task with `start`).
 *
 * Routes to `input_response` when:
 * - Backend has a pending InputRequest (text prompt, approval, or takeover pause).
 * - User is in browser takeover mode (`controlState === 'user'`) and is now
 *   providing post-takeover feedback that resolves the takeover InputRequest.
 * - Agent is actively running or paused — the backend's mid-run inbox queues
 *   the message and the agent drains it at the next checkpoint (PR #614).
 *
 * Otherwise (`created` / `completed` / `stopped` / `error`), the message
 * starts a new task via `start`.
 */
export function shouldUseInputResponse(args: {
  hasInputRequest: boolean
  controlState: ControlState
  sessionStatus: SessionStatus
}): boolean {
  const { hasInputRequest, controlState, sessionStatus } = args
  return (
    hasInputRequest ||
    controlState === 'user' ||
    sessionStatus === 'active' ||
    sessionStatus === 'paused'
  )
}
