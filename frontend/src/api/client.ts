/**
 * API Client
 *
 * Base HTTP client for communicating with the backend API.
 * Handles the standard response wrapper format: { status: boolean, data: T, message?: string }
 */
import { API_BASE_URL } from '@/lib/constants'
import { useBackendHealthStore } from '@/stores/backendHealthStore'
import { getAuthHeaders } from './auth'

// =============================================================================
// URL Helpers
// =============================================================================

/**
 * Get the WebSocket base URL
 * WebSocket requires full URL with protocol (ws:// or wss://)
 */
export function getWsBaseUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api`
}

// =============================================================================
// Types
// =============================================================================

/**
 * Standard API response wrapper from backend
 */
export interface ApiResponse<T> {
  status: boolean
  data: T
  message?: string
}

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
  statusCode?: number
  response?: unknown

  constructor(message: string, statusCode?: number, response?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.response = response
  }
}

// =============================================================================
// API Client
// =============================================================================

/**
 * Format an error response body into a user-readable message.
 *
 * Handles:
 * - String `message` or `detail` fields (FastAPI HTTPException style)
 * - Array `detail` (FastAPI Pydantic 422 — list of `{loc, msg, type, ...}`)
 *
 * Returns `null` when no recognizable error field is present.
 */
function formatErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  const obj = body as Record<string, unknown>
  if (typeof obj.message === 'string') return obj.message
  const { detail } = obj
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // Pydantic validation errors
    const parts = detail
      .map((e) => {
        if (e && typeof e === 'object') {
          const item = e as Record<string, unknown>
          const loc = Array.isArray(item.loc) ? item.loc.filter((x) => x !== 'body').join('.') : ''
          const msg = typeof item.msg === 'string' ? item.msg : JSON.stringify(item)
          return loc ? `${loc}: ${msg}` : msg
        }
        return String(e)
      })
      .filter(Boolean)
    if (parts.length > 0) return parts.join('; ')
  }
  return null
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

/**
 * Make an API request and handle the response wrapper
 *
 * @param endpoint - API endpoint (without /api prefix)
 * @param options - Fetch options
 * @returns Unwrapped data from the response
 * @throws ApiError if request fails or status is false
 */
async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...options.headers,
  }

  const config: RequestInit = {
    ...options,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  }

  let response: Response

  try {
    response = await fetch(url, config)
  } catch (error) {
    // Skip health updates for intentional cancellations (AbortController,
    // React Query unmount cleanup) — they don't say anything about backend
    // reachability and would otherwise flip the global banner spuriously.
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    // Network/CORS/offline — backend unreachable.
    useBackendHealthStore.getState().setReachable(false)
    throw new ApiError(error instanceof Error ? error.message : 'Network error', undefined, error)
  }

  // 5xx → backend down; anything else (incl. 4xx) → backend responding.
  if (response.status >= 500) {
    useBackendHealthStore.getState().setReachable(false)
  } else {
    useBackendHealthStore.getState().setReachable(true)
  }

  // Handle HTTP errors (4xx, 5xx)
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorData = await response.json()
      errorMessage = formatErrorMessage(errorData) ?? errorMessage
    } catch {
      // Response body is not JSON, use default message
    }
    throw new ApiError(errorMessage, response.status)
  }

  // Parse JSON response
  let data: ApiResponse<T>
  try {
    data = await response.json()
  } catch {
    throw new ApiError('Invalid JSON response', response.status)
  }

  // Handle API-level errors (status: false in wrapper)
  if (!data.status) {
    throw new ApiError(data.message || 'API request failed', response.status, data)
  }

  return data.data
}

/**
 * API client with typed methods
 */
export const apiClient = {
  /**
   * GET request
   */
  get<T>(endpoint: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'GET' })
  },

  /**
   * POST request
   */
  post<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'POST', body })
  },

  /**
   * PUT request
   */
  put<T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'method'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'PUT', body })
  },

  /**
   * DELETE request
   */
  delete<T>(endpoint: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'DELETE' })
  },
}
