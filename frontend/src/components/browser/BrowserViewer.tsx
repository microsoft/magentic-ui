/**
 * BrowserViewer Component
 *
 * Wraps react-vnc VncScreen for browser viewing.
 * Handles connection status, clipboard sync, and displays appropriate
 * placeholder when disconnected.
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import { VncScreen, type VncScreenHandle } from 'react-vnc'
import { cn } from '@/lib/utils'

// =============================================================================
// Types
// =============================================================================

type VncConnectionStatus = 'disconnected' | 'connecting' | 'connected'

// Connection timeout in milliseconds
const CONNECTION_TIMEOUT_MS = 10000

interface BrowserViewerProps {
  url: string
  /** Per-slot RFB password used during the noVNC handshake. */
  password: string
  viewOnly?: boolean
  className?: string
  /** Called when connection is established */
  onConnect?: () => void
  onDisconnect?: () => void
}

// =============================================================================
// Component
// =============================================================================

export function BrowserViewer({
  url,
  password,
  viewOnly = true,
  className,
  onConnect,
  onDisconnect,
}: BrowserViewerProps) {
  // Start in 'connecting' state since VncScreen begins connecting on mount
  const [status, setStatus] = useState<VncConnectionStatus>('connecting')
  const vncRef = useRef<VncScreenHandle>(null)
  // Track connection timeout timer for cleanup
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clear connection timeout timer
  const clearConnectionTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  // Reset to connecting state when URL changes (render-time state adjustment)
  const [prevUrl, setPrevUrl] = useState(url)
  if (prevUrl !== url) {
    setPrevUrl(url)
    setStatus('connecting')
  }

  // Connection timeout - show error if not connected within timeout
  useEffect(() => {
    timeoutRef.current = setTimeout(() => {
      setStatus((current) => {
        if (current === 'connecting') {
          console.debug('[BrowserViewer] Connection timeout')
          return 'disconnected'
        }
        return current
      })
    }, CONNECTION_TIMEOUT_MS)

    return clearConnectionTimeout
  }, [url, clearConnectionTimeout])

  // Track container ref for resize detection
  const containerRef = useRef<HTMLDivElement>(null)

  // Trigger VNC scale update when container size changes (e.g., sidebar toggle)
  // noVNC's internal ResizeObserver watches its own canvas, not our container.
  // We use the public scaleViewport property toggle to force a recalculation.
  useEffect(() => {
    const container = containerRef.current
    const rfb = vncRef.current?.rfb
    if (!container || !rfb) return

    const resizeObserver = new ResizeObserver(() => {
      // Toggle scaleViewport to trigger noVNC's internal _updateScale()
      // This is the public API way to force a scale recalculation
      if (rfb.scaleViewport) {
        rfb.scaleViewport = false
        rfb.scaleViewport = true
      }
    })
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [status]) // Re-attach when status changes to 'connected' (rfb becomes available)

  // Update RFB viewOnly when prop changes
  // react-vnc may not automatically update this on prop change
  // Note: Modifying rfb properties is intentional - this is noVNC's API
  useEffect(() => {
    const rfb = vncRef.current?.rfb
    if (rfb && rfb.viewOnly !== viewOnly) {
      console.debug('[BrowserViewer] Updating viewOnly:', viewOnly)
      // eslint-disable-next-line react-hooks/immutability -- noVNC API requires property mutation
      rfb.viewOnly = viewOnly
    }
    // When taking control, move focus to the VNC canvas. The React re-renders
    // triggered by the controlState transition often park focus on <body>,
    // and noVNC's keyboard listener is attached to the canvas — so without
    // this the user has to click the canvas first before typing reaches the
    // VM. Only steal focus when it is already on <body>: if the user is
    // typing into another input (e.g. the chat textarea), leave it alone.
    if (!viewOnly && document.activeElement === document.body) {
      vncRef.current?.focus()
    }
  }, [viewOnly])

  // Clipboard sync: VM → User
  // When the VM clipboard changes, write to the user's clipboard
  const handleClipboard = useCallback((e: { detail: { text: string } }) => {
    navigator.clipboard.writeText(e.detail.text).catch(() => {
      // Clipboard write can fail if page is not focused or permission denied
    })
  }, [])

  // Clipboard sync: User → VM
  // Sync host clipboard to VM on canvas focus (covers keyboard paste since
  // user must click into VNC first) and on right-click context menu paste.
  useEffect(() => {
    if (viewOnly || status !== 'connected') return

    const container = containerRef.current
    const canvas = container?.querySelector('canvas')
    if (!canvas) return

    // Read host clipboard and send to VM
    const syncClipboardToVM = async () => {
      try {
        const text = await navigator.clipboard.readText()
        if (text) {
          vncRef.current?.clipboardPaste(text)
        }
      } catch {
        // Permission denied or page not focused
      }
    }

    // Right-click menu paste (scoped to container, not document)
    const handlePaste = (e: Event) => {
      const clipboardEvent = e as ClipboardEvent
      const text = clipboardEvent.clipboardData?.getData('text/plain')
      if (text) {
        vncRef.current?.clipboardPaste(text)
      }
    }

    canvas.addEventListener('focus', syncClipboardToVM)
    container?.addEventListener('paste', handlePaste)
    return () => {
      canvas.removeEventListener('focus', syncClipboardToVM)
      container?.removeEventListener('paste', handlePaste)
    }
  }, [viewOnly, status])

  const handleConnect = useCallback(() => {
    console.debug('[BrowserViewer] Connected to VNC')
    clearConnectionTimeout()
    setStatus('connected')
    onConnect?.()
  }, [onConnect, clearConnectionTimeout])

  const handleDisconnect = useCallback(() => {
    console.debug('[BrowserViewer] Disconnected from VNC')
    setStatus('disconnected')
    onDisconnect?.()
  }, [onDisconnect])

  const handleSecurityFailure = useCallback(() => {
    console.debug('[BrowserViewer] Security failure')
    setStatus('disconnected')
  }, [])

  return (
    <div ref={containerRef} className={cn('bg-card relative overflow-hidden', className)}>
      <VncScreen
        ref={vncRef}
        url={url}
        viewOnly={viewOnly}
        scaleViewport
        showDotCursor={false}
        background="var(--card)"
        rfbOptions={{ credentials: { password } }}
        style={{
          width: '100%',
          height: '100%',
        }}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        onSecurityFailure={handleSecurityFailure}
        onClipboard={handleClipboard}
      />

      {/* Status Overlay */}
      {status !== 'connected' && (
        <div className="bg-card absolute inset-0 flex items-center justify-center">
          <span className="text-muted-foreground text-sm">
            {status === 'connecting' ? 'Connecting...' : 'Browser not available'}
          </span>
        </div>
      )}
    </div>
  )
}
