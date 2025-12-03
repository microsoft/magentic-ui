/**
 * Tests for ModelSettings reducer.
 */
import { describe, it, expect } from 'vitest'
import {
  deriveAgentMode,
  modelSettingsReducer as reducer,
  modelSettingsInitialState as initialState,
  type ModelSettingsState,
  type FormConfig,
} from '@/components/settings/modelSettingsReducer'

// =============================================================================
// Helpers
// =============================================================================

const ORCH: FormConfig = {
  endpointUrl: 'http://localhost:6000/v1',
  modelName: 'magenticbrain-v1',
  apiKey: 'key1',
}

const WS: FormConfig = {
  endpointUrl: 'http://localhost:5000/v1',
  modelName: 'fara-v1',
  apiKey: 'key2',
}

const EMPTY: FormConfig = { endpointUrl: '', modelName: '', apiKey: '' }

function loadedState(
  agentMode: 'all' | 'omniagent_only' | 'websurfer_only' = 'all',
  orchestrator: FormConfig = ORCH,
  webSurfer: FormConfig = WS
): ModelSettingsState {
  return reducer(initialState, {
    type: 'loaded',
    orchestrator,
    webSurfer,
    agentMode,
  })
}

// =============================================================================
// Tests
// =============================================================================

describe('deriveAgentMode', () => {
  it('returns "all" when both enabled', () => {
    expect(deriveAgentMode(true, true)).toBe('all')
  })
  it('returns "omniagent_only" when only orchestrator enabled', () => {
    expect(deriveAgentMode(true, false)).toBe('omniagent_only')
  })
  it('returns "websurfer_only" when only web-surfer enabled', () => {
    expect(deriveAgentMode(false, true)).toBe('websurfer_only')
  })
  it('returns null when neither enabled', () => {
    expect(deriveAgentMode(false, false)).toBeNull()
  })
})

