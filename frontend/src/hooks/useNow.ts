/**
 * useNow — periodic ticker for relative-time displays.
 *
 * Returns the current epoch ms and triggers a re-render every `intervalMs`
 * milliseconds (default 30s). Use this to keep `formatRelativeShort` outputs
 * fresh ("Just now" → "1m ago" → "2m ago" …) without waiting for unrelated
 * state changes to re-render the component.
 *
 * The default interval is small enough that "Just now" (which lasts up to 60s)
 * never goes more than ~30s stale, but large enough to avoid wasted renders.
 */
import { useEffect, useState } from 'react'

const DEFAULT_INTERVAL_MS = 30 * 1000

export function useNow(intervalMs: number = DEFAULT_INTERVAL_MS): number {
  const [now, setNow] = useState<number>(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])

  return now
}
