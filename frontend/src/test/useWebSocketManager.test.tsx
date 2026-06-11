/**
 * WebSocket Manager Tests
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WebSocketManagerProvider, useWebSocketManager } from '@/hooks/useWebSocketManager'
import { sessionKeys } from '@/api/sessions'
import { useChatStore, resetStore } from '@/stores/chatStore'
import { useNotificationStore } from '@/stores/notificationStore'
import type { ReactNode } from 'react'
import type { ActiveRun } from '@/types'

// Mock WebSocket - use module-level variables instead of static properties
// (static properties not allowed with erasableSyntaxOnly)
let mockWsInstances: MockWebSocket[] = []
const WS_OPEN = 1

class MockWebSocket {
  // Static readyState constants matching the real WebSocket interface so
  // production code that checks `WebSocket.OPEN` works against the stub.
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  readyState = WS_OPEN
  url: string

  constructor(url: string) {
    this.url = url
    mockWsInstances.push(this)
    // Auto-open after construction (simulate immediate connection)
    setTimeout(() => this.simulateOpen(), 0)
  }

  send = vi.fn()
  close = vi.fn()

  // Helper to simulate receiving a message
  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) })
    }
  }

  // Helper to simulate connection open
  simulateOpen() {
    this.readyState = WS_OPEN
    if (this.onopen) {
      this.onopen()
    }
  }
}

// Replace global WebSocket with mock
vi.stubGlobal('WebSocket', MockWebSocket)

describe('useWebSocketManager query invalidation', () => {
  let queryClient: QueryClient
  let invalidateQueriesSpy: ReturnType<typeof vi.spyOn>

  // Active run with 'active' status (required for WebSocket connection)
  const activeRun: ActiveRun = {
    sessionId: 1,
    runId: 'run-1',
    sessionName: 'Test Session',
    status: 'active', // Must be in ACTIVE_RUN_STATUSES for connection
  }

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <WebSocketManagerProvider activeRuns={[activeRun]} selectedSessionId={1}>
        {children}
      </WebSocketManagerProvider>
    </QueryClientProvider>
  )

  beforeEach(() => {
    // Reset stores
    resetStore()
    useNotificationStore.getState().clearAll()

    // Create fresh QueryClient
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    // Spy on invalidateQueries
    invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')

    // Clear mock WebSocket instances
    mockWsInstances = []

    // Initialize session in store
    useChatStore.getState().initSession(1, 'run-1')
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  // Must use sessionKeys.lists() not runs(sessionId), otherwise Sidebar won't update
  describe('invalidates sessions list (not just runs) on status changes', () => {
    it('does NOT invalidate sessions list on input_request message (status comes from system)', async () => {
      renderHook(() => useWebSocketManager(), { wrapper })

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })

      const ws = mockWsInstances[0]
      ws.simulateOpen()

      // Simulate receiving input_request
      act(() => {
        ws.simulateMessage({
          type: 'input_request',
          input_type: 'text',
          content: 'Enter your response',
        })
      })

      // Verify: input_request no longer invalidates queries (status update is in system message)
      expect(invalidateQueriesSpy).not.toHaveBeenCalled()
    })

    it('updates sessions list cache directly on system complete status', async () => {
      const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData')
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })

      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'system',
          status: 'complete',
          content: 'Task completed',
        })
      })

      // Should use setQueryData instead of invalidateQueries for terminal states
      // This directly updates the cache without a refetch
      expect(setQueryDataSpy).toHaveBeenCalled()
      expect(invalidateQueriesSpy).not.toHaveBeenCalledWith({
        queryKey: sessionKeys.lists(),
      })
    })

    it('invalidates sessions list on system active status', async () => {
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })

      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'system',
          status: 'active',
        })
      })

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: sessionKeys.lists(),
      })
      expect(invalidateQueriesSpy).not.toHaveBeenCalledWith({
        queryKey: sessionKeys.runs(1),
      })
    })

    it('updates sessions list cache directly on system error status', async () => {
      const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData')
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })

      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'system',
          status: 'error',
          content: 'Something went wrong',
        })
      })

      // Should use setQueryData for terminal states
      expect(setQueryDataSpy).toHaveBeenCalled()
      expect(invalidateQueriesSpy).not.toHaveBeenCalledWith({
        queryKey: sessionKeys.lists(),
      })
    })

    it('updates sessions list cache directly on system stopped status', async () => {
      const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData')
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })

      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'system',
          status: 'stopped',
          content: 'Stopped by user',
        })
      })

      // Should use setQueryData for terminal states
      expect(setQueryDataSpy).toHaveBeenCalled()
      expect(invalidateQueriesSpy).not.toHaveBeenCalledWith({
        queryKey: sessionKeys.lists(),
      })
    })
  })

  // ===========================================================================
  // agent_state: transient "Waiting for model" / "Thinking" signal
  // ===========================================================================
  describe('agent_state messages', () => {
    it('updates agentActivity in the chat store on agent_state messages', async () => {
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })
      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'agent_state',
          state: 'calling_model',
          source: 'omni_agent',
        })
      })
      expect(useChatStore.getState().getSessionState(1).agentActivity).toBe('calling_model')

      act(() => {
        ws.simulateMessage({
          type: 'agent_state',
          state: 'generating',
          source: 'omni_agent',
        })
      })
      expect(useChatStore.getState().getSessionState(1).agentActivity).toBe('generating')
    })

    it('clears agentActivity when a terminal system status arrives', async () => {
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })
      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'agent_state',
          state: 'generating',
          source: 'omni_agent',
        })
      })
      expect(useChatStore.getState().getSessionState(1).agentActivity).toBe('generating')

      act(() => {
        ws.simulateMessage({
          type: 'system',
          status: 'complete',
        })
      })
      expect(useChatStore.getState().getSessionState(1).agentActivity).toBeNull()
    })

    it('clears agentActivity when the run pauses (non-active status)', async () => {
      renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })
      const ws = mockWsInstances[0]
      ws.simulateOpen()

      act(() => {
        ws.simulateMessage({
          type: 'agent_state',
          state: 'generating',
          source: 'omni_agent',
        })
      })
      expect(useChatStore.getState().getSessionState(1).agentActivity).toBe('generating')

      // Take Control pauses the run; the agent is no longer calling the
      // model, so the transient indicator must clear even though 'paused'
      // is not a terminal status.
      act(() => {
        ws.simulateMessage({
          type: 'system',
          status: 'paused',
        })
      })
      expect(useChatStore.getState().getSessionState(1).agentActivity).toBeNull()
    })
  })

  // ===========================================================================
  // sendInputResponse: mid-session file uploads (issue #291)
  // ===========================================================================
  describe('sendInputResponse', () => {
    it('omits files key when no files passed (back-compat)', async () => {
      const { result } = renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })
      const ws = mockWsInstances[0]
      ws.simulateOpen()

      await act(async () => {
        await result.current.sendInputResponse('run-1', 1, 'plain text')
      })

      expect(ws.send).toHaveBeenCalled()
      const sent = JSON.parse(ws.send.mock.calls[0][0] as string)
      expect(sent).toEqual({
        type: 'input_response',
        response: 'plain text',
      })
      expect(sent).not.toHaveProperty('files')
    })

    it('includes files in payload when provided', async () => {
      const { result } = renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })
      const ws = mockWsInstances[0]
      ws.simulateOpen()

      const files = [
        { name: 'data.csv', path: 'files/user/u1/s1/run-1/data.csv', uploaded: true as const },
      ]
      await act(async () => {
        await result.current.sendInputResponse('run-1', 1, 'use this', files)
      })

      const sent = JSON.parse(ws.send.mock.calls[0][0] as string)
      expect(sent).toEqual({
        type: 'input_response',
        response: 'use this',
        files,
      })
    })

    it('omits files key when an empty array is passed', async () => {
      const { result } = renderHook(() => useWebSocketManager(), { wrapper })

      await waitFor(() => {
        expect(mockWsInstances.length).toBeGreaterThan(0)
      })
      const ws = mockWsInstances[0]
      ws.simulateOpen()

      await act(async () => {
        await result.current.sendInputResponse('run-1', 1, 'hi', [])
      })

      const sent = JSON.parse(ws.send.mock.calls[0][0] as string)
      expect(sent).not.toHaveProperty('files')
    })
  })
})
