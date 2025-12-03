/**
 * Unit tests for timeFormat utilities
 *
 * Tests cover:
 * - formatRelativeShort: thresholds for "Just now" / "Nm ago" / "Nh ago" /
 *   "Yesterday" / "MMM d" / "MMM d, yyyy"
 * - formatChatSeparator: today / Yesterday / same-year / cross-year formats
 * - exceedsChatGap: missing/equal/below/above-threshold timestamps
 *
 * All assertions pin `locale='en-US'` so the date/time strings are stable
 * across CI environments. The implementation defaults to the user's locale.
 */

import { describe, it, expect } from 'vitest'
import {
  formatRelativeShort,
  formatChatSeparator,
  exceedsChatGap,
  CHAT_TIMESTAMP_GAP_MS,
} from '@/lib/timeFormat'

const LOCALE = 'en-US'

// Fixed reference time: 2026-04-29 14:00:00 local
const NOW = new Date(2026, 3, 29, 14, 0, 0).getTime()

const at = (year: number, month: number, day: number, h = 14, m = 0): string =>
  new Date(year, month, day, h, m, 0).toISOString()

// =============================================================================
// formatRelativeShort
// =============================================================================

describe('formatRelativeShort', () => {
  it('returns empty string for nullish input', () => {
    expect(formatRelativeShort(null, NOW)).toBe('')
    expect(formatRelativeShort(undefined, NOW)).toBe('')
    expect(formatRelativeShort('', NOW)).toBe('')
  })

  it('returns empty string for unparseable input', () => {
    expect(formatRelativeShort('not-a-date', NOW)).toBe('')
  })

  it('accepts epoch ms (number) input directly', () => {
    expect(formatRelativeShort(NOW - 30_000, NOW)).toBe('Just now')
    expect(formatRelativeShort(NOW - 5 * 60_000, NOW)).toBe('5m ago')
  })

  it('shows "Just now" within the first minute', () => {
    expect(formatRelativeShort(new Date(NOW - 30_000).toISOString(), NOW)).toBe('Just now')
  })

  it('shows minutes for gaps under an hour', () => {
    expect(formatRelativeShort(new Date(NOW - 5 * 60_000).toISOString(), NOW)).toBe('5m ago')
    expect(formatRelativeShort(new Date(NOW - 59 * 60_000).toISOString(), NOW)).toBe('59m ago')
  })

  it('shows hours for gaps within today', () => {
    expect(formatRelativeShort(new Date(NOW - 2 * 3600_000).toISOString(), NOW)).toBe('2h ago')
  })

  it('shows "Yesterday" once the gap crosses 24h into the previous calendar day', () => {
    // Yesterday (Apr 28) 08:00 local → 30h before NOW
    const ts = new Date(2026, 3, 28, 8, 0, 0).toISOString()
    expect(formatRelativeShort(ts, NOW)).toBe('Yesterday')
  })

  it('shows "Yesterday" even when the literal gap is less than 24 hours (calendar day rolled over)', () => {
    // Yesterday 23:00 local — only 15h before NOW (14:00) but it is the previous calendar day
    const ts = new Date(2026, 3, 28, 23, 0, 0).toISOString()
    expect(formatRelativeShort(ts, NOW)).toBe('Yesterday')
  })

  it('shows "MMM d" for any same-year date older than yesterday (no weekday tier)', () => {
    // 3 days ago = Sunday Apr 26
    const ts = new Date(2026, 3, 26, 10, 0, 0).toISOString()
    expect(formatRelativeShort(ts, NOW, LOCALE)).toBe('Apr 26')
  })

  it('shows "MMM d" for older same-year dates', () => {
    const ts = at(2026, 0, 15) // Jan 15 same year
    expect(formatRelativeShort(ts, NOW, LOCALE)).toBe('Jan 15')
  })

  it('shows "MMM d, yyyy" for prior years', () => {
    const ts = at(2024, 5, 10)
    expect(formatRelativeShort(ts, NOW, LOCALE)).toBe('Jun 10, 2024')
  })
})

// =============================================================================
// formatChatSeparator
// =============================================================================

describe('formatChatSeparator', () => {
  it('returns empty string for unparseable input', () => {
    expect(formatChatSeparator('not-a-date', NOW)).toBe('')
  })

  it('shows time-only for today', () => {
    const ts = new Date(2026, 3, 29, 17, 1, 0).toISOString()
    expect(formatChatSeparator(ts, NOW, LOCALE)).toBe('5:01 PM')
  })

  it('prefixes "Yesterday" for the previous calendar day', () => {
    const ts = new Date(2026, 3, 28, 17, 1, 0).toISOString()
    expect(formatChatSeparator(ts, NOW, LOCALE)).toBe('Yesterday 5:01 PM')
  })

  it('uses long-month + day for same-year older dates', () => {
    const ts = new Date(2026, 0, 15, 17, 1, 0).toISOString()
    expect(formatChatSeparator(ts, NOW, LOCALE)).toBe('January 15 5:01 PM')
  })

  it('appends year for cross-year dates', () => {
    const ts = new Date(2024, 5, 10, 17, 1, 0).toISOString()
    expect(formatChatSeparator(ts, NOW, LOCALE)).toBe('June 10, 2024 5:01 PM')
  })
})

// =============================================================================
// exceedsChatGap
// =============================================================================

describe('exceedsChatGap', () => {
  it('returns true when prevIso is missing (leading separator)', () => {
    expect(exceedsChatGap(undefined, new Date().toISOString())).toBe(true)
    expect(exceedsChatGap(null, new Date().toISOString())).toBe(true)
  })

  it('returns false when currentIso is missing', () => {
    expect(exceedsChatGap(new Date().toISOString(), undefined)).toBe(false)
  })

  it('returns false when both timestamps are unparseable', () => {
    expect(exceedsChatGap('bad', 'also-bad')).toBe(false)
  })

  it('returns false when gap is exactly the threshold', () => {
    const a = new Date(NOW).toISOString()
    const b = new Date(NOW + CHAT_TIMESTAMP_GAP_MS).toISOString()
    expect(exceedsChatGap(a, b)).toBe(false)
  })

  it('returns true when gap exceeds the threshold', () => {
    const a = new Date(NOW).toISOString()
    const b = new Date(NOW + CHAT_TIMESTAMP_GAP_MS + 1).toISOString()
    expect(exceedsChatGap(a, b)).toBe(true)
  })

  it('returns false when gap is below the threshold', () => {
    const a = new Date(NOW).toISOString()
    const b = new Date(NOW + 60_000).toISOString()
    expect(exceedsChatGap(a, b)).toBe(false)
  })
})
