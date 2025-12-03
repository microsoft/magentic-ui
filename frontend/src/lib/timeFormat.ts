/**
 * Time formatting utilities
 *
 * - formatRelativeShort: compact relative time for SessionCard
 *   ("Just now", "5m ago", "2h ago", "Yesterday", "Apr 27")
 * - formatChatSeparator: absolute time for in-chat timestamp dividers
 *   ("5:01 PM", "Yesterday 5:01 PM", "April 27 5:01 PM")
 * - exceedsChatGap: whether the gap between two ISO timestamps warrants a
 *   timestamp separator in the chat view.
 *
 * Date-portion output (e.g. "Apr 27", "April 27 5:01 PM") is locale-formatted
 * via `Intl.DateTimeFormat`, so the actual order/words depend on the user's
 * locale. The English examples in this file's docstrings are illustrative.
 */

/** Threshold (ms) above which a new timestamp separator is inserted in the chat view. */
export const CHAT_TIMESTAMP_GAP_MS = 10 * 60 * 1000 // 10 minutes

const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

/** Returns the start-of-day timestamp (in local time) for the given epoch ms. */
function startOfLocalDay(ms: number): number {
  const d = new Date(ms)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

/**
 * Coerce a timestamp input (ISO string, epoch ms, or nullish) to epoch ms.
 * Returns NaN for unparseable / nullish input so callers can short-circuit.
 */
function toEpochMs(input: string | number | null | undefined): number {
  if (input == null || input === '') return NaN
  if (typeof input === 'number') return input
  return new Date(input).getTime()
}

/**
 * Compact relative time for SessionCard.
 *
 * Calendar-day based: "Yesterday" wins over "Nh ago" once the day rolls over,
 * even if the literal gap is still under 24 hours (e.g. 11pm yesterday viewed
 * at 6am today shows "Yesterday", not "7h ago").
 *
 * Rules (English shown for illustration; date strings are locale-formatted):
 *   < 60s                       → "Just now"
 *   < 60m                       → "Nm ago"
 *   same calendar day, < 24h    → "Nh ago"
 *   yesterday (calendar)        → "Yesterday"
 *   same year                   → short month + day (e.g. "Apr 27")
 *   else                        → short month + day + year (e.g. "Apr 27, 2025")
 *
 * @param input ISO string, epoch ms, or nullish.
 * @param now Reference "now" in epoch ms. Defaults to `Date.now()`.
 * @param locale Optional BCP-47 locale tag for the date portion. Defaults to
 *   the user's locale; pass an explicit value (e.g. `'en-US'`) for tests.
 */
export function formatRelativeShort(
  input: string | number | null | undefined,
  now: number = Date.now(),
  locale?: string | string[]
): string {
  const then = toEpochMs(input)
  if (Number.isNaN(then)) return ''

  const diff = now - then
  if (diff < MINUTE_MS) return 'Just now'
  if (diff < HOUR_MS) return `${Math.floor(diff / MINUTE_MS)}m ago`

  const todayStart = startOfLocalDay(now)
  const thenStart = startOfLocalDay(then)
  const dayDiff = Math.round((todayStart - thenStart) / DAY_MS)

  if (dayDiff === 0) return `${Math.floor(diff / HOUR_MS)}h ago`
  if (dayDiff === 1) return 'Yesterday'

  const sameYear = new Date(then).getFullYear() === new Date(now).getFullYear()
  return new Date(then).toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  })
}

/**
 * Absolute timestamp for the chat view's inline divider.
 *
 * Rules (English shown for illustration; date/time portions are locale-formatted):
 *   today        → time only (e.g. "5:01 PM")
 *   yesterday    → "Yesterday " + time (e.g. "Yesterday 5:01 PM")
 *   same year    → long month + day + time (e.g. "April 27 5:01 PM")
 *   else         → long month + day + year + time (e.g. "April 27, 2025 5:01 PM")
 *
 * @param input ISO string or epoch ms.
 * @param now Reference "now" in epoch ms. Defaults to `Date.now()`.
 * @param locale Optional BCP-47 locale tag. Defaults to the user's locale;
 *   pass an explicit value (e.g. `'en-US'`) for tests.
 */
export function formatChatSeparator(
  input: string | number,
  now: number = Date.now(),
  locale?: string | string[]
): string {
  const then = toEpochMs(input)
  if (Number.isNaN(then)) return ''

  const time = new Date(then).toLocaleTimeString(locale, {
    hour: 'numeric',
    minute: '2-digit',
  })

  const todayStart = startOfLocalDay(now)
  const thenStart = startOfLocalDay(then)
  const dayDiff = Math.round((todayStart - thenStart) / DAY_MS)

  if (dayDiff === 0) return time
  if (dayDiff === 1) return `Yesterday ${time}`

  const sameYear = new Date(then).getFullYear() === new Date(now).getFullYear()
  const date = new Date(then).toLocaleDateString(locale, {
    month: 'long',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  })
  return `${date} ${time}`
}

/**
 * True iff the gap between two ISO timestamps strictly exceeds
 * `CHAT_TIMESTAMP_GAP_MS`. Returns true when `prevIso` is missing so callers
 * can use this for the leading separator as well.
 */
export function exceedsChatGap(
  prevIso: string | undefined | null,
  currentIso: string | undefined | null
): boolean {
  if (!currentIso) return false
  if (!prevIso) return true
  const prev = new Date(prevIso).getTime()
  const curr = new Date(currentIso).getTime()
  if (Number.isNaN(prev) || Number.isNaN(curr)) return false
  return curr - prev > CHAT_TIMESTAMP_GAP_MS
}
