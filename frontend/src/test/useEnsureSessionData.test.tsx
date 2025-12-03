/**
 * Tests for useEnsureSessionData.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useEnsureSessionData, _resetSyncedSessions } from '@/hooks/useEnsureSessionData'
import { useChatStore, resetStore } from '@/stores/chatStore'
import type { Message } from '@/types'
import type { Run } from '@/types/api'

// Mock useSessionRun so the hook gets deterministic data without React Query.
const mockRun = vi.fn<() => { data: Run | null; isLoading: boolean }>()
vi.mock('@/api/sessions', () => ({
  useSessionRun: () => mockRun(),
}))

const SESSION_ID = 1
const RUN_ID = 'run-1'

function makeMessage(id: number | undefined, content: string, source = 'orchestrator'): Message {
  return {
    id,
    session_id: SESSION_ID,
    run_id: RUN_ID,
    config: { source, content },
    created_at: new Date().toISOString(),
  }
}

function makeRun(messages: Message[], status: Run['status'] = 'active'): Run {
  return {
    id: RUN_ID,
    session_id: SESSION_ID,
    status,
    task: null,
    messages,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}

describe('useEnsureSessionData', () => {
  beforeEach(() => {
    resetStore()
    _resetSyncedSessions()
    mockRun.mockReset()
  })

  it('hydrates the store from the API on first mount when store is empty', () => {
    const apiMessages = [
      makeMessage(101, 'Task'),
      makeMessage(102, 'Working on it', 'orchestrator'),
    ]
    mockRun.mockReturnValue({ data: makeRun(apiMessages), isLoading: false })

    renderHook(() => useEnsureSessionData(SESSION_ID))

    const stored = useChatStore.getState().getSessionState(SESSION_ID).messages
    expect(stored).toHaveLength(2)
    expect(stored.map((m) => m.raw.id)).toEqual([101, 102])
  })

  it('preserves WS-streamed messages across remounts when API snapshot is stale', () => {
    mockRun.mockReturnValue({
      data: makeRun([makeMessage(101, 'Task', 'user')]),
      isLoading: false,
    })

    const first = renderHook(() => useEnsureSessionData(SESSION_ID))

    const store = useChatStore.getState()
    store.addMessage(SESSION_ID, makeMessage(undefined, 'Thinking...', 'orchestrator'))
    store.addMessage(SESSION_ID, makeMessage(undefined, 'Browsing', 'web_surfer'))

    expect(useChatStore.getState().getSessionState(SESSION_ID).messages).toHaveLength(3)

    first.unmount()
    renderHook(() => useEnsureSessionData(SESSION_ID))

    const stored = useChatStore.getState().getSessionState(SESSION_ID).messages
    expect(stored).toHaveLength(3)
    expect(stored.map((m) => m.raw.config.content)).toEqual(['Task', 'Thinking...', 'Browsing'])
  })

  it('does not drop WS-streamed messages when merging with a stale API snapshot', () => {
    mockRun.mockReturnValue({
      data: makeRun([makeMessage(101, 'Task', 'user')]),
      isLoading: false,
    })

    const store = useChatStore.getState()
    store.initSession(SESSION_ID, RUN_ID, 'active', null)
    store.addMessage(SESSION_ID, makeMessage(101, 'Task', 'user'))
    store.addMessage(SESSION_ID, makeMessage(undefined, 'Streamed', 'orchestrator'))
    _resetSyncedSessions()

    renderHook(() => useEnsureSessionData(SESSION_ID))

    const stored = useChatStore.getState().getSessionState(SESSION_ID).messages
    expect(stored).toHaveLength(2)
    expect(stored.map((m) => m.raw.config.content)).toEqual(['Task', 'Streamed'])
  })

  it('overwrites the store when API and store agree (no unsynced WS data)', () => {
    const store = useChatStore.getState()
    store.initSession(SESSION_ID, RUN_ID, 'complete', null)
    store.addMessage(SESSION_ID, makeMessage(101, 'Old text', 'user'))
    _resetSyncedSessions()

    mockRun.mockReturnValue({
      data: makeRun(
        [makeMessage(101, 'Task', 'user'), makeMessage(102, 'Done', 'orchestrator')],
        'complete'
      ),
      isLoading: false,
    })

    renderHook(() => useEnsureSessionData(SESSION_ID))

    const stored = useChatStore.getState().getSessionState(SESSION_ID).messages
    expect(stored).toHaveLength(2)
    expect(stored.map((m) => m.raw.config.content)).toEqual(['Task', 'Done'])
  })

  it('is a no-op when sessionId is undefined', () => {
    mockRun.mockReturnValue({ data: null, isLoading: false })
    renderHook(() => useEnsureSessionData(undefined))
    expect(useChatStore.getState().sessionStates.size).toBe(0)
  })

  it('keeps API-only messages when WS connected after the run started', () => {
    // WebSocket connects mid-run and only receives messages from that point on;
    // the store therefore has fewer messages than the persisted history in the
    // API snapshot. The merge must keep API history and add the WS-only tail.
    const store = useChatStore.getState()
    store.initSession(SESSION_ID, RUN_ID, 'active', null)
    store.addMessage(SESSION_ID, makeMessage(undefined, 'Late WS msg', 'web_surfer'))
    _resetSyncedSessions()

    mockRun.mockReturnValue({
      data: makeRun([
        makeMessage(101, 'Task', 'user'),
        makeMessage(102, 'Early agent step', 'orchestrator'),
      ]),
      isLoading: false,
    })

    renderHook(() => useEnsureSessionData(SESSION_ID))

    const stored = useChatStore.getState().getSessionState(SESSION_ID).messages
    expect(stored.map((m) => m.raw.config.content)).toEqual([
      'Task',
      'Early agent step',
      'Late WS msg',
    ])
  })

  it('re-parses store messages when agentMode changes, even with unsynced WS data', () => {
    const store = useChatStore.getState()
    store.initSession(SESSION_ID, RUN_ID, 'active', null)
    store.addMessage(SESSION_ID, makeMessage(undefined, 'Streamed', 'web_surfer'))
    expect(useChatStore.getState().getSessionState(SESSION_ID).agentMode).toBeNull()

    mockRun.mockReturnValue({
      data: {
        ...makeRun([makeMessage(101, 'Task', 'user')]),
        agent_mode: 'all',
      },
      isLoading: false,
    })

    renderHook(() => useEnsureSessionData(SESSION_ID))

    const next = useChatStore.getState().getSessionState(SESSION_ID)
    expect(next.agentMode).toBe('all')
    expect(next.messages.map((m) => m.raw.config.content)).toEqual(['Task', 'Streamed'])
  })
})
