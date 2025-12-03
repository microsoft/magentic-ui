import { create } from 'zustand'
import {
  completeOnboarding,
  getOnboardingEndpoints,
  verifyEndpoints,
  type AgentMode,
  type VerifyEndpointsPayload,
} from '@/api/onboarding'

/** Onboarding step identifiers */
export type OnboardingStep = 'welcome' | 'custom_endpoint' | 'verifying' | 'verified' | 'ready'

/** Model endpoint configuration entered by user */
export interface ModelEndpointConfig {
  endpointUrl: string
  modelName: string
  apiKey: string
}

/** Verification state for a single model */
export interface ModelVerifyState {
  status: 'idle' | 'verifying' | 'success' | 'error'
  error?: string
}

interface OnboardingState {
  /** Current step in the onboarding flow */
  step: OnboardingStep

  /** OmniAgent (orchestrator) model config */
  orchestrator: ModelEndpointConfig

  /** Fara (web_surfer) model config */
  webSurfer: ModelEndpointConfig

  /** Whether the orchestrator role is enabled (checkbox state). */
  orchEnabled: boolean

  /** Whether the web-surfer role is enabled (checkbox state). */
  wsEnabled: boolean

  /** Verification state */
  verifyState: {
    orchestrator: ModelVerifyState
    webSurfer: ModelVerifyState
    overall: 'idle' | 'verifying' | 'success' | 'error'
    overallError?: string
  }

  /** Actions */
  setStep: (step: OnboardingStep) => void
  setOrchestrator: (config: Partial<ModelEndpointConfig>) => void
  setWebSurfer: (config: Partial<ModelEndpointConfig>) => void
  setOrchEnabled: (enabled: boolean) => void
  setWsEnabled: (enabled: boolean) => void
  /**
   * Hydrate from backend. If a model config was previously saved, jumps
   * straight to the model-card step (skipping welcome). This
   * handles bounce-back when YAML changes `agent_mode` to require a missing
   * model.
   */
  init: () => Promise<void>
  verifyWithApi: () => Promise<void>
  reset: () => void
}

const EMPTY_CONFIG: ModelEndpointConfig = {
  endpointUrl: '',
  modelName: '',
  apiKey: '',
}

const IDLE_VERIFY: ModelVerifyState = { status: 'idle' }

