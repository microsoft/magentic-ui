/**
 * useScrollToImportantBackgroundMessage Hook Tests
 *
 * Verifies the background-arrival jump behavior: when a session goes
 * from background to foreground and a final-answer / input-request /
 * error message arrived in the meantime, the hook should scroll that
 * message into view rather than letting useScrollRestoration restore
 * the stale read position.
 *
 * Includes a regression test for the bug Copilot caught on PR #575:
 * the pointer-update effect was clobbering the baseline before the
 * detection effect could read it on the false → true render.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useMemo } from 'react'
import {
  useScrollToImportantBackgroundMessage,
  _resetLastSeenForTesting,
  _peekLastSeenForTesting,
} from '@/hooks/useScrollToImportantBackgroundMessage'
import type { ParsedMessage, Message } from '@/types'

// =============================================================================
// Test helpers
// =============================================================================

const SESSION_ID = 1

const rawStub = (id: string): Message => ({
  id: Number(id) || 0,
  session_id: SESSION_ID,
  run_id: 'run-1',
  config: { source: 'system', content: '' },
  created_at: new Date().toISOString(),
})

/** Build a parsed message of an arbitrary kind (default: harmless 'user'). */
function msg(id: string, kind: ParsedMessage['kind'] = 'user'): ParsedMessage {
  const base = {
    id,
    timestamp: '2026-01-01T00:00:00Z',
    source: 'system',
    raw: rawStub(id),
  }
  switch (kind) {
    case 'final-answer':
      return { ...base, kind: 'final-answer', content: 'done' }
    case 'input-request':
      return { ...base, kind: 'input-request', inputType: 'text_input', content: '?' }
    case 'error':
      return { ...base, kind: 'error', content: 'boom' }
    case 'text':
      return { ...base, kind: 'text', content: 'plain' }
    default:
      return { ...base, kind: 'user', content: '' }
  }
}

/**
 * Build a single scroll container with a child element for every message
 * id the test will ever pass — that way both "before background" and
 * "after re-entry" message sets share the same scrollIntoView mock and
 * the test can simply assert call count.
 */
function makeContainer(allMessageIds: string[]): {
  container: HTMLDivElement
  scrollIntoView: ReturnType<typeof vi.fn>
} {
  const scrollIntoView = vi.fn()
  const container = document.createElement('div')
  for (const id of allMessageIds) {
    const child = document.createElement('div')
    child.setAttribute('data-scroll-id', id)
    Object.defineProperty(child, 'scrollIntoView', { value: scrollIntoView, writable: true })
    container.appendChild(child)
  }
  return { container, scrollIntoView }
}

/** Wait for the hook's double-rAF scrollIntoView to have a chance to run. */
async function flushDoubleRaf(): Promise<void> {
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
}

interface HookProps {
  sessionId: number | undefined
  isActive: boolean
  messages: ParsedMessage[]
  scrollContainer: HTMLDivElement | null
}

/**
 * Wrapper that supplies a ref-like object pointing at the test's scroll
 * container. Using a memoized object instead of useRef avoids the
 * "Cannot access refs during render" lint while still satisfying the
 * RefObject<HTMLDivElement | null> contract the hook expects.
 */
function useTestHarness(props: HookProps) {
  const refLike = useMemo<{ current: HTMLDivElement | null }>(
    () => ({ current: props.scrollContainer }),
    [props.scrollContainer]
  )
  useScrollToImportantBackgroundMessage({
    sessionId: props.sessionId,
    isActive: props.isActive,
    messages: props.messages,
    scrollRef: refLike,
  })
}

/**
 * Minimal driver: starts in active mode and exposes `step()` to mutate
 * any subset of props between renders. Tests stay focused on transitions
 * rather than repeating boilerplate.
 */
function startHook(initial: Partial<HookProps>) {
  const props: HookProps = {
    sessionId: SESSION_ID,
    isActive: true,
    messages: [],
    scrollContainer: null,
    ...initial,
  }
  const { rerender } = renderHook((p: HookProps) => useTestHarness(p), { initialProps: props })
  return (overrides: Partial<HookProps>) => {
    Object.assign(props, overrides)
    rerender({ ...props })
  }
}

// =============================================================================
// Tests
// =============================================================================

