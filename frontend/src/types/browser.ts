/**
 * Browser-related types shared across browser components and session views.
 */

/** Latest CUA action info for display in browser views */
export interface LatestCuaAction {
  /** Planned action (from toolArgs.thoughts) */
  thoughts?: string
  /** Completed action (from screenshot actionResult) */
  actionResult?: string
}
