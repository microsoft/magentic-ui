/**
 * API Client Tests
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { apiClient, ApiError } from '@/api/client'
import { API_BASE_URL } from '@/lib/constants'

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

describe('apiClient', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  describe('API_BASE_URL', () => {
    it('is /api', () => {
      expect(API_BASE_URL).toBe('/api')
    })
  })

  describe('get', () => {
    it('returns data on successful response', async () => {
      const mockData = { id: 1, name: 'Test Session' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: true, data: mockData }),
      })

      const result = await apiClient.get('/sessions/1')

      expect(result).toEqual(mockData)
      expect(mockFetch).toHaveBeenCalledWith('/api/sessions/1', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: undefined,
      })
    })

    it('throws ApiError when status is false', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: false, message: 'Not found' }),
      })

      await expect(apiClient.get('/sessions/999')).rejects.toThrow(ApiError)
      await expect(apiClient.get('/sessions/999')).rejects.toThrow('Not found')
    })

    it('throws ApiError on HTTP error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () => Promise.resolve({ message: 'Session not found' }),
      })

      await expect(apiClient.get('/sessions/999')).rejects.toThrow('Session not found')
    })

    it('throws ApiError on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network failure'))

      await expect(apiClient.get('/sessions/1')).rejects.toThrow('Network failure')
    })

    it('throws ApiError on invalid JSON response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.reject(new Error('Invalid JSON')),
      })

      await expect(apiClient.get('/sessions/1')).rejects.toThrow('Invalid JSON response')
    })
  })

  describe('post', () => {
    it('sends JSON body and returns data', async () => {
      const mockData = { id: 2, name: 'New Session' }
      const requestBody = { name: 'New Session', user_id: 'user@test.com' }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: true, data: mockData }),
      })

      const result = await apiClient.post('/sessions/', requestBody)

      expect(result).toEqual(mockData)
      expect(mockFetch).toHaveBeenCalledWith('/api/sessions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })
    })

    it('handles POST without body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: true, data: {} }),
      })

      await apiClient.post('/sessions/1/start')

      expect(mockFetch).toHaveBeenCalledWith('/api/sessions/1/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: undefined,
      })
    })
  })

  describe('put', () => {
    it('sends PUT request with body', async () => {
      const mockData = { id: 1, name: 'Updated Session' }
      const requestBody = { name: 'Updated Session' }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: true, data: mockData }),
      })

      const result = await apiClient.put('/sessions/1', requestBody)

      expect(result).toEqual(mockData)
      expect(mockFetch).toHaveBeenCalledWith('/api/sessions/1', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })
    })
  })

  describe('delete', () => {
    it('sends DELETE request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: true, data: null }),
      })

      await apiClient.delete('/sessions/1')

      expect(mockFetch).toHaveBeenCalledWith('/api/sessions/1', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: undefined,
      })
    })
  })

  describe('error formatting', () => {
    it('uses string `detail` from FastAPI HTTPException', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        json: () =>
          Promise.resolve({ detail: 'Missing required endpoint(s) for all: orchestrator' }),
      })

      await expect(apiClient.post('/onboarding/verify')).rejects.toThrow(
        'Missing required endpoint(s) for all: orchestrator'
      )
    })

    it('formats array `detail` from FastAPI 422 with loc + msg', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        statusText: 'Unprocessable Entity',
        json: () =>
          Promise.resolve({
            detail: [
              {
                type: 'string_type',
                loc: ['body', 'orchestrator', 'base_url'],
                msg: 'Input should be a valid string',
                input: null,
              },
              {
                type: 'value_error',
                loc: ['body', 'web_surfer', 'model'],
                msg: 'must not be empty or whitespace',
                input: '',
              },
            ],
          }),
      })

      await expect(apiClient.post('/onboarding/verify')).rejects.toThrow(
        'orchestrator.base_url: Input should be a valid string; web_surfer.model: must not be empty or whitespace'
      )
    })

    it('falls back to default HTTP message when body has no recognizable fields', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({ unrelated: 'value' }),
      })

      await expect(apiClient.post('/onboarding/verify')).rejects.toThrow(
        'HTTP 500: Internal Server Error'
      )
    })
  })
})

describe('apiClient auth header', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    delete window.__MAGUI_TOKEN__
  })

  it('attaches Authorization: Bearer <token> when token is injected', async () => {
    window.__MAGUI_TOKEN__ = 'injected-token-xyz'
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: true, data: null }),
    })

    await apiClient.get('/sessions')

    const [, config] = mockFetch.mock.calls[0]
    expect((config.headers as Record<string, string>).Authorization).toBe(
      'Bearer injected-token-xyz'
    )
  })

  it('omits Authorization when no token is injected (dev mode)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: true, data: null }),
    })

    await apiClient.get('/sessions')

    const [, config] = mockFetch.mock.calls[0]
    expect((config.headers as Record<string, string>).Authorization).toBeUndefined()
  })
})

describe('ApiError', () => {
  it('has correct name and message', () => {
    const error = new ApiError('Test error', 404)

    expect(error.name).toBe('ApiError')
    expect(error.message).toBe('Test error')
    expect(error.statusCode).toBe(404)
  })

  it('stores response data', () => {
    const responseData = { status: false, message: 'Error' }
    const error = new ApiError('Test error', 400, responseData)

    expect(error.response).toEqual(responseData)
  })
})
