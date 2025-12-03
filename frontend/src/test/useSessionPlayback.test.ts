/**
 * useSessionPlayback Hook Tests
 *
 * Tests the shared playback hook that reads from chatStore
 * and provides playback state + derived data for browser components.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useChatStore, resetStore } from '@/stores/chatStore'
import { useSessionPlayback } from '@/hooks/useSessionPlayback'
import type { Message } from '@/types'
import type { CuaAction } from '@/components/chat/messages'

// =============================================================================
// Test Helpers
// =============================================================================

const SESSION_ID = 1
const RUN_ID = 'run-1'

/** Create a raw browser-tool message (will be parsed by chatStore.setMessages) */
function createRawBrowserTool(
  id: number,
  tool: string = 'left_click',
  thoughts: string = 'thinking...'
): Message {
  return {
    id,
    session_id: SESSION_ID,
    run_id: RUN_ID,
    config: {
      source: 'web_surfer',
      content: [{ type: 'text', text: `Performing ${tool}` }],
      metadata: {
        type: 'tool_call',
        tool,
        tool_args: { thoughts },
      },
    },
    created_at: new Date().toISOString(),
  }
}

/** Create a raw screenshot message (will be parsed by chatStore.setMessages) */
function createRawScreenshot(id: number, actionResult?: string): Message {
  return {
    id,
    session_id: SESSION_ID,
    run_id: RUN_ID,
    config: {
      source: 'web_surfer',
      content: [
        { type: 'image', url: `data:image/png;base64,img${id}` },
        ...(actionResult ? [{ type: 'text' as const, text: actionResult }] : []),
      ],
      metadata: { type: 'browser_screenshot' },
    },
    created_at: new Date().toISOString(),
  }
}

/** Create a raw text message (will be parsed by chatStore.setMessages) */
function createRawTextMessage(id: number, source: string = 'orchestrator'): Message {
  return {
    id,
    session_id: SESSION_ID,
    run_id: RUN_ID,
    config: { source, content: 'some text response' },
    created_at: new Date().toISOString(),
  }
}

/** Set up a session with messages and optional novncUrl */
function setupSession(messages: Message[], novncUrl?: string) {
  const store = useChatStore.getState()
  store.initSession(SESSION_ID, RUN_ID)
  store.setMessages(SESSION_ID, messages)
  if (novncUrl) {
    store.setNovncUrl(SESSION_ID, novncUrl)
  }
}

// =============================================================================
// Tests
// =============================================================================

