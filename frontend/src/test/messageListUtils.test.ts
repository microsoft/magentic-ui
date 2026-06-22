/**
 * Tests for messageListUtils
 *
 * Tests cover:
 * - shouldMerge: code-execution + tool-result pairing
 * - shouldMergeOrchestratorTool: orchestrator-tool + tool-result pairing
 * - computeRenderItems: message grouping and browser embed insertion
 * - shouldHideStatusIndicator: session status indicator visibility
 */

import { describe, it, expect } from 'vitest'
import {
  shouldMerge,
  shouldMergeOrchestratorTool,
  computeRenderItems,
  insertTimestampSeparators,
  shouldHideStatusIndicator,
  type RenderItem,
} from '@/components/chat/messageListUtils'
import { isCuaBrowserMessage, type ParsedMessage } from '@/types'
import type { Message } from '@/types/api'

// =============================================================================
// Test Helpers
// =============================================================================

/** Create a minimal raw Message for testing */
function createRawMessage(id: number = 1): Message {
  return {
    id,
    session_id: 1,
    run_id: 'run-1',
    config: {
      source: 'test',
      content: 'test content',
    },
    created_at: '2025-01-01T00:00:00Z',
  }
}

/** Create a text message */
function createTextMessage(id: string, content: string = 'test'): ParsedMessage {
  return {
    kind: 'text',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'orchestrator',
    content,
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create a user message */
function createUserMessage(id: string, content: string = 'user message'): ParsedMessage {
  return {
    kind: 'user',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'user',
    content,
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create a code-execution message */
function createCodeExecutionMessage(id: string, code: string = 'print("hello")'): ParsedMessage {
  return {
    kind: 'code-execution',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'coder',
    code,
    language: 'python',
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create a tool-result message */
function createToolResultMessage(
  id: string,
  result: string = 'hello',
  toolName: string = 'execute_code',
  toolCallId?: string
): ParsedMessage {
  return {
    kind: 'tool-result',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'coder',
    toolName,
    result,
    toolCallId,
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create a browser-tool message */
function createBrowserToolMessage(
  id: string,
  tool: 'visit_url' | 'click' | 'type' | 'scroll' = 'visit_url'
): ParsedMessage {
  return {
    kind: 'cua-browser',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'web_surfer',
    tool,
    toolArgs: { thoughts: 'test action' },
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create a screenshot message */
function createScreenshotMessage(id: string): ParsedMessage {
  return {
    kind: 'screenshot',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'web_surfer',
    imageUrl: 'data:image/png;base64,abc123',
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create a browser-address message */
function createBrowserAddressMessage(id: string): ParsedMessage {
  return {
    kind: 'browser-address',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'web_surfer',
    novncPort: '6080',
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create an internal message */
function createInternalMessage(id: string): ParsedMessage {
  return {
    kind: 'internal',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'orchestrator',
    content: 'debug info',
    raw: createRawMessage(parseInt(id) || 1),
  }
}

/** Create an orchestrator-tool message */
function createOrchestratorToolMessage(
  id: string,
  tool: string,
  toolArgs: Record<string, unknown> = {},
  toolCallId?: string
): ParsedMessage {
  return {
    kind: 'orchestrator-tool',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'OmniAgent',
    tool,
    toolArgs,
    toolCallId,
    raw: createRawMessage(parseInt(id) || 1),
  }
}

// =============================================================================
// shouldMerge Tests
// =============================================================================

describe('shouldMerge', () => {
  it('returns true when code-execution followed by tool-result (execute_code)', () => {
    const codeMsg = createCodeExecutionMessage('1')
    const resultMsg = createToolResultMessage('2', 'hello', 'execute_code')

    expect(shouldMerge(codeMsg, resultMsg)).toBe(true)
  })

  it('returns false when code-execution followed by non-execute_code tool-result', () => {
    const codeMsg = createCodeExecutionMessage('1')
    const resultMsg = createToolResultMessage('2', 'result', 'delegate_cua')

    expect(shouldMerge(codeMsg, resultMsg)).toBe(false)
  })

  it('returns false when code-execution not followed by tool-result', () => {
    const codeMsg = createCodeExecutionMessage('1')
    const textMsg = createTextMessage('2')

    expect(shouldMerge(codeMsg, textMsg)).toBe(false)
  })

  it('returns false when first message is not code-execution', () => {
    const textMsg = createTextMessage('1')
    const resultMsg = createToolResultMessage('2')

    expect(shouldMerge(textMsg, resultMsg)).toBe(false)
  })
})

// =============================================================================
// shouldMergeOrchestratorTool Tests
// =============================================================================

describe('shouldMergeOrchestratorTool', () => {
  it('returns true when orchestrator-tool followed by tool-result with same toolCallId', () => {
    const toolMsg = createOrchestratorToolMessage('1', 'open', { path: '/tmp/test.py' }, 'tc-1')
    const resultMsg = createToolResultMessage('2', 'file contents', 'open', 'tc-1')

    expect(shouldMergeOrchestratorTool(toolMsg, resultMsg)).toBe(true)
  })

  it('returns false when toolCallIds do not match', () => {
    const toolMsg = createOrchestratorToolMessage('1', 'bash', { command: 'ls' }, 'tc-1')
    const resultMsg = createToolResultMessage('2', 'result', 'bash', 'tc-2')

    expect(shouldMergeOrchestratorTool(toolMsg, resultMsg)).toBe(false)
  })

  it('returns false when toolCallId is missing', () => {
    const toolMsg = createOrchestratorToolMessage('1', 'open', { path: '/tmp/test.py' })
    const resultMsg = createToolResultMessage('2', 'file contents', 'open')

    expect(shouldMergeOrchestratorTool(toolMsg, resultMsg)).toBe(false)
  })

  it('returns false when first message is not orchestrator-tool', () => {
    const textMsg = createTextMessage('1')
    const resultMsg = createToolResultMessage('2', 'result', 'bash')

    expect(shouldMergeOrchestratorTool(textMsg, resultMsg)).toBe(false)
  })

  it('returns false when second message is not tool-result', () => {
    const toolMsg = createOrchestratorToolMessage('1', 'bash', { command: 'ls' })
    const textMsg = createTextMessage('2')

    expect(shouldMergeOrchestratorTool(toolMsg, textMsg)).toBe(false)
  })
})

// =============================================================================
// isCuaBrowserMessage Tests
// =============================================================================

describe('isCuaBrowserMessage', () => {
  it('returns true for cua-browser messages', () => {
    const msg = createBrowserToolMessage('1')
    expect(isCuaBrowserMessage(msg)).toBe(true)
  })

  it('returns false for non-cua-browser messages', () => {
    const textMsg = createTextMessage('1')
    expect(isCuaBrowserMessage(textMsg)).toBe(false)

    const userMsg = createUserMessage('1')
    expect(isCuaBrowserMessage(userMsg)).toBe(false)

    const screenshotMsg = createScreenshotMessage('1')
    expect(isCuaBrowserMessage(screenshotMsg)).toBe(false)
  })
})

// =============================================================================
// computeRenderItems Tests
// =============================================================================

describe('computeRenderItems', () => {
  it('returns empty array for empty messages', () => {
    const result = computeRenderItems([], null)
    expect(result).toEqual([])
  })

  it('renders regular messages as message items', () => {
    const messages = [createTextMessage('1'), createTextMessage('2')]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(2)
    expect(result[0].kind).toBe('message')
    expect(result[1].kind).toBe('message')
  })

  it('filters out internal messages', () => {
    const messages = [createTextMessage('1'), createInternalMessage('2'), createTextMessage('3')]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(2)
    expect(result.every((item) => item.kind === 'message')).toBe(true)
  })

  it('filters out browser-address messages', () => {
    const messages = [
      createTextMessage('1'),
      createBrowserAddressMessage('2'),
      createTextMessage('3'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(2)
  })

  it('merges code-execution with subsequent tool-result (execute_code)', () => {
    const messages = [
      createCodeExecutionMessage('1', 'print("hello")'),
      createToolResultMessage('2', 'hello', 'execute_code'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('code-execution')
      expect(result[0].codeResultContent).toBe('hello')
    }
  })

  it('groups consecutive CUA actions', () => {
    const messages = [
      createBrowserToolMessage('1', 'visit_url'),
      createScreenshotMessage('2'),
      createBrowserToolMessage('3', 'click'),
      createScreenshotMessage('4'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('cua-group')
    if (result[0].kind === 'cua-group') {
      expect(result[0].actions).toHaveLength(2)
    }
  })

  it('ends CUA group when non-CUA message arrives', () => {
    const messages = [
      createBrowserToolMessage('1', 'visit_url'),
      createScreenshotMessage('2'),
      createTextMessage('3', 'Summary of actions'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(2)
    expect(result[0].kind).toBe('cua-group')
    expect(result[1].kind).toBe('message')
  })

  it('adds browser embed after CUA group when novncUrl is available', () => {
    const messages = [
      createBrowserAddressMessage('1'),
      createBrowserToolMessage('2', 'visit_url'),
      createScreenshotMessage('3'),
    ]

    const result = computeRenderItems(messages, 'ws://localhost:6080')

    expect(result).toHaveLength(2) // cua-group + browser-embed
    expect(result[0].kind).toBe('cua-group')
    expect(result[1].kind).toBe('browser-embed')
  })

  it('defers browser embed when novncUrl available but no CUA actions yet', () => {
    const messages = [createBrowserAddressMessage('1')]

    const result = computeRenderItems(messages, 'ws://localhost:6080')

    // A live browser is connected but no tool call has happened yet
    // (e.g. websurfer_only right after launch). The browser embed and the
    // "Using web browser" placeholder are deferred until the first CUA
    // action forms a group, so the bottom status indicator stays visible.
    expect(result).toHaveLength(0)
  })

  it('shows browser embed once the first CUA action arrives', () => {
    const messages = [createBrowserAddressMessage('1'), createBrowserToolMessage('2', 'visit_url')]

    const result = computeRenderItems(messages, 'ws://localhost:6080')

    // First tool call forms a cua-group; the browser embed now appears.
    expect(result.some((it) => it.kind === 'cua-group')).toBe(true)
    expect(result.some((it) => it.kind === 'browser-embed')).toBe(true)
    // No standalone "Using web browser" placeholder once a real group exists.
    expect(result.some((it) => it.kind === 'cua-placeholder')).toBe(false)
  })

  it('sets canUseProgressiveTense for last CUA group', () => {
    const messages = [createBrowserToolMessage('1', 'visit_url'), createScreenshotMessage('2')]

    const result = computeRenderItems(messages, null)

    expect(result[0].kind).toBe('cua-group')
    if (result[0].kind === 'cua-group') {
      expect(result[0].canUseProgressiveTense).toBe(true)
    }
  })

  it('disables canUseProgressiveTense when message follows CUA group', () => {
    const messages = [
      createBrowserToolMessage('1', 'visit_url'),
      createScreenshotMessage('2'),
      createTextMessage('3', 'Done'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result[0].kind).toBe('cua-group')
    if (result[0].kind === 'cua-group') {
      expect(result[0].canUseProgressiveTense).toBe(false)
    }
  })

  it('marks actions as complete when screenshot arrives and associates URL', () => {
    const messages = [
      createBrowserToolMessage('1', 'visit_url'),
      createScreenshotMessage('2'),
      createBrowserToolMessage('3', 'click'),
      // No screenshot after click - action in progress
    ]

    const result = computeRenderItems(messages, null)

    expect(result[0].kind).toBe('cua-group')
    if (result[0].kind === 'cua-group') {
      expect(result[0].actions[0].isComplete).toBe(true) // visit_url complete
      expect(result[0].actions[0].screenshotUrl).toBe('data:image/png;base64,abc123') // URL associated
      expect(result[0].actions[1].isComplete).toBe(false) // click in progress
      expect(result[0].actions[1].screenshotUrl).toBeUndefined() // no URL yet
    }
  })

  it('shows browser embed after the last CUA group', () => {
    // Multiple CUA groups with text message in between
    const messages = [
      createBrowserAddressMessage('1'),
      createBrowserToolMessage('2', 'visit_url'),
      createScreenshotMessage('3'),
      // Text message ends first CUA group
      createTextMessage('4', 'Summary'),
      // Second CUA group
      createBrowserAddressMessage('5'),
      createBrowserToolMessage('6', 'type'),
      createScreenshotMessage('7'),
    ]

    const result = computeRenderItems(messages, 'ws://localhost:6080')

    // Should have: cua-group, message, cua-group, browser-embed
    const cuaGroups = result.filter((r) => r.kind === 'cua-group')
    const browserEmbeds = result.filter((r) => r.kind === 'browser-embed')

    expect(cuaGroups).toHaveLength(2)
    expect(browserEmbeds).toHaveLength(1)

    // Browser embed should come after the last CUA group
    const lastCuaIndex = result.findIndex((r) => r.kind === 'cua-group' && r.groupId === 'cua-6')
    const embedIndex = result.findIndex((r) => r.kind === 'browser-embed')
    expect(embedIndex).toBe(lastCuaIndex + 1)
  })

  // =========================================================================
  // Screenshot-only mode (no VNC)
  // =========================================================================

  it('adds browser embed when hasScreenshots=true and no novncUrl', () => {
    const messages = [createBrowserToolMessage('1', 'visit_url'), createScreenshotMessage('2')]

    const result = computeRenderItems(messages, null, true)

    expect(result).toHaveLength(2) // cua-group + browser-embed
    expect(result[0].kind).toBe('cua-group')
    expect(result[1].kind).toBe('browser-embed')
  })

  it('does not add browser embed when hasScreenshots=false and no novncUrl', () => {
    const messages = [createBrowserToolMessage('1', 'visit_url'), createScreenshotMessage('2')]

    const result = computeRenderItems(messages, null, false)

    // Should have CUA group but no browser-embed
    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('cua-group')
  })

  it('adds placeholder + browser embed for hasScreenshots=true without CUA actions', () => {
    const messages = [createTextMessage('1', 'hello')]

    const result = computeRenderItems(messages, null, true)

    expect(result).toHaveLength(3) // message + placeholder + browser-embed
    expect(result[1].kind).toBe('cua-placeholder')
    expect(result[2].kind).toBe('browser-embed')
  })

  // =========================================================================
  // Orchestrator Tool Handling
  // =========================================================================

  it('shows orchestrator-tool as active when it is the last message', () => {
    const messages = [createOrchestratorToolMessage('1', 'bash', { command: 'ls -la' })]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
      expect(result[0].toolResultContent).toBeUndefined()
    }
  })

  it('always renders orchestrator-tool even when successor exists', () => {
    const messages = [
      createOrchestratorToolMessage('1', 'bash', { command: 'echo hi' }),
      createCodeExecutionMessage('2', 'echo hi'),
    ]

    const result = computeRenderItems(messages, null)

    // Both should appear: orchestrator-tool + code-execution
    expect(result).toHaveLength(2)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
    }
    expect(result[1].kind).toBe('message')
    if (result[1].kind === 'message') {
      expect(result[1].message.kind).toBe('code-execution')
    }
  })

  it('merges orchestrator-tool with adjacent tool-result of same tool', () => {
    const messages = [
      createOrchestratorToolMessage('1', 'open', { path: '/tmp/test.py' }, 'tc-1'),
      createToolResultMessage('2', 'File contents here', 'open', 'tc-1'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
      expect(result[0].toolResultContent).toBe('File contents here')
    }
  })

  it('does not merge orchestrator-tool with non-matching tool-result', () => {
    const messages = [
      createOrchestratorToolMessage('1', 'bash', { command: 'ls' }),
      createToolResultMessage('2', 'some result', 'open'),
    ]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(2)
  })

  it('skips orchestrator-tool(delegate_cua) when CUA messages follow', () => {
    const messages = [
      createOrchestratorToolMessage('1', 'delegate_cua'),
      createBrowserToolMessage('2', 'visit_url'),
      createScreenshotMessage('3'),
    ]

    const result = computeRenderItems(messages, null)

    // delegate_cua placeholder removed, only CUA group remains
    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('cua-group')
  })

  it('shows orchestrator-tool(delegate_cua) as placeholder when no CUA messages yet', () => {
    const messages = [createOrchestratorToolMessage('1', 'delegate_cua')]

    const result = computeRenderItems(messages, null)

    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
    }
  })

  it('does not duplicate shimmer when delegate_cua + novncUrl (no cua-placeholder needed)', () => {
    // delegate_cua is the only visible message, novncUrl available
    const messages = [createOrchestratorToolMessage('1', 'delegate_cua')]

    const result = computeRenderItems(messages, 'ws://localhost:6080')

    // Should be: orchestrator-tool message + browser-embed (NO cua-placeholder)
    expect(result).toHaveLength(2)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
    }
    expect(result[1].kind).toBe('browser-embed')
    // Ensure no cua-placeholder was added
    expect(result.some((item) => item.kind === 'cua-placeholder')).toBe(false)
  })

  it('recovers tool name on standalone tool-result via tool_call_id lookup', () => {
    // Simulates a delegate_cua flow: tool_call, then CUA browser activity,
    // then a non-adjacent tool_result whose content lacks the legacy
    // "Tool 'xxx' result:" prefix (so parser leaves toolName undefined).
    const callId = 'tc-123'
    const standaloneResult = createToolResultMessage('4', 'final summary', '', callId)
    const messages: ParsedMessage[] = [
      createOrchestratorToolMessage('1', 'delegate_cua', {}, callId),
      createBrowserToolMessage('2', 'visit_url'),
      createScreenshotMessage('3'),
      // Use a synthetic tool-result with toolName = '' to mimic parser fallback.
      { ...standaloneResult, toolName: undefined } as ParsedMessage,
    ]

    const result = computeRenderItems(messages, null)

    // Find the standalone tool-result render item
    const toolResultItem = result.find(
      (item) => item.kind === 'message' && item.message.kind === 'tool-result'
    )
    expect(toolResultItem).toBeDefined()
    if (toolResultItem?.kind === 'message' && toolResultItem.message.kind === 'tool-result') {
      expect(toolResultItem.message.toolName).toBe('delegate_cua')
    }
  })

  it('preserves parser-extracted tool name when standalone tool-result already has one', () => {
    const callId = 'tc-456'
    const messages: ParsedMessage[] = [
      createOrchestratorToolMessage('1', 'delegate_cua', {}, callId),
      createBrowserToolMessage('2', 'visit_url'),
      createScreenshotMessage('3'),
      // Parser succeeded — toolName already set; lookup should not overwrite it.
      createToolResultMessage('4', 'final summary', 'some_other_tool', callId),
    ]

    const result = computeRenderItems(messages, null)

    const toolResultItem = result.find(
      (item) => item.kind === 'message' && item.message.kind === 'tool-result'
    )
    expect(toolResultItem).toBeDefined()
    if (toolResultItem?.kind === 'message' && toolResultItem.message.kind === 'tool-result') {
      expect(toolResultItem.message.toolName).toBe('some_other_tool')
    }
  })

  it('leaves tool name undefined when standalone tool-result has no matching tool_call_id', () => {
    const messages: ParsedMessage[] = [
      // tool-result with a tool_call_id that no orchestrator-tool message produced
      {
        ...createToolResultMessage('1', 'orphan result', '', 'unknown-id'),
        toolName: undefined,
      } as ParsedMessage,
    ]

    const result = computeRenderItems(messages, null)

    const toolResultItem = result.find(
      (item) => item.kind === 'message' && item.message.kind === 'tool-result'
    )
    expect(toolResultItem).toBeDefined()
    if (toolResultItem?.kind === 'message' && toolResultItem.message.kind === 'tool-result') {
      expect(toolResultItem.message.toolName).toBeUndefined()
    }
  })

  it('full execute_code sequence: orchestrator-tool + code-execution + tool-result', () => {
    const messages = [
      createOrchestratorToolMessage('1', 'execute_code'),
      createCodeExecutionMessage('2', 'print("hello")'),
      createToolResultMessage('3', 'hello', 'execute_code'),
    ]

    const result = computeRenderItems(messages, null)

    // orchestrator-tool rendered, code-execution merged with tool-result
    expect(result).toHaveLength(2)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
    }
    expect(result[1].kind).toBe('message')
    if (result[1].kind === 'message') {
      expect(result[1].message.kind).toBe('code-execution')
      expect(result[1].codeResultContent).toBe('hello')
    }
  })

  it('merges orchestrator-tool(search_dir) with adjacent tool-result', () => {
    const messages = [
      createOrchestratorToolMessage('1', 'search_dir', { term: 'TODO', directory: '/src' }, 'tc-1'),
      createToolResultMessage('2', 'file1.py\nfile2.py', 'search_dir', 'tc-1'),
    ]

    const result = computeRenderItems(messages, null)

    // orchestrator-tool merged with tool-result
    expect(result).toHaveLength(1)
    expect(result[0].kind).toBe('message')
    if (result[0].kind === 'message') {
      expect(result[0].message.kind).toBe('orchestrator-tool')
      expect(result[0].toolResultContent).toBe('file1.py\nfile2.py')
    }
  })
})

// =============================================================================
// shouldHideStatusIndicator Tests
// =============================================================================

describe('shouldHideStatusIndicator', () => {
  // -------------------------------------------------------------------------
  // Helper: wrap a ParsedMessage as a RenderItem
  // -------------------------------------------------------------------------
  function msgItem(message: ParsedMessage, codeResultContent?: string): RenderItem {
    return { kind: 'message', message, codeResultContent }
  }

  function cuaGroupItem(canUseProgressiveTense: boolean): RenderItem {
    return { kind: 'cua-group', actions: [], groupId: 'cua-1', canUseProgressiveTense }
  }

  function cuaPlaceholderItem(): RenderItem {
    return { kind: 'cua-placeholder', groupId: 'cua-placeholder' }
  }

  function createFinalAnswerMessage(id: string): ParsedMessage {
    return {
      kind: 'final-answer',
      id,
      timestamp: '2025-01-01T00:00:00Z',
      source: 'orchestrator',
      content: 'Here is the answer',
      raw: createRawMessage(parseInt(id) || 1),
    }
  }

  function createInputRequestMessage(
    id: string,
    content: string = 'Please provide input'
  ): ParsedMessage {
    return {
      kind: 'input-request',
      id,
      timestamp: '2025-01-01T00:00:00Z',
      source: 'orchestrator',
      inputType: 'text_input',
      content,
      raw: createRawMessage(parseInt(id) || 1),
    }
  }

  function createErrorMessage(id: string, content: string = 'Something failed'): ParsedMessage {
    return {
      kind: 'error',
      id,
      timestamp: '2025-01-01T00:00:00Z',
      source: 'orchestrator',
      content,
      raw: createRawMessage(parseInt(id) || 1),
    }
  }

  function createSystemStatusMessage(
    id: string,
    status: 'error' | 'complete' | 'stopped' | 'paused',
    content: string = 'Error occurred'
  ): ParsedMessage {
    return {
      kind: 'system-status',
      id,
      timestamp: '2025-01-01T00:00:00Z',
      source: 'system',
      status,
      content,
      raw: createRawMessage(parseInt(id) || 1),
    }
  }

  // -------------------------------------------------------------------------
  // Non-active statuses return false by default
  // -------------------------------------------------------------------------
  it('returns false for undefined sessionStatus', () => {
    expect(shouldHideStatusIndicator([], undefined)).toBe(false)
  })

  it('returns false for created status', () => {
    const items: RenderItem[] = [msgItem(createTextMessage('1'))]
    expect(shouldHideStatusIndicator(items, 'created')).toBe(false)
  })

  it('returns false for stopped status', () => {
    const items: RenderItem[] = [msgItem(createTextMessage('1'))]
    expect(shouldHideStatusIndicator(items, 'stopped')).toBe(false)
  })

  it('returns false for paused status', () => {
    const items: RenderItem[] = [msgItem(createTextMessage('1'))]
    expect(shouldHideStatusIndicator(items, 'paused')).toBe(false)
  })

  // -------------------------------------------------------------------------
  // Active: shimmer headers
  // -------------------------------------------------------------------------
  describe('active status', () => {
    it('returns true when cua-placeholder exists', () => {
      const items: RenderItem[] = [cuaPlaceholderItem()]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(true)
    })

    it('returns true when cua-group has canUseProgressiveTense', () => {
      const items: RenderItem[] = [cuaGroupItem(true)]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(true)
    })

    it('returns false when cua-group does NOT have canUseProgressiveTense', () => {
      const items: RenderItem[] = [cuaGroupItem(false)]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(false)
    })

    it('returns true when code-execution has no result', () => {
      const items: RenderItem[] = [msgItem(createCodeExecutionMessage('1'))]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(true)
    })

    it('returns false when code-execution has result', () => {
      const items: RenderItem[] = [msgItem(createCodeExecutionMessage('1'), 'output')]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(false)
    })

    it('returns false when only regular messages', () => {
      const items: RenderItem[] = [msgItem(createTextMessage('1'))]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(false)
    })

    it('returns true when orchestrator-tool is the last item (no result)', () => {
      const items: RenderItem[] = [msgItem(createOrchestratorToolMessage('1', 'delegate_cua'))]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(true)
    })

    it('returns false when orchestrator-tool has result (completed)', () => {
      const item: RenderItem = {
        kind: 'message',
        message: createOrchestratorToolMessage('1', 'bash', { command: 'ls' }),
        toolResultContent: 'file1.py',
      }
      expect(shouldHideStatusIndicator([item], 'active')).toBe(false)
    })

    it('returns true when orchestrator-tool is last before browser-embed (no result)', () => {
      const items: RenderItem[] = [
        msgItem(createOrchestratorToolMessage('1', 'execute_code')),
        { kind: 'browser-embed', groupId: 'browser-embed' },
      ]
      expect(shouldHideStatusIndicator(items, 'active')).toBe(true)
    })
  })

  // -------------------------------------------------------------------------
  // Completed: last message is final-answer
  // -------------------------------------------------------------------------
  describe('completed status', () => {
    it('returns true when last message is final-answer', () => {
      const items: RenderItem[] = [
        msgItem(createTextMessage('1')),
        msgItem(createFinalAnswerMessage('2')),
      ]
      expect(shouldHideStatusIndicator(items, 'completed')).toBe(true)
    })

    it('returns false when last message is NOT final-answer', () => {
      const items: RenderItem[] = [
        msgItem(createFinalAnswerMessage('1')),
        msgItem(createTextMessage('2')),
      ]
      expect(shouldHideStatusIndicator(items, 'completed')).toBe(false)
    })

    it('returns false when no messages', () => {
      expect(shouldHideStatusIndicator([], 'completed')).toBe(false)
    })

    it('skips non-message items to find last message', () => {
      const items: RenderItem[] = [
        msgItem(createFinalAnswerMessage('1')),
        { kind: 'browser-embed', groupId: 'browser-embed' },
      ]
      expect(shouldHideStatusIndicator(items, 'completed')).toBe(true)
    })

    it('returns true when last message is system-status with complete status', () => {
      const items: RenderItem[] = [
        msgItem(createFinalAnswerMessage('1')),
        msgItem(createSystemStatusMessage('2', 'complete', 'Task completed')),
      ]
      expect(shouldHideStatusIndicator(items, 'completed')).toBe(true)
    })

    it('returns false when last message is system-status with complete status but empty content', () => {
      const items: RenderItem[] = [
        msgItem(createTextMessage('1')),
        msgItem(createSystemStatusMessage('2', 'complete', '')),
      ]
      expect(shouldHideStatusIndicator(items, 'completed')).toBe(false)
    })
  })

  // -------------------------------------------------------------------------
  // Awaiting input: last message is input-request with content
  // -------------------------------------------------------------------------
  describe('awaiting-input status', () => {
    it('returns true when last message is input-request with content', () => {
      const items: RenderItem[] = [msgItem(createInputRequestMessage('1', 'Need input'))]
      expect(shouldHideStatusIndicator(items, 'awaiting-input')).toBe(true)
    })

    it('returns false when last message is input-request with empty content', () => {
      const items: RenderItem[] = [msgItem(createInputRequestMessage('1', ''))]
      expect(shouldHideStatusIndicator(items, 'awaiting-input')).toBe(false)
    })

    it('returns false when last message is NOT input-request', () => {
      const items: RenderItem[] = [msgItem(createTextMessage('1'))]
      expect(shouldHideStatusIndicator(items, 'awaiting-input')).toBe(false)
    })
  })

  // -------------------------------------------------------------------------
  // Error: last message is error or system-status(error) with content
  // -------------------------------------------------------------------------
  describe('error status', () => {
    it('returns true when last message is error with content', () => {
      const items: RenderItem[] = [msgItem(createErrorMessage('1', 'Failed'))]
      expect(shouldHideStatusIndicator(items, 'error')).toBe(true)
    })

    it('returns true when last message is system-status with error status and content', () => {
      const items: RenderItem[] = [msgItem(createSystemStatusMessage('1', 'error', 'Crashed'))]
      expect(shouldHideStatusIndicator(items, 'error')).toBe(true)
    })

    it('returns false when last message is system-status with non-error status', () => {
      const items: RenderItem[] = [msgItem(createSystemStatusMessage('1', 'complete', 'Done'))]
      expect(shouldHideStatusIndicator(items, 'error')).toBe(false)
    })

    it('returns false when last message is error with empty content', () => {
      const items: RenderItem[] = [msgItem(createErrorMessage('1', ''))]
      expect(shouldHideStatusIndicator(items, 'error')).toBe(false)
    })

    it('returns false when last message is NOT error-related', () => {
      const items: RenderItem[] = [msgItem(createTextMessage('1'))]
      expect(shouldHideStatusIndicator(items, 'error')).toBe(false)
    })
  })
})

// =============================================================================
// File Message Deduplication
// =============================================================================

describe('file message deduplication in computeRenderItems', () => {
  function createFileMessage(
    id: string,
    files: Array<{ name: string; url: string }>
  ): ParsedMessage {
    return {
      kind: 'file',
      id,
      timestamp: '2025-01-01T00:00:00Z',
      source: 'system',
      files: files.map((f) => ({
        ...f,
        timestamp: 1,
        extension: f.name.split('.').pop() || '',
        file_type: 'text',
        action: 'created' as const,
      })),
      raw: createRawMessage(parseInt(id) || 1),
    } as ParsedMessage
  }

  it('shows file chip on first occurrence', () => {
    const messages: ParsedMessage[] = [
      createTextMessage('1', 'Creating file'),
      createFileMessage('2', [{ name: 'report.md', url: '/files/report.md' }]),
    ]

    const items = computeRenderItems(messages, null)
    const fileItems = items.filter((i) => i.kind === 'message' && i.message.kind === 'file')
    expect(fileItems).toHaveLength(1)
  })

  it('deduplicates same file url across multiple messages', () => {
    const messages: ParsedMessage[] = [
      createFileMessage('1', [{ name: 'report.md', url: '/files/report.md' }]),
      createTextMessage('2', 'Modified the file'),
      createFileMessage('3', [{ name: 'report.md', url: '/files/report.md' }]),
    ]

    const items = computeRenderItems(messages, null)
    const fileItems = items.filter((i) => i.kind === 'message' && i.message.kind === 'file')
    expect(fileItems).toHaveLength(1) // Only first occurrence
  })

  it('shows different files with different urls', () => {
    const messages: ParsedMessage[] = [
      createFileMessage('1', [{ name: 'a.md', url: '/files/a.md' }]),
      createFileMessage('2', [{ name: 'b.md', url: '/files/b.md' }]),
    ]

    const items = computeRenderItems(messages, null)
    const fileItems = items.filter((i) => i.kind === 'message' && i.message.kind === 'file')
    expect(fileItems).toHaveLength(2)
  })

  it('filters already-seen files from multi-file messages', () => {
    const messages: ParsedMessage[] = [
      createFileMessage('1', [{ name: 'a.md', url: '/files/a.md' }]),
      createFileMessage('2', [
        { name: 'a.md', url: '/files/a.md' }, // duplicate
        { name: 'b.md', url: '/files/b.md' }, // new
      ]),
    ]

    const items = computeRenderItems(messages, null)
    const fileItems = items.filter((i) => i.kind === 'message' && i.message.kind === 'file')
    expect(fileItems).toHaveLength(2)
    // Second file message should only contain b.md
    const secondFileMsg = fileItems[1]
    if (secondFileMsg.kind === 'message' && secondFileMsg.message.kind === 'file') {
      expect(secondFileMsg.message.files).toHaveLength(1)
      expect(secondFileMsg.message.files[0].name).toBe('b.md')
    }
  })

  it('skips file message entirely if all files are duplicates', () => {
    const messages: ParsedMessage[] = [
      createFileMessage('1', [
        { name: 'a.md', url: '/files/a.md' },
        { name: 'b.md', url: '/files/b.md' },
      ]),
      createFileMessage('2', [
        { name: 'a.md', url: '/files/a.md' },
        { name: 'b.md', url: '/files/b.md' },
      ]),
    ]

    const items = computeRenderItems(messages, null)
    const fileItems = items.filter((i) => i.kind === 'message' && i.message.kind === 'file')
    expect(fileItems).toHaveLength(1) // Only the first message
  })

  it('always renders summary file message even when files were already seen', () => {
    // End-of-run summary lists every file the agent touched. Without the
    // exemption, dedup would drop it entirely because each file already
    // appeared inline during the run.
    const summaryMsg = createFileMessage('2', [{ name: 'a.md', url: '/files/a.md' }])
    if (summaryMsg.kind === 'file') {
      summaryMsg.summary = true
    }
    const messages: ParsedMessage[] = [
      createFileMessage('1', [{ name: 'a.md', url: '/files/a.md' }]),
      summaryMsg,
    ]

    const items = computeRenderItems(messages, null)
    const fileItems = items.filter((i) => i.kind === 'message' && i.message.kind === 'file')
    expect(fileItems).toHaveLength(2)
    const last = fileItems[1]
    if (last.kind === 'message' && last.message.kind === 'file') {
      expect(last.message.summary).toBe(true)
      expect(last.message.files).toHaveLength(1)
      expect(last.message.files[0].name).toBe('a.md')
    }
  })
})

// =============================================================================
// CUA group folding: errors + inline non-browser tools
// =============================================================================

function createErrorMessage(id: string, content: string): ParsedMessage {
  return {
    kind: 'error',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'web_surfer',
    content,
    raw: createRawMessage(parseInt(id) || 1),
  }
}

function createCuaNonBrowserMessage(
  id: string,
  tool: 'read_page_answer_question' | 'run_command' | 'pause_and_memorize_fact',
  toolArgs: Record<string, unknown> = {}
): ParsedMessage {
  return {
    kind: 'cua-non-browser',
    id,
    timestamp: '2025-01-01T00:00:00Z',
    source: 'web_surfer',
    tool,
    toolArgs: { thoughts: '', ...toolArgs },
    raw: createRawMessage(parseInt(id) || 1),
  } as ParsedMessage
}

describe('computeRenderItems — CUA group folding', () => {
  it('folds errors during a CUA flow inline as error rows with the failing tool context', () => {
    const messages: ParsedMessage[] = [
      createBrowserToolMessage('1', 'visit_url'),
      createErrorMessage('2', 'Connection error.'),
    ]

    const items = computeRenderItems(messages, null)

    expect(items).toHaveLength(1)
    expect(items[0].kind).toBe('cua-group')
    if (items[0].kind === 'cua-group') {
      expect(items[0].actions).toHaveLength(2)
      const errorRow = items[0].actions[1]
      expect(errorRow.errorContent).toBe('Connection error.')
      // Error row inherits the failing action's tool/toolArgs so the UI
      // can render "Error Visiting ...".
      expect(errorRow.tool).toBe('visit_url')
    }
  })

  it('inherits tool context from the last real action across consecutive errors', () => {
    const messages: ParsedMessage[] = [
      createBrowserToolMessage('1', 'visit_url'),
      createErrorMessage('2', 'Connection error.'),
      createErrorMessage('3', 'Connection error.'),
    ]

    const items = computeRenderItems(messages, null)

    expect(items).toHaveLength(1)
    if (items[0].kind === 'cua-group') {
      expect(items[0].actions).toHaveLength(3)
      // Both errors should carry the original visit_url context, not the
      // previous error pseudo-action (which has no tool).
      expect(items[0].actions[1].tool).toBe('visit_url')
      expect(items[0].actions[2].tool).toBe('visit_url')
    }
  })

  it('folds read_page_answer_question into the CUA group', () => {
    const messages: ParsedMessage[] = [
      createBrowserToolMessage('1', 'visit_url'),
      createCuaNonBrowserMessage('2', 'read_page_answer_question', {
        question: 'What is the score?',
      }),
      createBrowserToolMessage('3', 'click'),
    ]

    const items = computeRenderItems(messages, null)

    expect(items).toHaveLength(1)
    expect(items[0].kind).toBe('cua-group')
    if (items[0].kind === 'cua-group') {
      expect(items[0].actions).toHaveLength(3)
      expect(items[0].actions[1].tool).toBe('read_page_answer_question')
    }
  })

  it('folds run_command into the CUA group', () => {
    const messages: ParsedMessage[] = [
      createBrowserToolMessage('1', 'visit_url'),
      createCuaNonBrowserMessage('2', 'run_command', { command: 'ls -la' }),
    ]

    const items = computeRenderItems(messages, null)

    expect(items).toHaveLength(1)
    if (items[0].kind === 'cua-group') {
      expect(items[0].actions).toHaveLength(2)
      expect(items[0].actions[1].tool).toBe('run_command')
    }
  })

  it('does NOT fold pause_and_memorize_fact into the CUA group', () => {
    const messages: ParsedMessage[] = [
      createBrowserToolMessage('1', 'visit_url'),
      createCuaNonBrowserMessage('2', 'pause_and_memorize_fact', { fact: 'note' }),
    ]

    const items = computeRenderItems(messages, null)

    // pause_and_memorize_fact flushes the group and renders standalone
    expect(items.length).toBeGreaterThanOrEqual(2)
    expect(items[0].kind).toBe('cua-group')
    if (items[0].kind === 'cua-group') {
      expect(items[0].actions).toHaveLength(1)
      expect(items[0].actions[0].tool).toBe('visit_url')
    }
  })
})

// =============================================================================
// computeRenderItems — timestamp separators
// =============================================================================

describe('insertTimestampSeparators', () => {
  /** Build a text message at a specific ISO time. */
  function textAt(id: string, iso: string, content: string = 'msg'): ParsedMessage {
    return { ...createTextMessage(id, content), timestamp: iso }
  }

  /** Build a browser-tool message at a specific ISO time. */
  function browserAt(id: string, iso: string): ParsedMessage {
    return { ...createBrowserToolMessage(id, 'visit_url'), timestamp: iso }
  }

  /** Run the full pipeline used in production: structural + separators. */
  function pipeline(messages: ParsedMessage[]): RenderItem[] {
    return insertTimestampSeparators(computeRenderItems(messages, null, false))
  }

  it('inserts a leading timestamp before the first message', () => {
    const items = pipeline([textAt('1', '2025-01-01T10:00:00Z')])
    expect(items[0].kind).toBe('timestamp')
    if (items[0].kind === 'timestamp') {
      expect(items[0].iso).toBe('2025-01-01T10:00:00Z')
    }
    expect(items[1].kind).toBe('message')
  })

  it('does not insert a separator when the gap is below the threshold', () => {
    // 5 minute gap < 10 minutes
    const items = pipeline([
      textAt('1', '2025-01-01T10:00:00Z'),
      textAt('2', '2025-01-01T10:05:00Z'),
    ])
    const separators = items.filter((it) => it.kind === 'timestamp')
    expect(separators).toHaveLength(1) // only the leading one
  })

  it('inserts a separator when the gap exceeds the threshold', () => {
    // 11 minute gap > 10 minutes
    const items = pipeline([
      textAt('1', '2025-01-01T10:00:00Z'),
      textAt('2', '2025-01-01T10:11:00Z'),
    ])
    const separators = items.filter((it) => it.kind === 'timestamp')
    expect(separators).toHaveLength(2) // leading + between
    // Order: [ts-lead, msg-1, ts-between, msg-2]
    expect(items.map((it) => it.kind)).toEqual(['timestamp', 'message', 'timestamp', 'message'])
  })

  it('keeps a CUA group atomic — never inserts a separator inside it', () => {
    // Two browser actions inside the same group, 30 minutes apart.
    // Even though the gap >> 10 min, they collapse into one cua-group, and the
    // separator must appear before the group, not inside it.
    const items = pipeline([
      browserAt('1', '2025-01-01T10:00:00Z'),
      browserAt('2', '2025-01-01T10:30:00Z'),
    ])
    expect(items.map((it) => it.kind)).toEqual(['timestamp', 'cua-group'])
    if (items[1].kind === 'cua-group') {
      expect(items[1].actions).toHaveLength(2)
    }
  })

  it('uses the first action timestamp as the cua-group anchor', () => {
    // text at 09:00, then a CUA group starting at 09:30 (30 min later).
    // Should produce: [lead-ts(09:00), text, gap-ts(09:30), cua-group]
    const items = pipeline([
      textAt('1', '2025-01-01T09:00:00Z'),
      browserAt('2', '2025-01-01T09:30:00Z'),
    ])
    expect(items.map((it) => it.kind)).toEqual(['timestamp', 'message', 'timestamp', 'cua-group'])
    if (items[2].kind === 'timestamp') {
      expect(items[2].iso).toBe('2025-01-01T09:30:00Z')
    }
  })

  it('returns an empty array for no messages (no leading separator without anchor)', () => {
    const items = pipeline([])
    expect(items).toEqual([])
  })
})
