/**
 * Tests for folderPreferencesStore
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock the settings API before importing the store
vi.mock('@/api/settings', () => ({
  listTrustedFolders: vi.fn().mockResolvedValue([]),
  addTrustedFolder: vi
    .fn()
    .mockImplementation((name: string, path: string) =>
      Promise.resolve({ id: Date.now(), name, path })
    ),
  removeTrustedFolder: vi.fn().mockResolvedValue(undefined),
}))

import { useFolderPreferencesStore } from '@/stores/folderPreferencesStore'
import type { FolderInfo } from '@/types'

describe('folderPreferencesStore', () => {
  beforeEach(() => {
    // Reset to initial state before each test
    useFolderPreferencesStore.setState({ trustedFolders: [], loaded: true })
  })

  // ---------------------------------------------------------------------------
  // Initial state
  // ---------------------------------------------------------------------------

  it('has empty trustedFolders initially', () => {
    const state = useFolderPreferencesStore.getState()
    expect(state.trustedFolders).toEqual([])
  })

  // ---------------------------------------------------------------------------
  // addTrustedFolder
  // ---------------------------------------------------------------------------

  describe('addTrustedFolder', () => {
    it('adds a folder to the trusted list', async () => {
      const folder: FolderInfo = { name: 'my-project', path: 'my-project' }
      useFolderPreferencesStore.getState().addTrustedFolder(folder)

      // Wait for async API call to resolve
      await vi.waitFor(() => {
        const state = useFolderPreferencesStore.getState()
        expect(state.trustedFolders).toHaveLength(1)
      })
      expect(useFolderPreferencesStore.getState().trustedFolders[0].path).toBe('my-project')
    })

    it('adds multiple folders', async () => {
      const store = useFolderPreferencesStore.getState()
      store.addTrustedFolder({ name: 'project-a', path: 'project-a' })
      store.addTrustedFolder({ name: 'project-b', path: 'project-b' })

      await vi.waitFor(() => {
        expect(useFolderPreferencesStore.getState().trustedFolders).toHaveLength(2)
      })
    })

    it('does not add duplicate folders (same path)', async () => {
      const store = useFolderPreferencesStore.getState()
      store.addTrustedFolder({ name: 'my-project', path: 'my-project' })

      await vi.waitFor(() => {
        expect(useFolderPreferencesStore.getState().trustedFolders).toHaveLength(1)
      })

      // Try adding again — should be skipped locally
      useFolderPreferencesStore
        .getState()
        .addTrustedFolder({ name: 'my-project', path: 'my-project' })

      // Still 1
      await vi.waitFor(() => {
        expect(useFolderPreferencesStore.getState().trustedFolders).toHaveLength(1)
      })
    })

    it('allows folders with different paths but same name', async () => {
      const store = useFolderPreferencesStore.getState()
      store.addTrustedFolder({ name: 'src', path: '/Users/alice/src' })
      store.addTrustedFolder({ name: 'src', path: '/Users/bob/src' })

      await vi.waitFor(() => {
        expect(useFolderPreferencesStore.getState().trustedFolders).toHaveLength(2)
      })
    })
  })

  // ---------------------------------------------------------------------------
  // removeTrustedFolder
  // ---------------------------------------------------------------------------

  describe('removeTrustedFolder', () => {
    it('removes a folder by path', () => {
      useFolderPreferencesStore.setState({
        trustedFolders: [
          { id: 1, name: 'project-a', path: 'project-a' },
          { id: 2, name: 'project-b', path: 'project-b' },
        ],
      })

      useFolderPreferencesStore.getState().removeTrustedFolder('project-a')

      const state = useFolderPreferencesStore.getState()
      expect(state.trustedFolders).toHaveLength(1)
      expect(state.trustedFolders[0].path).toBe('project-b')
    })

    it('does nothing when removing non-existent path', () => {
      useFolderPreferencesStore.setState({
        trustedFolders: [{ id: 1, name: 'project-a', path: 'project-a' }],
      })

      useFolderPreferencesStore.getState().removeTrustedFolder('non-existent')

      const state = useFolderPreferencesStore.getState()
      expect(state.trustedFolders).toHaveLength(1)
    })

    it('removes the correct folder when multiple exist', () => {
      useFolderPreferencesStore.setState({
        trustedFolders: [
          { id: 1, name: 'a', path: 'path-a' },
          { id: 2, name: 'b', path: 'path-b' },
          { id: 3, name: 'c', path: 'path-c' },
        ],
      })

      useFolderPreferencesStore.getState().removeTrustedFolder('path-b')

      const state = useFolderPreferencesStore.getState()
      expect(state.trustedFolders).toHaveLength(2)
      expect(state.trustedFolders.map((f) => f.path)).toEqual(['path-a', 'path-c'])
    })
  })

  // ---------------------------------------------------------------------------
  // isTrusted
  // ---------------------------------------------------------------------------

  describe('isTrusted', () => {
    it('returns false for empty list', () => {
      expect(useFolderPreferencesStore.getState().isTrusted('anything')).toBe(false)
    })

    it('returns true for a trusted folder', () => {
      useFolderPreferencesStore.setState({
        trustedFolders: [{ id: 1, name: 'my-project', path: 'my-project' }],
      })
      expect(useFolderPreferencesStore.getState().isTrusted('my-project')).toBe(true)
    })

    it('returns false for an untrusted folder', () => {
      useFolderPreferencesStore.setState({
        trustedFolders: [{ id: 1, name: 'my-project', path: 'my-project' }],
      })
      expect(useFolderPreferencesStore.getState().isTrusted('other-project')).toBe(false)
    })

    it('returns false after folder is removed', () => {
      useFolderPreferencesStore.setState({
        trustedFolders: [{ id: 1, name: 'my-project', path: 'my-project' }],
      })
      useFolderPreferencesStore.getState().removeTrustedFolder('my-project')
      expect(useFolderPreferencesStore.getState().isTrusted('my-project')).toBe(false)
    })
  })
})
