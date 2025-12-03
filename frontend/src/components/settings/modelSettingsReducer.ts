/**
 * ModelSettings reducer
 *
 * State + actions for the Settings → Models tab. Lives in its own file so
 * unit tests can import it without going through the component (which would
 * otherwise need a DOM) and so React Fast Refresh isn't broken by mixed
 * exports in `ModelSettings.tsx`.
 */
import { type AgentMode, type ModelClientConfig } from '@/api/onboarding'

// =============================================================================
// Form types & helpers
// =============================================================================

export interface FormConfig {
  endpointUrl: string
  modelName: string
  apiKey: string
}

export const EMPTY_FORM: FormConfig = { endpointUrl: '', modelName: '', apiKey: '' }

export function toForm(ep: ModelClientConfig | null): FormConfig {
  if (!ep) return { ...EMPTY_FORM }
  return {
    endpointUrl: ep.config.base_url,
    modelName: ep.config.model,
    apiKey: ep.config.api_key,
  }
}

export function configEqual(a: FormConfig, b: FormConfig): boolean {
  return a.endpointUrl === b.endpointUrl && a.modelName === b.modelName && a.apiKey === b.apiKey
}

export function isFormFilled(f: FormConfig): boolean {
  return !!f.endpointUrl.trim() && !!f.modelName.trim()
}

/**
 * Derive the AgentMode value from the orchestrator/web-surfer enabled flags.
 * Returns `null` when neither role is enabled (an unsupported state — the
 * UI must block submit in that case).
 */
export function deriveAgentMode(orchEnabled: boolean, wsEnabled: boolean): AgentMode | null {
  if (orchEnabled && wsEnabled) return 'all'
  if (orchEnabled) return 'omniagent_only'
  if (wsEnabled) return 'websurfer_only'
  return null
}

/** True when `agent_mode` requires orchestrator. */
function requiresOrch(mode: AgentMode): boolean {
  return mode === 'all' || mode === 'omniagent_only'
}

/** True when `agent_mode` requires web_surfer. */
function requiresWs(mode: AgentMode): boolean {
  return mode === 'all' || mode === 'websurfer_only'
}

// =============================================================================
// State
// =============================================================================

interface RolesState {
  orchestrator: FormConfig
  webSurfer: FormConfig
}

interface SelectionState {
  orchEnabled: boolean
  wsEnabled: boolean
}

export interface ModelSettingsState {
  saved: RolesState & SelectionState
  draft: RolesState & SelectionState
  loading: boolean
  verifying: boolean
  /** True while the latest saved state is verified (or trivially valid). */
  verified: boolean
  errors: string[]
  orchError: boolean
  wsError: boolean
}

export type ModelSettingsAction =
  | {
      type: 'loaded'
      orchestrator: FormConfig
      webSurfer: FormConfig
      agentMode: AgentMode
    }
  | { type: 'edit-orch'; partial: Partial<FormConfig> }
  | { type: 'edit-ws'; partial: Partial<FormConfig> }
  | { type: 'set-orch-enabled'; enabled: boolean }
  | { type: 'set-ws-enabled'; enabled: boolean }
  | { type: 'trim' }
  | { type: 'verify-start' }
  | { type: 'verify-success' }
  | { type: 'verify-fail'; errors: string[]; orchError: boolean; wsError: boolean }
  | { type: 'mode-save-success'; orchEnabled: boolean; wsEnabled: boolean }
  | { type: 'mode-save-fail'; errors: string[] }
  | { type: 'discard' }

const EMPTY_STATE: RolesState & SelectionState = {
  orchestrator: { ...EMPTY_FORM },
  webSurfer: { ...EMPTY_FORM },
  orchEnabled: false,
  wsEnabled: false,
}

