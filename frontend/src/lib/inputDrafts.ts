/**
 * Per-session input draft storage.
 *
 * Module-level Map that survives component unmounts (e.g. dashboard round-trips)
 * but not full page refreshes. Keeps typed-but-unsent text per session.
 */
const inputDrafts = new Map<number, string>()

/** Get the stored draft for a session. */
export function getInputDraft(sessionId: number): string {
  return inputDrafts.get(sessionId) ?? ''
}

/** Save a draft for a session. Removes entry if value is empty. */
export function setInputDraft(sessionId: number, value: string) {
  if (value) {
    inputDrafts.set(sessionId, value)
  } else {
    inputDrafts.delete(sessionId)
  }
}

/** Clear the stored input draft for a session (e.g. after deletion or promotion). */
export function clearInputDraft(sessionId: number) {
  inputDrafts.delete(sessionId)
}
