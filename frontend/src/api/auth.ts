/**
 * Browser-side session auth.
 *
 * The backend injects a random session token into index.html as
 * `window.__MAGUI_TOKEN__`. We read it here and attach it to every
 * outgoing API request and WebSocket handshake. When the token is
 * absent (Vite dev server serving its own HTML) the backend accepts
 * requests based on the dev-origin bypass instead.
 */

declare global {
  interface Window {
    __MAGUI_TOKEN__?: string
  }
}

/** Keep in sync with `WS_PROTOCOL_TAG` in `backend/web/auth.py`. */
export const WS_PROTOCOL_TAG = 'magui.auth.bearer'

export function getSessionToken(): string {
  return window.__MAGUI_TOKEN__ ?? ''
}

/** Bearer header for fetch. Empty when there is no injected token (dev). */
export function getAuthHeaders(): Record<string, string> {
  const token = getSessionToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Open a WebSocket with the token carried in `Sec-WebSocket-Protocol`
 * (the only client-controlled handshake header in the browser). When
 * no token is present we open an unauth'd socket and rely on the
 * backend's dev-origin bypass.
 */
export function createAuthenticatedWebSocket(url: string): WebSocket {
  const token = getSessionToken()
  return token ? new WebSocket(url, [WS_PROTOCOL_TAG, token]) : new WebSocket(url)
}