describe('useSessionPlayback', () => {
  beforeEach(() => {
    resetStore()
  })

  // ---------------------------------------------------------------------------
  // Default / Empty State
  // ---------------------------------------------------------------------------

  describe('default state', () => {
    it('returns empty state for undefined sessionId', () => {
      const { result } = renderHook(() => useSessionPlayback(undefined))

      expect(result.current.screenshotActions).toEqual([])
      expect(result.current.liveActionInfo).toBeUndefined()
      expect(result.current.playbackIsLive).toBe(true)
      expect(result.current.playbackIndex).toBe(0)
    })

    it('returns empty state for session with no messages', () => {
      useChatStore.getState().initSession(SESSION_ID, RUN_ID)
      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.screenshotActions).toEqual([])
      expect(result.current.liveActionInfo).toBeUndefined()
      expect(result.current.playbackIsLive).toBe(true)
      expect(result.current.playbackIndex).toBe(0)
    })
  })

  // ---------------------------------------------------------------------------
  // Screenshot Actions
  // ---------------------------------------------------------------------------

  describe('screenshotActions', () => {
    it('collects completed browser-tool + screenshot pairs', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'clicking button'),
        createRawScreenshot(2, 'Clicked button'),
        createRawBrowserTool(3, 'type', 'typing text'),
        createRawScreenshot(4, 'Typed text'),
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.screenshotActions).toHaveLength(2)
      expect(result.current.screenshotActions[0].tool).toBe('left_click')
      expect(result.current.screenshotActions[0].screenshotUrl).toContain('data:image/png')
      expect(result.current.screenshotActions[1].tool).toBe('type')
    })

    it('excludes browser-tool without screenshot', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'clicking'),
        createRawScreenshot(2),
        createRawBrowserTool(3, 'type', 'typing'), // no screenshot follows
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      // Only the first action has a screenshot
      expect(result.current.screenshotActions).toHaveLength(1)
      expect(result.current.screenshotActions[0].tool).toBe('left_click')
    })
  })

  // ---------------------------------------------------------------------------
  // liveActionInfo
  // ---------------------------------------------------------------------------

  describe('liveActionInfo', () => {
    it('returns undefined when no novncUrl', () => {
      setupSession([
        createRawBrowserTool(1, 'click', 'clicking'),
        createRawScreenshot(2, 'Clicked'),
      ])
      // No novncUrl set

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.liveActionInfo).toBeUndefined()
    })

    it('returns last completed action info when novncUrl is set', () => {
      setupSession(
        [
          createRawBrowserTool(1, 'left_click', 'clicking button'),
          createRawScreenshot(2, 'Clicked button'),
        ],
        'ws://localhost:6080'
      )

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.liveActionInfo).toBeDefined()
      expect(result.current.liveActionInfo?.thoughts).toBe('clicking button')
      expect(result.current.liveActionInfo?.actionResult).toBe('Clicked button')
    })

    it('returns pending action thoughts when action has no screenshot yet', () => {
      setupSession(
        [
          createRawBrowserTool(1, 'left_click', 'clicking button'),
          createRawScreenshot(2, 'Clicked'),
          createRawBrowserTool(3, 'type', 'typing into field'),
          // No screenshot for action 3 yet — it's pending
        ],
        'ws://localhost:6080'
      )

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.liveActionInfo).toBeDefined()
      expect(result.current.liveActionInfo?.thoughts).toBe('typing into field')
      expect(result.current.liveActionInfo?.actionResult).toBeUndefined()
    })

    it('returns undefined when there are messages after last CUA action', () => {
      setupSession(
        [
          createRawBrowserTool(1, 'left_click', 'clicking'),
          createRawScreenshot(2, 'Clicked'),
          createRawTextMessage(3, 'orchestrator'), // non-CUA message after
        ],
        'ws://localhost:6080'
      )

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.liveActionInfo).toBeUndefined()
    })
  })

  // ---------------------------------------------------------------------------
  // Playback Handlers
  // ---------------------------------------------------------------------------

  describe('onPlaybackIndexChange', () => {
    it('sets playback to history mode at given index', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'click 1'),
        createRawScreenshot(2),
        createRawBrowserTool(3, 'type', 'type 1'),
        createRawScreenshot(4),
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      act(() => {
        result.current.onPlaybackIndexChange(1)
      })

      // Should switch to history mode (not live) at index 1
      expect(result.current.playbackIsLive).toBe(false)
      expect(result.current.playbackIndex).toBe(1)
    })

    it('sets highlightedActionId to corresponding message', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'click 1'),
        createRawScreenshot(2),
        createRawBrowserTool(3, 'type', 'type 1'),
        createRawScreenshot(4),
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      act(() => {
        result.current.onPlaybackIndexChange(0)
      })

      const state = useChatStore.getState().getSessionState(SESSION_ID)
      expect(state.highlightedActionId).toBe(result.current.screenshotActions[0].messageId)
    })

    it('is no-op for undefined sessionId', () => {
      const { result } = renderHook(() => useSessionPlayback(undefined))

      act(() => {
        result.current.onPlaybackIndexChange(0)
      })

      // Should not throw
      expect(result.current.playbackIsLive).toBe(true)
    })
  })

  describe('onSetLive', () => {
    it('switches to history mode when called with false', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'click'),
        createRawScreenshot(2),
        createRawBrowserTool(3, 'type', 'type'),
        createRawScreenshot(4),
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      // Initially live
      expect(result.current.playbackIsLive).toBe(true)

      // Set to history
      act(() => {
        result.current.onSetLive(false)
      })

      expect(result.current.playbackIsLive).toBe(false)
      expect(result.current.playbackIndex).toBe(1) // last index (2 actions, 0-based)
    })

    it('switches to live mode when called with true', () => {
      setupSession([createRawBrowserTool(1, 'left_click', 'click'), createRawScreenshot(2)])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      // First switch to history
      act(() => {
        result.current.onSetLive(false)
      })
      expect(result.current.playbackIsLive).toBe(false)

      // Switch to live
      act(() => {
        result.current.onSetLive(true)
      })

      expect(result.current.playbackIsLive).toBe(true)
      expect(result.current.playbackIndex).toBe(0)
    })

    it('clears highlightedActionId when going live', () => {
      setupSession([createRawBrowserTool(1, 'left_click', 'click'), createRawScreenshot(2)])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      // Select an action first
      act(() => {
        result.current.onPlaybackIndexChange(0)
      })

      const stateBefore = useChatStore.getState().getSessionState(SESSION_ID)
      expect(stateBefore.highlightedActionId).not.toBeNull()

      // Go live → should clear highlight
      act(() => {
        result.current.onSetLive(true)
      })

      const stateAfter = useChatStore.getState().getSessionState(SESSION_ID)
      expect(stateAfter.highlightedActionId).toBeNull()
    })

    it('is no-op for undefined sessionId', () => {
      const { result } = renderHook(() => useSessionPlayback(undefined))

      act(() => {
        result.current.onSetLive(false)
      })

      // Should not throw
      expect(result.current.playbackIsLive).toBe(true)
    })
  })

  // ---------------------------------------------------------------------------
  // onCuaActionClick
  // ---------------------------------------------------------------------------

  describe('onCuaActionClick', () => {
    it('jumps to the correct screenshot index and highlights action', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'click 1'),
        createRawScreenshot(2, 'Clicked 1'),
        createRawBrowserTool(3, 'type', 'type 1'),
        createRawScreenshot(4, 'Typed 1'),
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))
      const secondAction = result.current.screenshotActions[1]

      act(() => {
        result.current.onCuaActionClick(secondAction)
      })

      expect(result.current.playbackIsLive).toBe(false)
      expect(result.current.playbackIndex).toBe(1)

      const state = useChatStore.getState().getSessionState(SESSION_ID)
      expect(state.highlightedActionId).toBe(secondAction.messageId)
    })

    it('is no-op when action is not found in completedActions', () => {
      setupSession([
        createRawBrowserTool(1, 'left_click', 'click 1'),
        createRawScreenshot(2, 'Clicked 1'),
      ])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      act(() => {
        result.current.onCuaActionClick({
          messageId: 'nonexistent',
          tool: 'left_click',
          isComplete: true,
        } as CuaAction)
      })

      // Should remain in live mode (no change)
      expect(result.current.playbackIsLive).toBe(true)
    })

    it('is no-op for undefined sessionId', () => {
      const { result } = renderHook(() => useSessionPlayback(undefined))

      act(() => {
        result.current.onCuaActionClick({
          messageId: 'test',
          tool: 'left_click',
          isComplete: true,
        } as CuaAction)
      })

      // Should not throw
      expect(result.current.playbackIsLive).toBe(true)
    })
  })

  // ---------------------------------------------------------------------------
  // Reactivity
  // ---------------------------------------------------------------------------

  describe('reactivity', () => {
    it('updates when messages are added to store', () => {
      useChatStore.getState().initSession(SESSION_ID, RUN_ID)

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.screenshotActions).toHaveLength(0)

      // Add messages
      act(() => {
        useChatStore
          .getState()
          .addMessage(SESSION_ID, createRawBrowserTool(1, 'left_click', 'click'))
      })
      act(() => {
        useChatStore.getState().addMessage(SESSION_ID, createRawScreenshot(2, 'Clicked'))
      })

      expect(result.current.screenshotActions).toHaveLength(1)
    })

    it('updates when playback state changes externally', () => {
      setupSession([createRawBrowserTool(1, 'left_click', 'click'), createRawScreenshot(2)])

      const { result } = renderHook(() => useSessionPlayback(SESSION_ID))

      expect(result.current.playbackIsLive).toBe(true)

      // External state change (e.g., from SessionView's handleCuaActionClick)
      act(() => {
        useChatStore.getState().setPlaybackState(SESSION_ID, false, 0, false)
      })

      expect(result.current.playbackIsLive).toBe(false)
      expect(result.current.playbackIndex).toBe(0)
    })
  })
})
