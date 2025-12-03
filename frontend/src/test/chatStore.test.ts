/**
 * Chat Store Tests
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useChatStore, resetStore, useSessionAgentMode, useIsCuaActive } from '@/stores/chatStore'
import { initialSessionChatState } from '@/types'
import type { Message, InputRequest, FileInfo } from '@/types'

// Helper to create mock messages
function createMockMessage(overrides?: Partial<Message>): Message {
  return {
    id: 1,
    session_id: 1,
    run_id: 'run-1',
    config: { source: 'user', content: 'Hello' },
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('chatStore', () => {
  beforeEach(() => {
    resetStore()
  })

  it('maintains separate state for different sessions', () => {
    const store = useChatStore.getState()

    // Initialize two sessions
    store.initSession(1, 'run-1')
    store.initSession(2, 'run-2')

    // Add message to session 1
    store.addMessage(1, createMockMessage({ id: 101, session_id: 1 }))
    store.setServerStatus(1, 'active')

    // Add different message to session 2
    store.addMessage(2, createMockMessage({ id: 201, session_id: 2 }))
    store.setServerStatus(2, 'awaiting_input')

    // Verify states are independent
    const state1 = store.getSessionState(1)
    const state2 = store.getSessionState(2)

    expect(state1.messages).toHaveLength(1)
    expect(state1.messages[0].id).toBe('101') // ParsedMessage.id is string
    expect(state1.serverStatus).toBe('active')

    expect(state2.messages).toHaveLength(1)
    expect(state2.messages[0].id).toBe('201') // ParsedMessage.id is string
    expect(state2.serverStatus).toBe('awaiting_input')
  })

  describe('getSessionState', () => {
    it('returns initial state for non-existent session', () => {
      const state = useChatStore.getState().getSessionState(999)
      expect(state).toEqual(initialSessionChatState)
    })

    it('returns stored state for existing session', () => {
      useChatStore.getState().initSession(1, 'run-1')
      const state = useChatStore.getState().getSessionState(1)
      expect(state.runId).toBe('run-1')
    })
  })

  describe('initSession', () => {
    it('creates new session state with runId', () => {
      useChatStore.getState().initSession(1, 'run-abc')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.runId).toBe('run-abc')
      expect(state.serverStatus).toBe('created')
      expect(state.messages).toEqual([])
    })

    it('reinitializes when runId changes', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(1, createMockMessage())

      // Reinitialize with different runId
      useChatStore.getState().initSession(1, 'run-2')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.runId).toBe('run-2')
      expect(state.messages).toEqual([]) // Messages cleared
    })

    it('does not reinitialize when runId is the same', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(1, createMockMessage())

      // Call init again with same runId
      useChatStore.getState().initSession(1, 'run-1')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(1) // Messages preserved
    })
  })

  describe('clearSession', () => {
    it('removes session state', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().clearSession(1)

      const state = useChatStore.getState().getSessionState(1)
      expect(state).toEqual(initialSessionChatState)
    })
  })

  describe('setServerStatus', () => {
    it('updates server status', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setServerStatus(1, 'active')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.serverStatus).toBe('active')
    })

    it('clears pending action when status matches expected', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setPendingAction(1, { type: 'pausing', timestamp: Date.now() })

      // Server confirms stopped
      useChatStore.getState().setServerStatus(1, 'stopped')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.pendingAction).toBeNull()
    })

    it('keeps pending action when status does not match', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setPendingAction(1, { type: 'pausing', timestamp: Date.now() })

      // Server reports active (not stopped yet)
      useChatStore.getState().setServerStatus(1, 'active')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.pendingAction).not.toBeNull()
    })
  })

  describe('addMessage', () => {
    it('appends message to session (parsed)', () => {
      useChatStore.getState().initSession(1)
      const msg1 = createMockMessage({ id: 1 })
      const msg2 = createMockMessage({ id: 2 })

      useChatStore.getState().addMessage(1, msg1)
      useChatStore.getState().addMessage(1, msg2)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(2)
      // Messages are now ParsedMessage, check by id (string) and kind
      expect(state.messages[0].id).toBe('1')
      expect(state.messages[0].kind).toBe('user')
      expect(state.messages[1].id).toBe('2')
    })

    it('creates session state if not exists', () => {
      const msg = createMockMessage()
      useChatStore.getState().addMessage(999, msg)

      const state = useChatStore.getState().getSessionState(999)
      expect(state.messages).toHaveLength(1)
    })
  })

  describe('setMessages', () => {
    it('replaces all messages (parsed)', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().addMessage(1, createMockMessage({ id: 1 }))

      const newMessages = [createMockMessage({ id: 10 }), createMockMessage({ id: 11 })]
      useChatStore.getState().setMessages(1, newMessages)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(2)
      expect(state.messages[0].id).toBe('10') // ParsedMessage.id is string
    })

    it('persists agentMode passed to setMessages', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setMessages(1, [], 'all')

      expect(useChatStore.getState().getSessionState(1).agentMode).toBe('all')
    })

    it('uses agentMode to demote a CUA final_answer that arrives before any OmniAgent message', () => {
      // Reproduces session 279 streaming bug: CUA's final_answer was the first
      // message classified, so without the persisted agent_mode the parser
      // would promote it to a real final-answer. With agent_mode='all'
      // initialized on the session, it stays internal.
      useChatStore.getState().initSession(1, 'run-1', undefined, 'all')

      const cuaFinalAnswer = createMockMessage({
        id: 100,
        config: {
          source: 'web_surfer',
          content: [{ type: 'text', text: 'CUA hand-off' }],
          metadata: { type: 'final_answer' },
        },
      })

      useChatStore.getState().addMessage(1, cuaFinalAnswer)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(1)
      expect(state.messages[0].kind).toBe('internal')
    })
  })

  describe('replaceOptimisticUserMessage', () => {
    it('replaces optimistic message with backend version', () => {
      useChatStore.getState().initSession(1)
      // Add an optimistic user message (has _optimistic marker)
      useChatStore.getState().addMessage(
        1,
        createMockMessage({
          id: -1000001,
          config: {
            source: 'user',
            content: 'Hello',
            metadata: { _optimistic: true },
          },
        })
      )
      expect(useChatStore.getState().getSessionState(1).messages).toHaveLength(1)
      expect(useChatStore.getState().getSessionState(1).messages[0].kind).toBe('user')

      // Replace with backend version
      useChatStore.getState().replaceOptimisticUserMessage(
        1,
        createMockMessage({
          id: 100,
          config: {
            source: 'user',
            content: 'Hello',
            metadata: { attached_files: '[]' },
          },
        })
      )

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(1)
      expect(state.messages[0].id).toBe('100') // Replaced with backend ID
    })

    it('appends if no optimistic message found', () => {
      useChatStore.getState().initSession(1)
      // Add a normal (non-optimistic) user message
      useChatStore.getState().addMessage(1, createMockMessage({ id: 1 }))

      // Try to replace — no optimistic found, appends instead
      useChatStore
        .getState()
        .replaceOptimisticUserMessage(
          1,
          createMockMessage({ id: 200, config: { source: 'user', content: 'New' } })
        )

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(2)
    })

    it('preserves mountedFolder from optimistic message when backend omits it', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().addMessage(
        1,
        createMockMessage({
          id: -1000001,
          config: {
            source: 'user',
            content: 'Hello',
            metadata: {
              _optimistic: true,
              mounted_folder: { name: 'repo', path: '/Users/weilishi/Code/magentic-ui2.0' },
            },
          },
        })
      )

      useChatStore.getState().replaceOptimisticUserMessage(
        1,
        createMockMessage({
          id: 101,
          config: {
            source: 'user',
            content: 'Hello',
            metadata: { attached_files: '[]' },
          },
        })
      )

      const msg = useChatStore.getState().getSessionState(1).messages[0]
      expect(msg.kind).toBe('user')
      if (msg.kind === 'user') {
        expect(msg.mountedFolder).toEqual({
          name: 'repo',
          path: '/Users/weilishi/Code/magentic-ui2.0',
        })
      }
    })
  })

  describe('updateOptimisticFileStatus', () => {
    it('updates file status on optimistic message', () => {
      useChatStore.getState().initSession(1)
      const filesJson = JSON.stringify([{ name: 'test.txt', url: '', uploadStatus: 'uploading' }])
      useChatStore.getState().addMessage(
        1,
        createMockMessage({
          id: -1000001,
          config: {
            source: 'user',
            content: 'Check this file',
            metadata: { _optimistic: true, attached_files: filesJson },
          },
        })
      )

      useChatStore.getState().updateOptimisticFileStatus(1, 'uploaded')

      const msg = useChatStore.getState().getSessionState(1).messages[0]
      if (msg.kind === 'user' && msg.attachedFiles) {
        expect(msg.attachedFiles[0].uploadStatus).toBe('uploaded')
      }
    })

    it('sets error status on upload failure', () => {
      useChatStore.getState().initSession(1)
      const filesJson = JSON.stringify([{ name: 'big.zip', url: '', uploadStatus: 'uploading' }])
      useChatStore.getState().addMessage(
        1,
        createMockMessage({
          id: -1000001,
          config: {
            source: 'user',
            content: 'Upload this',
            metadata: { _optimistic: true, attached_files: filesJson },
          },
        })
      )

      useChatStore.getState().updateOptimisticFileStatus(1, 'error')

      const msg = useChatStore.getState().getSessionState(1).messages[0]
      if (msg.kind === 'user' && msg.attachedFiles) {
        expect(msg.attachedFiles[0].uploadStatus).toBe('error')
      }
    })

    it('no-op if no optimistic message', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().addMessage(1, createMockMessage({ id: 1 }))

      // Should not throw
      useChatStore.getState().updateOptimisticFileStatus(1, 'error')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.messages).toHaveLength(1)
    })
  })

  describe('setInputRequest', () => {
    it('sets input request', () => {
      useChatStore.getState().initSession(1)
      const request: InputRequest = { input_type: 'approval', content: 'Approve?' }

      useChatStore.getState().setInputRequest(1, request)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.inputRequest).toEqual(request)
    })

    it('clears input request with null', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setInputRequest(1, { input_type: 'text_input' })
      useChatStore.getState().setInputRequest(1, null)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.inputRequest).toBeNull()
    })
  })

  describe('setConnectionStatus', () => {
    it('updates connection status', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setConnectionStatus(1, 'connected')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.connectionStatus).toBe('connected')
    })
  })

  describe('setPendingAction', () => {
    it('sets pending action', () => {
      useChatStore.getState().initSession(1)
      const action = { type: 'pausing' as const, timestamp: Date.now() }

      useChatStore.getState().setPendingAction(1, action)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.pendingAction).toEqual(action)
    })
  })

  describe('getSessionStatus', () => {
    it('ignores pending action - returns server status (no optimistic UI)', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setServerStatus(1, 'active')
      useChatStore.getState().setPendingAction(1, { type: 'pausing', timestamp: Date.now() })

      const status = useChatStore.getState().getSessionStatus(1)
      expect(status).toBe('active') // Server status, not optimistic
    })

    it('returns server status when reconnecting (preserves awaiting-input)', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setServerStatus(1, 'awaiting_input')
      useChatStore.getState().setConnectionStatus(1, 'reconnecting')

      const status = useChatStore.getState().getSessionStatus(1)
      expect(status).toBe('awaiting-input') // Preserves server status during reconnect
    })

    it('returns active when connecting with no server status', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setConnectionStatus(1, 'connecting')

      const status = useChatStore.getState().getSessionStatus(1)
      expect(status).toBe('active') // Optimistic: assume connection will succeed
    })

    it('returns mapped session status when no pending action or connection issue', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setServerStatus(1, 'awaiting_input')
      useChatStore.getState().setConnectionStatus(1, 'connected')

      const status = useChatStore.getState().getSessionStatus(1)
      expect(status).toBe('awaiting-input') // Mapped from awaiting_input
    })

    it('returns paused when server status is paused', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setServerStatus(1, 'paused')
      useChatStore.getState().setConnectionStatus(1, 'connected')

      const status = useChatStore.getState().getSessionStatus(1)
      expect(status).toBe('paused')
    })

    it('returns created for non-existent session', () => {
      const status = useChatStore.getState().getSessionStatus(999)
      expect(status).toBe('created') // Safe default
    })
  })

  describe('setNovncUrl', () => {
    it('sets novnc url', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setNovncUrl(1, 'ws://localhost:58581/websockify')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.novncUrl).toBe('ws://localhost:58581/websockify')
    })

    it('clears novnc url with null', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setNovncUrl(1, 'ws://localhost:58581/websockify')
      useChatStore.getState().setNovncUrl(1, null)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.novncUrl).toBeNull()
    })
  })

  describe('setBrowserViewMode', () => {
    it('sets browser view mode', () => {
      useChatStore.getState().initSession(1)
      useChatStore.getState().setBrowserViewMode(1, 'expanded')

      const state = useChatStore.getState().getSessionState(1)
      expect(state.browserViewMode).toBe('expanded')
    })

    it('defaults to embedded mode', () => {
      useChatStore.getState().initSession(1)

      const state = useChatStore.getState().getSessionState(1)
      expect(state.browserViewMode).toBe('embedded')
    })
  })

  describe('previewFile auto-update', () => {
    it('updates previewFile when a file message arrives with matching file', () => {
      const store = useChatStore.getState()
      store.initSession(1, 'run-1')

      // Set initial previewFile
      const initialFile: FileInfo = {
        name: 'report.md',
        url: '/files/user/guest/1/1/report.md',
        timestamp: 100,
        extension: 'md',
        file_type: 'text',
        action: 'created',
      }
      store.setPreviewFile(1, initialFile)

      // Add a file message with updated timestamp for same file
      store.addMessage(
        1,
        createMockMessage({
          id: 10,
          config: {
            source: 'system',
            content: 'File Generated',
            metadata: {
              type: 'file',
              files: JSON.stringify([
                {
                  name: 'report.md',
                  url: '/files/user/guest/1/1/report.md',
                  timestamp: 200,
                  extension: 'md',
                  file_type: 'text',
                  action: 'modified',
                },
              ]),
            },
          },
        })
      )

      const state = store.getSessionState(1)
      expect(state.previewFile).not.toBeNull()
      expect(state.previewFile!.timestamp).toBe(200)
      expect(state.previewFile!.action).toBe('modified')
    })

    it('does not update previewFile when file message has no matching file', () => {
      const store = useChatStore.getState()
      store.initSession(1, 'run-1')

      const initialFile: FileInfo = {
        name: 'report.md',
        url: '/files/user/guest/1/1/report.md',
        timestamp: 100,
        extension: 'md',
        file_type: 'text',
        action: 'created',
      }
      store.setPreviewFile(1, initialFile)

      // Add a file message for a different file
      store.addMessage(
        1,
        createMockMessage({
          id: 11,
          config: {
            source: 'system',
            content: 'File Generated',
            metadata: {
              type: 'file',
              files: JSON.stringify([
                {
                  name: 'other.py',
                  url: '/files/user/guest/1/1/other.py',
                  timestamp: 200,
                  extension: 'py',
                  file_type: 'code',
                  action: 'created',
                },
              ]),
            },
          },
        })
      )

      const state = store.getSessionState(1)
      expect(state.previewFile!.timestamp).toBe(100) // unchanged
    })
  })

  // ---------------------------------------------------------------------------
  // Folder Mounting
  // ---------------------------------------------------------------------------

  describe('setMountedFolder', () => {
    it('sets mounted folder for a session', () => {
      const store = useChatStore.getState()
      store.initSession(1, 'run-1')

      store.setMountedFolder(1, { name: 'my-project', path: 'my-project' })

      const state = store.getSessionState(1)
      expect(state.mountedFolder).toEqual({ name: 'my-project', path: 'my-project' })
    })

    it('clears mounted folder when set to null', () => {
      const store = useChatStore.getState()
      store.initSession(1, 'run-1')

      store.setMountedFolder(1, { name: 'my-project', path: 'my-project' })
      store.setMountedFolder(1, null)

      const state = store.getSessionState(1)
      expect(state.mountedFolder).toBeNull()
    })

    it('isolates mounted folder between sessions', () => {
      const store = useChatStore.getState()
      store.initSession(1, 'run-1')
      store.initSession(2, 'run-2')

      store.setMountedFolder(1, { name: 'project-a', path: 'project-a' })

      expect(store.getSessionState(1).mountedFolder?.name).toBe('project-a')
      expect(store.getSessionState(2).mountedFolder).toBeNull()
    })

    it('defaults to null for new sessions', () => {
      const store = useChatStore.getState()
      store.initSession(1, 'run-1')

      expect(store.getSessionState(1).mountedFolder).toBeNull()
    })
  })

  // ---------------------------------------------------------------------------
  // useSessionAgentMode (issue #626)
  // ---------------------------------------------------------------------------

  describe('useSessionAgentMode', () => {
    it('returns null when sessionId is undefined', () => {
      const { result } = renderHook(() => useSessionAgentMode(undefined))
      expect(result.current).toBeNull()
    })

    it('returns null for an unknown session', () => {
      const { result } = renderHook(() => useSessionAgentMode(999))
      expect(result.current).toBeNull()
    })

    it('returns the persisted agent mode after initSession', () => {
      useChatStore.getState().initSession(1, 'run-1', undefined, 'websurfer_only')

      const { result } = renderHook(() => useSessionAgentMode(1))
      expect(result.current).toBe('websurfer_only')
    })

    it('reflects each session in isolation', () => {
      useChatStore.getState().initSession(1, 'run-1', undefined, 'all')
      useChatStore.getState().initSession(2, 'run-2', undefined, 'websurfer_only')

      const { result: r1 } = renderHook(() => useSessionAgentMode(1))
      const { result: r2 } = renderHook(() => useSessionAgentMode(2))
      expect(r1.current).toBe('all')
      expect(r2.current).toBe('websurfer_only')
    })
  })

  // ---------------------------------------------------------------------------
  // useIsCuaActive (issue #626)
  // ---------------------------------------------------------------------------

  describe('useIsCuaActive', () => {
    /** Build a `tool_call` message that parses to an orchestrator-tool. */
    function createOrchestratorToolCall(id: number, tool: string, toolCallId: string): Message {
      return createMockMessage({
        id,
        config: {
          source: 'OmniAgent',
          content: [{ type: 'text', text: `Calling ${tool}` }],
          metadata: {
            type: 'tool_call',
            tool,
            tool_call_id: toolCallId,
            tool_args: {},
          },
        },
      })
    }

    /** Build a `tool_result` message that parses to a tool-result. */
    function createOrchestratorToolResult(id: number, tool: string, toolCallId: string): Message {
      return createMockMessage({
        id,
        config: {
          source: 'OmniAgent',
          content: [{ type: 'text', text: `Result of ${tool}` }],
          metadata: { type: 'tool_result', tool, tool_call_id: toolCallId },
        },
      })
    }

    it('returns false when sessionId is undefined', () => {
      const { result } = renderHook(() => useIsCuaActive(undefined))
      expect(result.current).toBe(false)
    })

    it('returns false for a session with no messages', () => {
      useChatStore.getState().initSession(1, 'run-1')
      const { result } = renderHook(() => useIsCuaActive(1))
      expect(result.current).toBe(false)
    })

    it('returns true while a delegate_cua call has no matching tool_result', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(1, createOrchestratorToolCall(10, 'delegate_cua', 'tc-1'))

      const { result } = renderHook(() => useIsCuaActive(1))
      expect(result.current).toBe(true)
    })

    it('returns false once the matching delegate_cua tool_result arrives', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(1, createOrchestratorToolCall(10, 'delegate_cua', 'tc-1'))
      useChatStore
        .getState()
        .addMessage(1, createOrchestratorToolResult(11, 'delegate_cua', 'tc-1'))

      const { result } = renderHook(() => useIsCuaActive(1))
      expect(result.current).toBe(false)
    })

    it('returns true when one delegate_cua is open even if a previous one was resolved', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(1, createOrchestratorToolCall(10, 'delegate_cua', 'tc-1'))
      useChatStore
        .getState()
        .addMessage(1, createOrchestratorToolResult(11, 'delegate_cua', 'tc-1'))
      useChatStore.getState().addMessage(1, createOrchestratorToolCall(12, 'delegate_cua', 'tc-2'))

      const { result } = renderHook(() => useIsCuaActive(1))
      expect(result.current).toBe(true)
    })

    it('ignores other in-flight orchestrator tools (e.g. bash)', () => {
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(1, createOrchestratorToolCall(10, 'bash', 'tc-1'))

      const { result } = renderHook(() => useIsCuaActive(1))
      expect(result.current).toBe(false)
    })

    it('does not count delegate_cua calls that lack a tool_call_id', () => {
      // Without a toolCallId we cannot pair call ↔ result, so we conservatively
      // treat the call as not-in-flight (avoids hiding the upload UI forever
      // when older messages are missing the id).
      useChatStore.getState().initSession(1, 'run-1')
      useChatStore.getState().addMessage(
        1,
        createMockMessage({
          id: 10,
          config: {
            source: 'OmniAgent',
            content: [{ type: 'text', text: 'Delegating' }],
            metadata: { type: 'tool_call', tool: 'delegate_cua', tool_args: {} },
          },
        })
      )

      const { result } = renderHook(() => useIsCuaActive(1))
      expect(result.current).toBe(false)
    })
  })
})
