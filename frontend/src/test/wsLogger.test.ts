/**
 * Tests for `scrubForLog` — must recursively redact sensitive keys before
 * the WebSocket logger writes them to the browser console.
 */
import { describe, it, expect } from 'vitest'
import { scrubForLog } from '@/lib/wsLogger'

describe('scrubForLog', () => {
  it('redacts top-level password', () => {
    expect(scrubForLog({ password: 'secret-token' })).toEqual({
      password: '***REDACTED***',
    })
  })

  it('redacts nested password (metadata depth)', () => {
    expect(
      scrubForLog({
        type: 'message',
        data: { metadata: { password: 'secret-token' } },
      })
    ).toEqual({
      type: 'message',
      data: { metadata: { password: '***REDACTED***' } },
    })
  })

  it('redacts deeply nested password', () => {
    expect(scrubForLog({ a: { b: { c: { d: { password: 'secret-token' } } } } })).toEqual({
      a: { b: { c: { d: { password: '***REDACTED***' } } } },
    })
  })

  it('redacts password inside list of dicts', () => {
    expect(
      scrubForLog({
        items: [{ password: 'a' }, { password: 'b' }, { other: 'c' }],
      })
    ).toEqual({
      items: [{ password: '***REDACTED***' }, { password: '***REDACTED***' }, { other: 'c' }],
    })
  })

  it('redacts all sensitive keys (password, token, api_key, secret)', () => {
    expect(
      scrubForLog({
        password: 'p',
        token: 't',
        api_key: 'k',
        secret: 's',
        normal: 'n',
      })
    ).toEqual({
      password: '***REDACTED***',
      token: '***REDACTED***',
      api_key: '***REDACTED***',
      secret: '***REDACTED***',
      normal: 'n',
    })
  })

  it('matches sensitive keys case-insensitively', () => {
    expect(scrubForLog({ PASSWORD: 'x', Token: 'y', API_KEY: 'z' })).toEqual({
      PASSWORD: '***REDACTED***',
      Token: '***REDACTED***',
      API_KEY: '***REDACTED***',
    })
  })

  it('leaves non-sensitive keys unchanged', () => {
    const input = { username: 'u', port: 9999, url: 'http://x' }
    expect(scrubForLog(input)).toEqual(input)
  })

  it('passes primitives through unchanged', () => {
    expect(scrubForLog('hello')).toBe('hello')
    expect(scrubForLog(42)).toBe(42)
    expect(scrubForLog(true)).toBe(true)
    expect(scrubForLog(null)).toBeNull()
    expect(scrubForLog(undefined)).toBeUndefined()
    expect(scrubForLog([1, 2, 3])).toEqual([1, 2, 3])
  })

  it('passes empty structures through unchanged', () => {
    expect(scrubForLog({})).toEqual({})
    expect(scrubForLog([])).toEqual([])
  })

  it('redacts the real browser_address message shape', () => {
    const msg = {
      type: 'message',
      data: {
        source: 'web_surfer',
        content: [{ type: 'text', text: 'Browser ready at noVNC port 59253' }],
        metadata: {
          source: 'web_surfer',
          type: 'browser_address',
          novnc_port: '59253',
          playwright_port: '51305',
          password: 'secret-token',
        },
      },
    }
    const result = scrubForLog(msg) as {
      data: { metadata: { password: string; novnc_port: string; type: string } }
    }
    expect(result.data.metadata.password).toBe('***REDACTED***')
    expect(result.data.metadata.novnc_port).toBe('59253') // unchanged
    expect(result.data.metadata.type).toBe('browser_address') // unchanged
  })

  it('does not mutate the original input', () => {
    const msg = { password: 'secret-token' }
    scrubForLog(msg)
    expect(msg).toEqual({ password: 'secret-token' }) // unchanged
  })
})