export const useOnboardingStore = create<OnboardingState>((set) => ({
  step: 'welcome',
  orchestrator: { ...EMPTY_CONFIG },
  webSurfer: { ...EMPTY_CONFIG },
  orchEnabled: true,
  wsEnabled: true,
  verifyState: {
    orchestrator: { ...IDLE_VERIFY },
    webSurfer: { ...IDLE_VERIFY },
    overall: 'idle',
  },

  setStep: (step) => set({ step }),

  setOrchestrator: (config) =>
    set((s) => ({
      orchestrator: { ...s.orchestrator, ...config },
      verifyState: {
        orchestrator: { ...IDLE_VERIFY },
        webSurfer: s.verifyState.webSurfer,
        overall: 'idle',
        overallError: undefined,
      },
    })),

  setWebSurfer: (config) =>
    set((s) => ({
      webSurfer: { ...s.webSurfer, ...config },
      verifyState: {
        orchestrator: s.verifyState.orchestrator,
        webSurfer: { ...IDLE_VERIFY },
        overall: 'idle',
        overallError: undefined,
      },
    })),

  setOrchEnabled: (enabled) =>
    set({
      orchEnabled: enabled,
      verifyState: {
        orchestrator: { ...IDLE_VERIFY },
        webSurfer: { ...IDLE_VERIFY },
        overall: 'idle',
        overallError: undefined,
      },
    }),

  setWsEnabled: (enabled) =>
    set({
      wsEnabled: enabled,
      verifyState: {
        orchestrator: { ...IDLE_VERIFY },
        webSurfer: { ...IDLE_VERIFY },
        overall: 'idle',
        overallError: undefined,
      },
    }),

  init: async () => {
    try {
      const data = await getOnboardingEndpoints()
      const orchSaved = data.orchestrator
      const wsSaved = data.web_surfer
      const hasAnySaved = !!orchSaved || !!wsSaved
      // When a saved config exists, mirror its agent_mode so we don't
      // re-enable a model the user previously disabled. Otherwise fall
      // back to the fresh-onboarding default (both enabled).
      const orchFromMode = data.agent_mode === 'all' || data.agent_mode === 'omniagent_only'
      const wsFromMode = data.agent_mode === 'all' || data.agent_mode === 'websurfer_only'
      set((s) => ({
        orchEnabled: hasAnySaved ? !!orchSaved && orchFromMode : true,
        wsEnabled: hasAnySaved ? !!wsSaved && wsFromMode : true,
        orchestrator: orchSaved
          ? {
              endpointUrl: orchSaved.config.base_url,
              modelName: orchSaved.config.model,
              apiKey: orchSaved.config.api_key,
            }
          : s.orchestrator,
        webSurfer: wsSaved
          ? {
              endpointUrl: wsSaved.config.base_url,
              modelName: wsSaved.config.model,
              apiKey: wsSaved.config.api_key,
            }
          : s.webSurfer,
        // Bounce-back: if user previously saved a model, skip welcome
        // and land directly on the model-card step.
        step: hasAnySaved && s.step === 'welcome' ? 'custom_endpoint' : s.step,
      }))
    } catch {
      // Backend unreachable — leave defaults; user will see welcome screen.
    }
  },

  verifyWithApi: async () => {
    const { orchestrator, webSurfer, orchEnabled, wsEnabled } = useOnboardingStore.getState()
    // Derive AgentMode from checkbox state. Caller is expected to ensure at
    // least one is enabled before invoking; otherwise this no-ops.
    const agentMode: AgentMode | null =
      orchEnabled && wsEnabled
        ? 'all'
        : orchEnabled
          ? 'omniagent_only'
          : wsEnabled
            ? 'websurfer_only'
            : null
    if (!agentMode) return
    const orchActive = orchEnabled
    const wsActive = wsEnabled

    // Trim inputs and update store so model cards display trimmed values
    const trimmedOrch = {
      endpointUrl: orchestrator.endpointUrl.trim(),
      modelName: orchestrator.modelName.trim(),
      apiKey: orchestrator.apiKey.trim(),
    }
    const trimmedWs = {
      endpointUrl: webSurfer.endpointUrl.trim(),
      modelName: webSurfer.modelName.trim(),
      apiKey: webSurfer.apiKey.trim(),
    }

    set({
      orchestrator: trimmedOrch,
      webSurfer: trimmedWs,
      step: 'verifying',
      verifyState: {
        orchestrator: orchActive ? { status: 'verifying' } : { ...IDLE_VERIFY },
        webSurfer: wsActive ? { status: 'verifying' } : { ...IDLE_VERIFY },
        overall: 'verifying',
      },
    })

    try {
      const payload: VerifyEndpointsPayload = { agent_mode: agentMode }
      if (orchActive) {
        payload.orchestrator = {
          base_url: trimmedOrch.endpointUrl,
          model: trimmedOrch.modelName,
          api_key: trimmedOrch.apiKey,
        }
      }
      if (wsActive) {
        payload.web_surfer = {
          base_url: trimmedWs.endpointUrl,
          model: trimmedWs.modelName,
          api_key: trimmedWs.apiKey,
        }
      }

      const result = await verifyEndpoints(payload)

      const orchOk = !orchActive || !!result.orchestrator?.success
      const wsOk = !wsActive || !!result.web_surfer?.success
      const allOk = orchOk && wsOk

      // Build per-endpoint error message
      const errors: string[] = []
      if (orchActive && !orchOk) {
        errors.push(`Orchestrator model: ${result.orchestrator?.error ?? 'Verification failed'}`)
      }
      if (wsActive && !wsOk) {
        errors.push(`Browser use model: ${result.web_surfer?.error ?? 'Verification failed'}`)
      }

      set({
        step: allOk ? 'verified' : 'custom_endpoint',
        verifyState: {
          orchestrator: orchActive
            ? {
                status: orchOk ? 'success' : 'error',
                error: result.orchestrator?.error,
              }
            : { ...IDLE_VERIFY },
          webSurfer: wsActive
            ? {
                status: wsOk ? 'success' : 'error',
                error: result.web_surfer?.error,
              }
            : { ...IDLE_VERIFY },
          overall: allOk ? 'success' : 'error',
          overallError: allOk ? undefined : errors.join('\n'),
        },
      })

      // If all required passed, mark onboarding complete then advance to ready
      if (allOk) {
        await completeOnboarding()
        set({ step: 'ready' })
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Verification failed'
      set({
        step: 'custom_endpoint',
        verifyState: {
          orchestrator: orchActive ? { status: 'error', error: msg } : { ...IDLE_VERIFY },
          webSurfer: wsActive ? { status: 'error', error: msg } : { ...IDLE_VERIFY },
          overall: 'error',
          overallError: msg,
        },
      })
    }
  },

  reset: () =>
    set({
      step: 'welcome',
      orchestrator: { ...EMPTY_CONFIG },
      webSurfer: { ...EMPTY_CONFIG },
      orchEnabled: true,
      wsEnabled: true,
      verifyState: {
        orchestrator: { ...IDLE_VERIFY },
        webSurfer: { ...IDLE_VERIFY },
        overall: 'idle',
      },
    }),
}))