describe('ModelSettings reducer', () => {
  describe('initial state', () => {
    it('starts in loading state with empty forms and unchecked flags', () => {
      expect(initialState.loading).toBe(true)
      expect(initialState.draft.orchestrator.endpointUrl).toBe('')
      expect(initialState.draft.webSurfer.endpointUrl).toBe('')
      expect(initialState.draft.orchEnabled).toBe(false)
      expect(initialState.draft.wsEnabled).toBe(false)
      expect(initialState.verified).toBe(false)
      expect(initialState.errors).toEqual([])
    })
  })

  describe('loaded', () => {
    it('derives both checkboxes from agent_mode=all when both configs are saved', () => {
      const state = loadedState('all')
      expect(state.loading).toBe(false)
      expect(state.draft.orchEnabled).toBe(true)
      expect(state.draft.wsEnabled).toBe(true)
      expect(state.saved.orchestrator).toEqual(ORCH)
      expect(state.saved.webSurfer).toEqual(WS)
      expect(state.verified).toBe(true)
    })

    it('only checks orchestrator when agent_mode=omniagent_only', () => {
      const state = loadedState('omniagent_only')
      expect(state.draft.orchEnabled).toBe(true)
      expect(state.draft.wsEnabled).toBe(false)
    })

    it('reflects backend agent_mode literally even when a config is missing', () => {
      // Mismatch: agent_mode='all' but ws config empty. UI surfaces this so
      // the user can either fill it in or uncheck the role.
      const state = loadedState('all', ORCH, EMPTY)
      expect(state.draft.orchEnabled).toBe(true)
      expect(state.draft.wsEnabled).toBe(true)
      // Selection requires ws config but it's missing — not verifiable.
      expect(state.verified).toBe(false)
    })

    it('starts with both checkboxes checked when agent_mode=all (even if nothing is saved)', () => {
      const state = loadedState('all', EMPTY, EMPTY)
      expect(state.draft.orchEnabled).toBe(true)
      expect(state.draft.wsEnabled).toBe(true)
      expect(state.verified).toBe(false)
    })
  })

  describe('edit-orch', () => {
    it('updates draft orchestrator and clears verify state', () => {
      let state = loadedState()
      state = reducer(state, { type: 'verify-start' })
      state = reducer(state, { type: 'verify-success' })
      expect(state.verified).toBe(true)

      state = reducer(state, { type: 'edit-orch', partial: { modelName: 'new-model' } })
      expect(state.draft.orchestrator.modelName).toBe('new-model')
      expect(state.draft.orchestrator.endpointUrl).toBe(ORCH.endpointUrl) // unchanged
      expect(state.verified).toBe(false)
      expect(state.errors).toEqual([])
      expect(state.orchError).toBe(false)
      expect(state.wsError).toBe(false)
    })
  })

  describe('edit-ws', () => {
    it('updates draft webSurfer and clears verify state', () => {
      let state = loadedState()
      state = reducer(state, {
        type: 'verify-fail',
        errors: ['Orchestrator model: failed'],
        orchError: true,
        wsError: false,
      })
      expect(state.orchError).toBe(true)

      state = reducer(state, { type: 'edit-ws', partial: { endpointUrl: 'http://new:5000/v1' } })
      expect(state.draft.webSurfer.endpointUrl).toBe('http://new:5000/v1')
      expect(state.orchError).toBe(false)
      expect(state.errors).toEqual([])
    })
  })

  describe('verify-start', () => {
    it('sets verifying and clears errors', () => {
      let state = loadedState()
      state = reducer(state, {
        type: 'verify-fail',
        errors: ['error'],
        orchError: true,
        wsError: true,
      })

      state = reducer(state, { type: 'verify-start' })
      expect(state.verifying).toBe(true)
      expect(state.errors).toEqual([])
      expect(state.orchError).toBe(false)
      expect(state.wsError).toBe(false)
    })
  })

  describe('verify-success', () => {
    it('sets verified and updates saved to match draft', () => {
      let state = loadedState()
      state = reducer(state, { type: 'edit-orch', partial: { modelName: 'changed' } })
      state = reducer(state, { type: 'verify-start' })
      state = reducer(state, { type: 'verify-success' })

      expect(state.verifying).toBe(false)
      expect(state.verified).toBe(true)
      // saved should now match draft
      expect(state.saved.orchestrator.modelName).toBe('changed')
    })

    it('does NOT promote disabled-role draft into saved', () => {
      // After unchecking web-surfer, edits to that card must not be saved
      // because the verify request omits the disabled role.
      let state = loadedState('all')
      state = reducer(state, { type: 'set-ws-enabled', enabled: false })
      // User somehow edited the (now disabled) Browser-use card.
      state = reducer(state, { type: 'edit-ws', partial: { modelName: 'unsaved-fara' } })
      state = reducer(state, { type: 'edit-orch', partial: { modelName: 'new-omni' } })
      state = reducer(state, { type: 'verify-start' })
      state = reducer(state, { type: 'verify-success' })

      expect(state.saved.orchestrator.modelName).toBe('new-omni') // promoted
      expect(state.saved.webSurfer.modelName).toBe(WS.modelName) // NOT promoted
      expect(state.saved.orchEnabled).toBe(true)
      expect(state.saved.wsEnabled).toBe(false)
    })
  })

  describe('verify-fail', () => {
    it('stores errors and per-endpoint error flags', () => {
      let state = loadedState()
      state = reducer(state, { type: 'verify-start' })
      state = reducer(state, {
        type: 'verify-fail',
        errors: ['Orchestrator model: Connection refused', 'Browser use model: Model not found'],
        orchError: true,
        wsError: true,
      })

      expect(state.verifying).toBe(false)
      expect(state.errors).toHaveLength(2)
      expect(state.orchError).toBe(true)
      expect(state.wsError).toBe(true)
      expect(state.verified).toBe(false)
    })

    it('can flag only one endpoint as errored', () => {
      let state = loadedState()
      state = reducer(state, {
        type: 'verify-fail',
        errors: ['Browser use model: timeout'],
        orchError: false,
        wsError: true,
      })

      expect(state.orchError).toBe(false)
      expect(state.wsError).toBe(true)
    })
  })

  describe('discard', () => {
    it('resets draft to saved and clears errors', () => {
      let state = loadedState()
      state = reducer(state, { type: 'edit-orch', partial: { modelName: 'dirty' } })
      state = reducer(state, {
        type: 'verify-fail',
        errors: ['error'],
        orchError: true,
        wsError: false,
      })

      state = reducer(state, { type: 'discard' })
      expect(state.draft.orchestrator).toEqual(ORCH)
      expect(state.draft.webSurfer).toEqual(WS)
      expect(state.errors).toEqual([])
      expect(state.orchError).toBe(false)
    })

    it('also reverts checkbox changes', () => {
      let state = loadedState('all')
      state = reducer(state, { type: 'set-orch-enabled', enabled: false })
      expect(state.draft.orchEnabled).toBe(false)

      state = reducer(state, { type: 'discard' })
      expect(state.draft.orchEnabled).toBe(true)
    })

    it('after fixing the missing role and discarding, restores the mismatch state', () => {
      // Backend says agent_mode=all but only orchestrator saved. Both boxes
      // start checked but verified=false because ws config is missing.
      // Editing then discarding should put us back to that initial state.
      let state = loadedState('all', ORCH, EMPTY)
      expect(state.verified).toBe(false)
      state = reducer(state, { type: 'edit-ws', partial: { endpointUrl: 'http://x' } })
      state = reducer(state, { type: 'discard' })
      expect(state.draft.wsEnabled).toBe(true)
      expect(state.draft.webSurfer).toEqual(EMPTY)
      expect(state.verified).toBe(false)
    })

    it('recomputes verified=false when nothing was saved', () => {
      let state = loadedState('all', EMPTY, EMPTY)
      state = reducer(state, { type: 'edit-orch', partial: { endpointUrl: 'http://x' } })
      state = reducer(state, { type: 'discard' })
      expect(state.verified).toBe(false)
    })
  })

  describe('set-orch-enabled / set-ws-enabled', () => {
    it('keeps verified=true when target selection required configs are saved', () => {
      // loadedState seeds both ORCH and WS as saved.
      let state = loadedState('all')
      state = reducer(state, { type: 'verify-start' })
      state = reducer(state, { type: 'verify-success' })
      expect(state.verified).toBe(true)

      // Unchecking orchestrator → ws still saved, so selection matches saved
      // for websurfer_only → verified stays true (ready for silent save).
      state = reducer(state, { type: 'set-orch-enabled', enabled: false })
      expect(state.draft.orchEnabled).toBe(false)
      expect(state.saved.orchEnabled).toBe(true) // unchanged
      expect(state.verified).toBe(true)
    })

    it('flips verified=false when target selection required configs are missing', () => {
      // Only orchestrator saved.
      let state = loadedState('omniagent_only', ORCH, EMPTY)
      // Enabling web-surfer requires a config that's not saved yet.
      state = reducer(state, { type: 'set-ws-enabled', enabled: true })
      expect(state.verified).toBe(false)
    })

    it('flips verified=false when nothing is enabled', () => {
      let state = loadedState('all')
      state = reducer(state, { type: 'verify-start' })
      state = reducer(state, { type: 'verify-success' })
      expect(state.verified).toBe(true)

      state = reducer(state, { type: 'set-orch-enabled', enabled: false })
      state = reducer(state, { type: 'set-ws-enabled', enabled: false })
      expect(state.verified).toBe(false)
    })
  })

  describe('mode-save-success', () => {
    it('promotes the saved selection into saved silently', () => {
      let state = loadedState('all')
      state = reducer(state, { type: 'set-orch-enabled', enabled: false })
      // verified stayed true after toggling because ws config is already saved.
      expect(state.verified).toBe(true)

      state = reducer(state, {
        type: 'mode-save-success',
        orchEnabled: false,
        wsEnabled: true,
      })

      expect(state.saved.orchEnabled).toBe(false)
      expect(state.saved.wsEnabled).toBe(true)
      expect(state.saved.orchestrator).toEqual(ORCH) // unchanged
      expect(state.verified).toBe(true)
      expect(state.verifying).toBe(false)
    })

    it('uses the action payload, not the draft (race-condition safety)', () => {
      // In-flight save for `orchEnabled=true,wsEnabled=false` returns AFTER
      // the user has toggled draft to `orchEnabled=false,wsEnabled=true`.
      // The success dispatch should promote the saved target.
      let state = loadedState('all')
      state = reducer(state, { type: 'set-ws-enabled', enabled: false })
      state = reducer(state, { type: 'set-orch-enabled', enabled: false })
      state = reducer(state, { type: 'set-ws-enabled', enabled: true })
      state = reducer(state, {
        type: 'mode-save-success',
        orchEnabled: true,
        wsEnabled: false,
      })

      expect(state.saved.orchEnabled).toBe(true)
      expect(state.saved.wsEnabled).toBe(false)
      expect(state.draft.orchEnabled).toBe(false)
      expect(state.draft.wsEnabled).toBe(true)
    })
  })

  describe('mode-save-fail', () => {
    it('records errors and flips verified to false', () => {
      let state = loadedState('all')
      state = reducer(state, { type: 'set-orch-enabled', enabled: false })
      state = reducer(state, {
        type: 'mode-save-fail',
        errors: ['Failed to save mode'],
      })
      expect(state.errors).toEqual(['Failed to save mode'])
      expect(state.verified).toBe(false)
    })
  })
})