describe('useScrollToImportantBackgroundMessage', () => {
  beforeEach(() => {
    _resetLastSeenForTesting()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not jump on the very first opening of a session (no baseline)', async () => {
    const { container, scrollIntoView } = makeContainer(['m1', 'final'])
    startHook({ messages: [msg('m1'), msg('final', 'final-answer')], scrollContainer: container })
    await flushDoubleRaf()
    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('advances the last-seen pointer while active (but not on the activation render)', () => {
    const { container } = makeContainer(['m1', 'm2'])
    const step = startHook({ messages: [msg('m1')], scrollContainer: container })

    // Activation render itself does NOT advance — that's the regression
    // guard that keeps the detection effect's baseline intact.
    expect(_peekLastSeenForTesting(SESSION_ID)).toBeUndefined()

    // Subsequent renders while still active DO advance
    step({ messages: [msg('m1'), msg('m2')] })
    expect(_peekLastSeenForTesting(SESSION_ID)).toBe('m2')
  })

  it('REGRESSION: jumps to a new important message arriving in the background (PR #575)', async () => {
    // Without the activation-render guard, the pointer-update effect
    // (declared first) would clobber the baseline to "final" before the
    // detection effect read it, and the jump would never fire.
    const { container, scrollIntoView } = makeContainer(['u', 'final'])
    const step = startHook({ messages: [msg('u')], scrollContainer: container })
    step({ messages: [msg('u')] }) // record baseline = "u"
    step({ isActive: false }) // background
    step({ isActive: true, messages: [msg('u'), msg('final', 'final-answer')] })
    await flushDoubleRaf()

    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' })
  })

  it.each([
    ['final-answer', 'final' as const],
    ['input-request', 'q' as const],
    ['error', 'err' as const],
  ])('jumps for new %s message', async (kind, id) => {
    const { container, scrollIntoView } = makeContainer(['u', id])
    const step = startHook({ messages: [msg('u')], scrollContainer: container })
    step({ messages: [msg('u')] }) // baseline
    step({ isActive: false })
    step({ isActive: true, messages: [msg('u'), msg(id, kind as ParsedMessage['kind'])] })
    await flushDoubleRaf()

    expect(scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('does not jump for non-important new messages', async () => {
    const { container, scrollIntoView } = makeContainer(['u', 'm2'])
    const step = startHook({ messages: [msg('u')], scrollContainer: container })
    step({ messages: [msg('u')] })
    step({ isActive: false })
    step({ isActive: true, messages: [msg('u'), msg('m2', 'text')] })
    await flushDoubleRaf()

    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('treats messages as all-new when last-seen id is no longer present', async () => {
    // Pre-record baseline "u", then come back with messages that no longer
    // include "u" (history truncation). The jump should fire on the first
    // important message it finds.
    const { container, scrollIntoView } = makeContainer(['u', 'final'])
    const step = startHook({ messages: [msg('u')], scrollContainer: container })
    step({ messages: [msg('u')] })
    step({ isActive: false })
    step({ isActive: true, messages: [msg('final', 'final-answer')] })
    await flushDoubleRaf()

    expect(scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('does not jump again on later message updates within the same active period', async () => {
    const { container, scrollIntoView } = makeContainer(['u', 'final', 'final2'])
    const step = startHook({ messages: [msg('u')], scrollContainer: container })
    step({ messages: [msg('u')] })
    step({ isActive: false })
    step({ isActive: true, messages: [msg('u'), msg('final', 'final-answer')] })
    await flushDoubleRaf()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)

    // Another final-answer arrives WITHOUT going back to background
    step({
      messages: [msg('u'), msg('final', 'final-answer'), msg('final2', 'final-answer')],
    })
    await flushDoubleRaf()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('REGRESSION: does not re-jump on subsequent re-entries when no new messages arrived (PR #575 review)', async () => {
    // Without advancing the baseline at jump time, a second re-entry with
    // no new messages would still see the same important message as "new"
    // (because the pointer-update effect is gated by `wasActive` and so
    // doesn't fire on the activation render itself), and would jump again.
    const { container, scrollIntoView } = makeContainer(['u', 'final'])
    const step = startHook({ messages: [msg('u')], scrollContainer: container })
    step({ messages: [msg('u')] }) // baseline = "u"
    step({ isActive: false })
    step({ isActive: true, messages: [msg('u'), msg('final', 'final-answer')] })
    await flushDoubleRaf()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)

    // Leave and return again with the SAME messages — no new important
    // message has arrived, so the hook must not jump a second time.
    step({ isActive: false })
    step({ isActive: true })
    await flushDoubleRaf()
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('is a no-op when sessionId is undefined', async () => {
    const { container, scrollIntoView } = makeContainer(['final'])
    startHook({
      sessionId: undefined,
      messages: [msg('final', 'final-answer')],
      scrollContainer: container,
    })
    await flushDoubleRaf()
    expect(scrollIntoView).not.toHaveBeenCalled()
  })
})
