/**
 * Backend health endpoint.
 *
 * Used by `useBackendHealthPolling`. We don't care about the response
 * shape — the `request()` wrapper in `client.ts` updates the health
 * store as a side effect, so a successful call is enough.
 */
import { apiClient } from './client'

export function pingBackend(): Promise<unknown> {
  return apiClient.get<unknown>('/health')
}