export const modelSettingsInitialState: ModelSettingsState = {
  saved: { ...EMPTY_STATE },
  draft: { ...EMPTY_STATE },
  loading: true,
  verifying: false,
  verified: false,
  errors: [],
  orchError: false,
  wsError: false,
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Returns true when the given enabled flags can be persisted as-is using the
 * saved configs (i.e. every enabled role already has a complete saved form).
 * Used to keep `verified` true across silent mode-only saves.
 */
function selectionMatchesSaved(
  saved: RolesState & SelectionState,
  orchEnabled: boolean,
  wsEnabled: boolean
): boolean {
  if (!orchEnabled && !wsEnabled) return false
  if (orchEnabled && !isFormFilled(saved.orchestrator)) return false
  if (wsEnabled && !isFormFilled(saved.webSurfer)) return false
  return true
}

// =============================================================================
// Reducer
// =============================================================================

export function modelSettingsReducer(
  state: ModelSettingsState,
  action: ModelSettingsAction
): ModelSettingsState {
  switch (action.type) {
    case 'loaded': {
      // Reflect the backend's `agent_mode` literally — even if a role's
      // saved config is missing. The UI then surfaces the mismatch (checkbox
      // checked but fields empty, Verify button disabled), so the user can
      // either fill it in or uncheck the role. The /onboarding route handles
      // first-run/missing-config bounce-back separately.
      const orchEnabled = requiresOrch(action.agentMode)
      const wsEnabled = requiresWs(action.agentMode)
      const next = {
        orchestrator: action.orchestrator,
        webSurfer: action.webSurfer,
        orchEnabled,
        wsEnabled,
      }
      const initiallyVerified = selectionMatchesSaved(next, orchEnabled, wsEnabled)
      return {
        ...state,
        loading: false,
        verified: initiallyVerified,
        saved: { ...next },
        draft: { ...next },
      }
    }
    case 'edit-orch':
      return {
        ...state,
        draft: {
          ...state.draft,
          orchestrator: { ...state.draft.orchestrator, ...action.partial },
        },
        verified: false,
        errors: [],
        orchError: false,
        wsError: false,
      }
    case 'edit-ws':
      return {
        ...state,
        draft: {
          ...state.draft,
          webSurfer: { ...state.draft.webSurfer, ...action.partial },
        },
        verified: false,
        errors: [],
        orchError: false,
        wsError: false,
      }
    case 'set-orch-enabled': {
      // Keep `verified` true only when the new selection's required configs
      // are already saved (so the silent auto-save doesn't flicker the UI).
      const verified = selectionMatchesSaved(state.saved, action.enabled, state.draft.wsEnabled)
      return {
        ...state,
        draft: { ...state.draft, orchEnabled: action.enabled },
        verified,
        errors: [],
        orchError: false,
        wsError: false,
      }
    }
    case 'set-ws-enabled': {
      const verified = selectionMatchesSaved(state.saved, state.draft.orchEnabled, action.enabled)
      return {
        ...state,
        draft: { ...state.draft, wsEnabled: action.enabled },
        verified,
        errors: [],
        orchError: false,
        wsError: false,
      }
    }
    case 'trim': {
      const trimForm = (f: FormConfig): FormConfig => ({
        endpointUrl: f.endpointUrl.trim(),
        modelName: f.modelName.trim(),
        apiKey: f.apiKey.trim(),
      })
      return {
        ...state,
        draft: {
          ...state.draft,
          orchestrator: trimForm(state.draft.orchestrator),
          webSurfer: trimForm(state.draft.webSurfer),
        },
      }
    }
    case 'verify-start':
      return {
        ...state,
        verifying: true,
        verified: false,
        errors: [],
        orchError: false,
        wsError: false,
      }
    case 'verify-success': {
      // Only promote enabled-side drafts into `saved`. The verify request
      // omits the disabled role, so the backend never persisted it — keep
      // its previous saved value to avoid showing unsaved drafts as saved.
      return {
        ...state,
        verifying: false,
        verified: true,
        saved: {
          orchEnabled: state.draft.orchEnabled,
          wsEnabled: state.draft.wsEnabled,
          orchestrator: state.draft.orchEnabled
            ? state.draft.orchestrator
            : state.saved.orchestrator,
          webSurfer: state.draft.wsEnabled ? state.draft.webSurfer : state.saved.webSurfer,
        },
      }
    }
    case 'verify-fail':
      return {
        ...state,
        verifying: false,
        verified: false,
        errors: action.errors,
        orchError: action.orchError,
        wsError: action.wsError,
      }
    case 'mode-save-success':
      // Silent success — promote the selection that was actually saved
      // (passed in by the action) into `saved` without touching `verifying`
      // or `verified`. We use the action payload, not the latest draft, to
      // avoid overwriting saved with a newer in-flight selection.
      return {
        ...state,
        saved: {
          ...state.saved,
          orchEnabled: action.orchEnabled,
          wsEnabled: action.wsEnabled,
        },
      }
    case 'mode-save-fail':
      return {
        ...state,
        verified: false,
        errors: action.errors,
      }
    case 'discard': {
      // Recompute `verified` from saved — don't assume the saved state is
      // valid (e.g., orchEnabled=true but orchestrator config empty would
      // not be a verified state).
      const savedComplete = selectionMatchesSaved(
        state.saved,
        state.saved.orchEnabled,
        state.saved.wsEnabled
      )
      return {
        ...state,
        draft: { ...state.saved },
        verified: savedComplete,
        errors: [],
        orchError: false,
        wsError: false,
      }
    }
    default: {
      // Exhaustiveness check: if a new action type is added without a case
      // here, TypeScript will fail to assign it to `never`. Returning state
      // also keeps us safe at runtime if a stray action is ever dispatched.
      const _exhaustive: never = action
      void _exhaustive
      return state
    }
  }
}
