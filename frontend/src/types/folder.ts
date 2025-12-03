/**
 * Folder Mounting Types
 *
 * Types for the "Work in Folder" feature that allows users to mount
 * a local folder for agent access.
 */

/** Folder reference — used for both session mounting and trusted folder preferences */
export interface FolderInfo {
  /** Display name (last segment of the path) */
  name: string
  /** Folder path — used for identity/matching and sent to backend */
  path: string
}
