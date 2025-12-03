/**
 * Unit tests for message parser
 */

import { describe, it, expect } from 'vitest'
import { parseMessage, parseMessages } from '@/lib/messages/parser'
import type { Message, MessageContentItem } from '@/types/api'

// =============================================================================
// Test Helpers
// =============================================================================

function createMessage(
  config: {
    source?: string
    content?: string | MessageContentItem[]
    metadata?: Record<string, unknown>
  },
  id?: number
): Message {
  return {
    id: id ?? 1,
    run_id: 'run-1',
    session_id: 1,
    created_at: '2024-01-01T00:00:00Z',
    config: {
      source: config.source ?? 'web_surfer',
      content: config.content ?? '',
      metadata: config.metadata,
    },
  }
}

// =============================================================================
// User Messages
// =============================================================================

describe('parseMessage - user messages', () => {
  it('parses user message with plain string content', () => {
    const msg = createMessage({
      source: 'user',
      content: 'Hello world',
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('user')
    expect(result.source).toBe('user')
    if (result.kind === 'user') {
      expect(result.content).toBe('Hello world')
    }
  })

  it('unwraps JSON-encoded user content', () => {
    const msg = createMessage({
      source: 'user_proxy',
      content: JSON.stringify({
        accepted: true,
        content: 'User typed message',
      }),
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('user')
    if (result.kind === 'user') {
      expect(result.content).toBe('User typed message')
    }
  })
})

// =============================================================================
// Browser Tool Messages
// =============================================================================

describe('parseMessage - browser tool messages', () => {
  it('parses left_click action', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Clicking on button' }],
      metadata: {
        type: 'tool_call',
        tool: 'left_click',
        tool_args: {
          coordinate: [100, 200],
          thoughts: 'Clicking the submit button',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-browser')
    if (result.kind === 'cua-browser') {
      expect(result.tool).toBe('left_click')
      expect(result.toolArgs.coordinate).toEqual([100, 200])
      expect(result.toolArgs.thoughts).toBe('Clicking the submit button')
    }
  })

  it('parses type action', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Typing text' }],
      metadata: {
        type: 'tool_call',
        tool: 'type',
        tool_args: {
          text: 'hello@example.com',
          press_enter: true,
          thoughts: 'Entering email',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-browser')
    if (result.kind === 'cua-browser') {
      expect(result.tool).toBe('type')
      expect(result.toolArgs.text).toBe('hello@example.com')
      expect(result.toolArgs.press_enter).toBe(true)
    }
  })

  it('parses visit_url action', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Navigating' }],
      metadata: {
        type: 'tool_call',
        tool: 'visit_url',
        tool_args: {
          url: 'https://example.com',
          thoughts: 'Going to the main page',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-browser')
    if (result.kind === 'cua-browser') {
      expect(result.tool).toBe('visit_url')
      expect(result.toolArgs.url).toBe('https://example.com')
    }
  })

  it('parses scroll action', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Scrolling' }],
      metadata: {
        type: 'tool_call',
        tool: 'scroll',
        tool_args: {
          pixels: 300,
          thoughts: 'Scrolling to see more content',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-browser')
    if (result.kind === 'cua-browser') {
      expect(result.tool).toBe('scroll')
      expect(result.toolArgs.pixels).toBe(300)
    }
  })

  it('parses wait action', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Waiting' }],
      metadata: {
        type: 'tool_call',
        tool: 'wait',
        tool_args: {
          time: 5,
          thoughts: 'Waiting for page to load',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-browser')
    if (result.kind === 'cua-browser') {
      expect(result.tool).toBe('wait')
    }
  })
})

// =============================================================================
// Non-Browser Tool Messages
// =============================================================================

describe('parseMessage - non-browser tool messages', () => {
  it('parses pause_and_memorize_fact', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Memorizing fact' }],
      metadata: {
        type: 'tool_call',
        tool: 'pause_and_memorize_fact',
        tool_args: {
          fact: 'User prefers dark mode',
          thoughts: 'Saving user preference',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-non-browser')
    if (result.kind === 'cua-non-browser') {
      expect(result.tool).toBe('pause_and_memorize_fact')
      expect(result.toolArgs.fact).toBe('User prefers dark mode')
    }
  })

  it('parses terminate', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Task complete' }],
      metadata: {
        type: 'tool_call',
        tool: 'terminate',
        tool_args: {
          status: 'success',
          thoughts: 'Task completed successfully',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-non-browser')
    if (result.kind === 'cua-non-browser') {
      expect(result.tool).toBe('terminate')
      expect(result.toolArgs.status).toBe('success')
    }
  })
})

// =============================================================================
// Screenshot Messages
// =============================================================================

describe('parseMessage - screenshot messages', () => {
  it('parses screenshot with image URL', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'image', url: 'data:image/png;base64,abc123' }],
      metadata: { type: 'browser_screenshot' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('screenshot')
    if (result.kind === 'screenshot') {
      expect(result.imageUrl).toBe('data:image/png;base64,abc123')
    }
  })

  it('handles screenshot without image', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'No image' }],
      metadata: { type: 'browser_screenshot' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('screenshot')
    if (result.kind === 'screenshot') {
      expect(result.imageUrl).toBe('')
    }
  })
})

// =============================================================================
// Code Messages
// =============================================================================

describe('parseMessage - code messages', () => {
  it('parses code_to_execute with plain text (no fence)', () => {
    const msg = createMessage({
      source: 'coder',
      content: [{ type: 'text', text: 'print("hello")' }],
      metadata: { type: 'code_to_execute' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('code-execution')
    if (result.kind === 'code-execution') {
      expect(result.code).toBe('print("hello")')
      expect(result.language).toBe('python')
    }
  })

  it('parses code_to_execute with code fence wrapper', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [
        {
          type: 'text',
          text: '[OmniAgent] Executing code:\n```python\nimport requests\nprint("hello")\n```',
        },
      ],
      metadata: { type: 'code_to_execute', code: '' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('code-execution')
    if (result.kind === 'code-execution') {
      expect(result.code).toBe('import requests\nprint("hello")')
      expect(result.language).toBe('python')
    }
  })

  it('prefers metadata.code when non-empty', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'Executing code:\n```python\nwrapped\n```' }],
      metadata: { type: 'code_to_execute', code: 'clean_code()' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('code-execution')
    if (result.kind === 'code-execution') {
      expect(result.code).toBe('clean_code()')
      expect(result.language).toBe('python')
    }
  })

  it('parses tool_result with raw content (tool name resolved downstream)', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'Some result' }],
      metadata: { type: 'tool_result', tool_call_id: 'tc-1' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('tool-result')
    if (result.kind === 'tool-result') {
      // Parser leaves toolName undefined; computeRenderItems fills it via
      // tool_call_id reverse-lookup against the originating orchestrator-tool.
      expect(result.toolName).toBeUndefined()
      expect(result.result).toBe('Some result')
      expect(result.toolCallId).toBe('tc-1')
    }
  })

  it('reads tool name from metadata.tool when present', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'Some result' }],
      metadata: { type: 'tool_result', tool: 'delegate_cua', tool_call_id: 'tc-1' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('tool-result')
    if (result.kind === 'tool-result') {
      expect(result.toolName).toBe('delegate_cua')
      expect(result.result).toBe('Some result')
      expect(result.toolCallId).toBe('tc-1')
    }
  })

  it('parses tool_result without tool_call_id', () => {
    const msg = createMessage({
      source: 'coder',
      content: [{ type: 'text', text: 'hello' }],
      metadata: { type: 'tool_result' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('tool-result')
    if (result.kind === 'tool-result') {
      expect(result.toolName).toBeUndefined()
      expect(result.result).toBe('hello')
      expect(result.toolCallId).toBeUndefined()
    }
  })

  it('routes tool_result for hidden tools (request_user_input) to internal', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'User response: yes' }],
      metadata: { type: 'tool_result', tool: 'request_user_input', tool_call_id: 'tc-1' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('internal')
  })
})

// =============================================================================
// Orchestrator Tool Messages
// =============================================================================

describe('parseMessage - orchestrator tool messages', () => {
  it('parses delegate_cua from OmniAgent as orchestrator-tool', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'Delegating to CUA' }],
      metadata: {
        type: 'tool_call',
        tool: 'delegate_cua',
        tool_args: {
          task: 'Search for flights to Tokyo',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('orchestrator-tool')
    if (result.kind === 'orchestrator-tool') {
      expect(result.tool).toBe('delegate_cua')
      expect(result.toolArgs).toEqual({ task: 'Search for flights to Tokyo' })
    }
  })

  it('parses bash from OmniAgent as orchestrator-tool', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'Running command' }],
      metadata: {
        type: 'tool_call',
        tool: 'bash',
        tool_args: {
          command: 'ls -la',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('orchestrator-tool')
    if (result.kind === 'orchestrator-tool') {
      expect(result.tool).toBe('bash')
      expect(result.toolArgs.command).toBe('ls -la')
    }
  })

  it('parses open from OmniAgent as orchestrator-tool (empty args)', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: '',
      metadata: {
        type: 'tool_call',
        tool: 'open',
        tool_args: { path: '/tmp/test.py' },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('orchestrator-tool')
    if (result.kind === 'orchestrator-tool') {
      expect(result.tool).toBe('open')
      expect(result.toolArgs).toEqual({ path: '/tmp/test.py' })
    }
  })

  it('routes web_surfer tool_call to cua-browser (not orchestrator-tool)', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Clicking' }],
      metadata: {
        type: 'tool_call',
        tool: 'left_click',
        tool_args: { coordinate: [50, 100], thoughts: 'Click the button' },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('cua-browser')
  })

  it('routes unknown web_surfer tool to text (not orchestrator-tool)', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Unknown action' }],
      metadata: {
        type: 'tool_call',
        tool: 'some_unknown_tool',
        tool_args: { thoughts: 'doing something' },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('text')
  })

  it('routes unknown source tool_call to text (not orchestrator-tool)', () => {
    const msg = createMessage({
      source: 'some_other_agent',
      content: 'Some tool action',
      metadata: {
        type: 'tool_call',
        tool: 'custom_tool',
        tool_args: { param: 'value' },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('text')
  })

  it('routes request_user_input from OmniAgent to internal', () => {
    const msg = createMessage({
      source: 'OmniAgent',
      content: 'Requesting input',
      metadata: {
        type: 'tool_call',
        tool: 'request_user_input',
        tool_args: { prompt: 'Please confirm' },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('internal')
  })
})

// =============================================================================
// Other Message Types
// =============================================================================

describe('parseMessage - other types', () => {
  it('parses final_answer', () => {
    const msg = createMessage({
      source: 'orchestrator',
      content: [{ type: 'text', text: 'Here is the answer' }],
      metadata: { type: 'final_answer' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('final-answer')
    if (result.kind === 'final-answer') {
      expect(result.content).toBe('Here is the answer')
    }
  })

  it('routes CUA final_answer to internal in OmniAgent modes', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Task done' }],
      metadata: { type: 'final_answer' },
    })

    // OmniAgent owns the real final answer in 'all' and 'omniagent_only' —
    // the web_surfer's must be demoted to avoid two final-answer cards.
    expect(parseMessage(msg, undefined, 'all').kind).toBe('internal')
    expect(parseMessage(msg, undefined, 'omniagent_only').kind).toBe('internal')
  })

  it('keeps CUA final_answer as the real answer in websurfer_only mode', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Real FARA answer' }],
      metadata: { type: 'final_answer' },
    })

    const result = parseMessage(msg, undefined, 'websurfer_only')

    expect(result.kind).toBe('final-answer')
    if (result.kind === 'final-answer') {
      expect(result.content).toBe('Real FARA answer')
    }
  })

  it('keeps CUA final_answer when agent_mode is null (legacy run)', () => {
    // Information preservation: legacy runs with no persisted agent_mode keep
    // the CUA final_answer as a real final-answer so we never hide the only
    // real answer in legacy FARA-only sessions. The trade-off is that legacy
    // OmniAgent sessions show one extra intermediate final-answer card.
    const msg = createMessage({
      source: 'web_surfer',
      content: [{ type: 'text', text: 'Legacy answer' }],
      metadata: { type: 'final_answer' },
    })

    expect(parseMessage(msg, undefined, null).kind).toBe('final-answer')
    expect(parseMessage(msg, undefined, undefined).kind).toBe('final-answer')
  })

  it('keeps non-CUA final_answer in OmniAgent mode (only CUA is demoted)', () => {
    // OmniAgent's own final_answer in OmniAgent mode is the real answer.
    const msg = createMessage({
      source: 'OmniAgent',
      content: [{ type: 'text', text: 'Orchestrator final' }],
      metadata: { type: 'final_answer' },
    })

    expect(parseMessage(msg, undefined, 'all').kind).toBe('final-answer')
    expect(parseMessage(msg, undefined, 'omniagent_only').kind).toBe('final-answer')
  })

  it('parses summary text', () => {
    const msg = createMessage({
      source: 'orchestrator',
      content: [{ type: 'text', text: 'Summary of actions' }],
      metadata: { type: 'text' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('summary')
    if (result.kind === 'summary') {
      expect(result.content).toBe('Summary of actions')
    }
  })

  it('parses browser_address', () => {
    const msg = createMessage({
      source: 'web_surfer',
      content: 'Browser ready',
      metadata: {
        type: 'browser_address',
        novnc_port: '6080',
        playwright_port: '9222',
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('browser-address')
    if (result.kind === 'browser-address') {
      expect(result.novncPort).toBe('6080')
      expect(result.playwrightPort).toBe('9222')
    }
  })

  it('parses debugging as internal', () => {
    const msg = createMessage({
      source: 'orchestrator',
      content: 'Debug info',
      metadata: { type: 'debugging' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('internal')
  })

  it('parses error message', () => {
    const msg = createMessage({
      source: 'orchestrator',
      content: 'Something went wrong',
      metadata: { type: 'error' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('error')
    if (result.kind === 'error') {
      expect(result.content).toBe('Something went wrong')
    }
  })

  it('fallback to text for unknown metadata type', () => {
    const msg = createMessage({
      source: 'unknown',
      content: 'Plain text',
      metadata: { type: 'unknown_type' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('text')
    if (result.kind === 'text') {
      expect(result.content).toBe('Plain text')
    }
  })

  it('fallback to text for no metadata', () => {
    const msg = createMessage({
      source: 'unknown',
      content: 'Plain text',
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('text')
  })
})

// =============================================================================
// parseMessages (batch)
// =============================================================================

describe('parseMessages', () => {
  it('parses multiple messages', () => {
    const messages = [
      createMessage({ source: 'user', content: 'Hello' }, 1),
      createMessage(
        {
          source: 'web_surfer',
          content: [{ type: 'text', text: 'Clicking' }],
          metadata: {
            type: 'tool_call',
            tool: 'left_click',
            tool_args: { coordinate: [0, 0], thoughts: '' },
          },
        },
        2
      ),
    ]

    const results = parseMessages(messages)

    expect(results).toHaveLength(2)
    expect(results[0].kind).toBe('user')
    expect(results[1].kind).toBe('cua-browser')
  })

  it('threads previousTimestamp to reasoning messages for duration calculation', () => {
    const messages: Message[] = [
      {
        id: 1,
        run_id: 'run-1',
        session_id: 1,
        created_at: '2024-01-01T00:00:00Z',
        config: { source: 'user', content: 'Hello', metadata: undefined },
      },
      {
        id: 2,
        run_id: 'run-1',
        session_id: 1,
        created_at: '2024-01-01T00:00:05Z',
        config: {
          source: 'omni_agent',
          content: [{ type: 'text', text: 'Thinking about the problem' }],
          metadata: { type: 'reasoning' },
        },
      },
    ]

    const results = parseMessages(messages)

    expect(results[1].kind).toBe('reasoning')
    if (results[1].kind === 'reasoning') {
      expect(results[1].thinkingSeconds).toBe(5)
    }
  })

  it('hides CUA final_answer when agent_mode says OmniAgent owns the answer', () => {
    const omniAgentMsg = createMessage(
      {
        source: 'OmniAgent',
        content: [{ type: 'text', text: 'Delegating to CUA' }],
        metadata: {
          type: 'tool_call',
          tool: 'delegate_cua',
          tool_args: { task: 'Do something' },
        },
      },
      1
    )

    const cuaFinalAnswer = createMessage(
      {
        source: 'web_surfer',
        content: [{ type: 'text', text: 'CUA final answer' }],
        metadata: { type: 'final_answer' },
      },
      2
    )

    // OmniAgent run: orchestrator + CUA final_answer → CUA hidden
    const omniResults = parseMessages([omniAgentMsg, cuaFinalAnswer], 'all')
    expect(omniResults).toHaveLength(2)
    expect(omniResults[1].kind).toBe('internal')

    // FARA-only run: CUA owns the final answer
    const faraResults = parseMessages([cuaFinalAnswer], 'websurfer_only')
    expect(faraResults).toHaveLength(1)
    expect(faraResults[0].kind).toBe('final-answer')
    if (faraResults[0].kind === 'final-answer') {
      expect(faraResults[0].content).toBe('CUA final answer')
    }
  })

  it('agent_mode "all" demotes CUA final_answer that arrives before any OmniAgent message', () => {
    // Reproduces session 279 streaming bug: only CUA messages have arrived
    // by the time CUA finishes, but the run is in "all" mode so CUA's
    // final_answer is still intermediate. Persisted agent_mode fixes this.
    const cuaFirst = createMessage(
      {
        source: 'web_surfer',
        content: [{ type: 'text', text: 'preliminary' }],
        metadata: {},
      },
      1
    )
    const cuaFinalAnswer = createMessage(
      {
        source: 'web_surfer',
        content: [{ type: 'text', text: 'CUA final answer' }],
        metadata: { type: 'final_answer' },
      },
      2
    )

    const results = parseMessages([cuaFirst, cuaFinalAnswer], 'all')
    expect(results).toHaveLength(2)
    expect(results[1].kind).toBe('internal')
  })

  it('legacy run (agent_mode null) keeps CUA final_answer to avoid hiding info', () => {
    const cuaFinalAnswer = createMessage(
      {
        source: 'web_surfer',
        content: [{ type: 'text', text: 'Legacy answer' }],
        metadata: { type: 'final_answer' },
      },
      1
    )

    const results = parseMessages([cuaFinalAnswer])
    expect(results[0].kind).toBe('final-answer')
  })

  it('sets thinkingSeconds to null for the first reasoning message (no previous)', () => {
    const messages: Message[] = [
      {
        id: 1,
        run_id: 'run-1',
        session_id: 1,
        created_at: '2024-01-01T00:00:05Z',
        config: {
          source: 'omni_agent',
          content: [{ type: 'text', text: 'Thinking...' }],
          metadata: { type: 'reasoning' },
        },
      },
    ]

    const results = parseMessages(messages)

    expect(results[0].kind).toBe('reasoning')
    if (results[0].kind === 'reasoning') {
      expect(results[0].thinkingSeconds).toBeNull()
    }
  })
})

// =============================================================================
// Reasoning Messages
// =============================================================================

describe('parseMessage - reasoning messages', () => {
  it('parses reasoning message with valid previousTimestamp', () => {
    const msg = createMessage({
      source: 'omni_agent',
      content: [{ type: 'text', text: 'Let me think about this step by step' }],
      metadata: { type: 'reasoning' },
    })
    // Override created_at for predictable duration
    msg.created_at = '2024-01-01T00:00:10Z'

    const result = parseMessage(msg, '2024-01-01T00:00:03Z')

    expect(result.kind).toBe('reasoning')
    if (result.kind === 'reasoning') {
      expect(result.content).toBe('Let me think about this step by step')
      expect(result.thinkingSeconds).toBe(7)
    }
  })

  it('returns thinkingSeconds null when no previousTimestamp', () => {
    const msg = createMessage({
      source: 'omni_agent',
      content: [{ type: 'text', text: 'Reasoning without prior context' }],
      metadata: { type: 'reasoning' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('reasoning')
    if (result.kind === 'reasoning') {
      expect(result.content).toBe('Reasoning without prior context')
      expect(result.thinkingSeconds).toBeNull()
    }
  })

  it('returns thinkingSeconds null for negative time difference', () => {
    const msg = createMessage({
      source: 'omni_agent',
      content: [{ type: 'text', text: 'Out of order message' }],
      metadata: { type: 'reasoning' },
    })
    // created_at is before previousTimestamp (clock skew or out-of-order)
    msg.created_at = '2024-01-01T00:00:00Z'

    const result = parseMessage(msg, '2024-01-01T00:00:05Z')

    expect(result.kind).toBe('reasoning')
    if (result.kind === 'reasoning') {
      expect(result.thinkingSeconds).toBeNull()
    }
  })

  it('returns thinkingSeconds null for equal timestamps', () => {
    const msg = createMessage({
      source: 'omni_agent',
      content: [{ type: 'text', text: 'Same instant' }],
      metadata: { type: 'reasoning' },
    })
    msg.created_at = '2024-01-01T00:00:05Z'

    const result = parseMessage(msg, '2024-01-01T00:00:05Z')

    expect(result.kind).toBe('reasoning')
    if (result.kind === 'reasoning') {
      // diff is 0, which is not > 0, so thinkingSeconds should be null
      expect(result.thinkingSeconds).toBeNull()
    }
  })

  it('rounds thinkingSeconds to nearest integer', () => {
    const msg = createMessage({
      source: 'omni_agent',
      content: [{ type: 'text', text: 'Fractional timing' }],
      metadata: { type: 'reasoning' },
    })
    // 2.7 seconds difference → should round to 3
    msg.created_at = '2024-01-01T00:00:02.700Z'

    const result = parseMessage(msg, '2024-01-01T00:00:00Z')

    expect(result.kind).toBe('reasoning')
    if (result.kind === 'reasoning') {
      expect(result.thinkingSeconds).toBe(3)
    }
  })

  it('handles string content (non-array)', () => {
    const msg = createMessage({
      source: 'omni_agent',
      content: 'Plain string reasoning',
      metadata: { type: 'reasoning' },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('reasoning')
    if (result.kind === 'reasoning') {
      expect(result.content).toBe('Plain string reasoning')
    }
  })
})

// =============================================================================
// File Messages
// =============================================================================

describe('file messages', () => {
  it('parses metadata.type === "file" with files JSON', () => {
    const files = [
      {
        name: 'report.csv',
        url: '/files/user/uid/sid/rid/report.csv',
        timestamp: 1709561234.567,
        extension: 'csv',
        file_type: 'csv',
        action: 'created',
      },
    ]
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: { type: 'file', files: JSON.stringify(files) },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('file')
    if (result.kind === 'file') {
      expect(result.files).toHaveLength(1)
      expect(result.files[0].name).toBe('report.csv')
      expect(result.files[0].url).toBe('/files/user/uid/sid/rid/report.csv')
    }
  })

  it('parses multiple files', () => {
    const files = [
      {
        name: 'a.py',
        url: '/a.py',
        extension: 'py',
        file_type: 'code',
        action: 'created',
        timestamp: 1,
      },
      {
        name: 'b.md',
        url: '/b.md',
        extension: 'md',
        file_type: 'text',
        action: 'modified',
        timestamp: 2,
      },
    ]
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: { type: 'file', files: JSON.stringify(files) },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('file')
    if (result.kind === 'file') {
      expect(result.files).toHaveLength(2)
    }
  })

  it('falls through to text when files JSON is invalid', () => {
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: { type: 'file', files: 'not json' },
    })

    const result = parseMessage(msg)

    // Empty files array → parser falls through
    expect(result.kind).toBe('text')
  })

  it('marks message as summary when metadata.summary is true', () => {
    const files = [
      {
        name: 'report.csv',
        url: '/files/user/uid/sid/rid/report.csv',
        timestamp: 1,
        extension: 'csv',
        file_type: 'csv',
        action: 'created',
      },
    ]
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: { type: 'file', files: JSON.stringify(files), summary: true },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('file')
    if (result.kind === 'file') {
      expect(result.summary).toBe(true)
    }
  })

  it('does not set summary flag when metadata.summary is missing', () => {
    const files = [
      {
        name: 'report.csv',
        url: '/files/r.csv',
        timestamp: 1,
        extension: 'csv',
        file_type: 'csv',
        action: 'created',
      },
    ]
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: { type: 'file', files: JSON.stringify(files) },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('file')
    if (result.kind === 'file') {
      expect(result.summary).toBeUndefined()
    }
  })

  it('parses uploadedFiles from metadata.uploaded_files on summary', () => {
    const files = [
      {
        name: 'out.md',
        url: '/files/out.md',
        timestamp: 2,
        extension: 'md',
        file_type: 'code',
        action: 'created',
      },
    ]
    const uploaded = [
      {
        name: 'in.csv',
        url: '/files/in.csv',
        timestamp: 1,
        extension: 'csv',
        file_type: 'csv',
      },
    ]
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: {
        type: 'file',
        files: JSON.stringify(files),
        summary: true,
        uploaded_files: JSON.stringify(uploaded),
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('file')
    if (result.kind === 'file') {
      expect(result.summary).toBe(true)
      expect(result.uploadedFiles).toHaveLength(1)
      expect(result.uploadedFiles![0].name).toBe('in.csv')
    }
  })

  it('parses summary message that has only uploaded_files (no agent files)', () => {
    const uploaded = [
      {
        name: 'in.csv',
        url: '/files/in.csv',
        timestamp: 1,
        extension: 'csv',
        file_type: 'csv',
      },
    ]
    const msg = createMessage({
      source: 'system',
      content: 'File Generated',
      metadata: {
        type: 'file',
        files: JSON.stringify([]),
        summary: true,
        uploaded_files: JSON.stringify(uploaded),
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('file')
    if (result.kind === 'file') {
      expect(result.files).toEqual([])
      expect(result.uploadedFiles).toHaveLength(1)
    }
  })

  it('parses user message with attached_files metadata', () => {
    const attachedFiles = [
      { name: 'input.csv', path: '/files/user/uid/sid/rid/input.csv', uploaded: true },
    ]
    const msg = createMessage({
      source: 'user',
      content: 'Analyze this file',
      metadata: { attached_files: JSON.stringify(attachedFiles) },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('user')
    if (result.kind === 'user') {
      expect(result.content).toBe('Analyze this file')
      expect(result.attachedFiles).toHaveLength(1)
      expect(result.attachedFiles![0].name).toBe('input.csv')
    }
  })

  it('user message without attached_files has no attachedFiles', () => {
    const msg = createMessage({
      source: 'user',
      content: 'Hello',
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('user')
    if (result.kind === 'user') {
      expect(result.attachedFiles).toBeUndefined()
    }
  })

  it('parses user message with mounted_folder metadata', () => {
    const msg = createMessage({
      source: 'user',
      content: 'Start this task',
      metadata: {
        mounted_folder: {
          name: 'magentic-ui2.0',
          path: '/Users/weilishi/Code/magentic-ui2.0',
        },
      },
    })

    const result = parseMessage(msg)

    expect(result.kind).toBe('user')
    if (result.kind === 'user') {
      expect(result.mountedFolder).toEqual({
        name: 'magentic-ui2.0',
        path: '/Users/weilishi/Code/magentic-ui2.0',
      })
    }
  })
})
