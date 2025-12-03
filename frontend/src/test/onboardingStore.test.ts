/**
 * Tests for onboardingStore
 *
 * Covers: step transitions, config setters, verifyWithApi (success/partial/error),
 * orch/ws enabled flags, init/bounce-back, and reset.
 */

import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { useOnboardingStore } from '@/stores/onboardingStore'

// Mock the API module.
vi.mock('@/api/onboarding', async () => {
  const actual = await vi.importActual<typeof import('@/api/onboarding')>('@/api/onboarding')
  return {
    ...actual,
    verifyEndpoints: vi.fn(),
    completeOnboarding: vi.fn(),
    getOnboardingEndpoints: vi.fn(),
    setAgentMode: vi.fn(),
  }
})

import { completeOnboarding, getOnboardingEndpoints, verifyEndpoints } from '@/api/onboarding'

const INITIAL_STATE = {
  step: 'welcome' as const,
  orchestrator: { endpointUrl: '', modelName: '', apiKey: '' },
  webSurfer: { endpointUrl: '', modelName: '', apiKey: '' },
  orchEnabled: true,
  wsEnabled: true,
  verifyState: {
    orchestrator: { status: 'idle' as const },
    webSurfer: { status: 'idle' as const },
    overall: 'idle' as const,
  },
}

describe('onboardingStore', () => {
  beforeEach(() => {
    useOnboardingStore.setState(INITIAL_STATE)
    vi.clearAllMocks()
  })

  // ---------------------------------------------------------------------------
  // Step transitions
  // ---------------------------------------------------------------------------

  describe('setStep', () => {
    it('updates step', () => {
      useOnboardingStore.getState().setStep('custom_endpoint')
      expect(useOnboardingStore.getState().step).toBe('custom_endpoint')
    })
  })

  // ---------------------------------------------------------------------------
  // Config setters
  // ---------------------------------------------------------------------------

  describe('setOrchestrator', () => {
    it('merges partial config', () => {
      useOnboardingStore.getState().setOrchestrator({ endpointUrl: 'http://x' })
      const { orchestrator } = useOnboardingStore.getState()
      expect(orchestrator.endpointUrl).toBe('http://x')
      expect(orchestrator.modelName).toBe('') // unchanged
    })
  })

  describe('setWebSurfer', () => {
    it('merges partial config', () => {
      useOnboardingStore.getState().setWebSurfer({ modelName: 'fara-v1' })
      const { webSurfer } = useOnboardingStore.getState()
      expect(webSurfer.modelName).toBe('fara-v1')
      expect(webSurfer.endpointUrl).toBe('') // unchanged
    })
  })

  describe('setOrchEnabled / setWsEnabled', () => {
    it('updates flags and resets verify state', () => {
      useOnboardingStore.setState({
        verifyState: {
          orchestrator: { status: 'success' },
          webSurfer: { status: 'success' },
          overall: 'success',
        },
      })
      useOnboardingStore.getState().setOrchEnabled(true)
      const state = useOnboardingStore.getState()
      expect(state.orchEnabled).toBe(true)
      expect(state.verifyState.overall).toBe('idle')
    })

    it('allows toggling both off', () => {
      useOnboardingStore.setState({ orchEnabled: true, wsEnabled: false })
      useOnboardingStore.getState().setOrchEnabled(false)
      expect(useOnboardingStore.getState().orchEnabled).toBe(false)
      expect(useOnboardingStore.getState().wsEnabled).toBe(false)
    })
  })

  // ---------------------------------------------------------------------------
  // init / bounce-back
  // ---------------------------------------------------------------------------

  describe('init', () => {
    const SAVED_ENDPOINT = {
      provider: 'OpenAIChatCompletionClient',
      config: {
        model: 'm',
        api_key: '__MASKED__',
        base_url: 'http://x/v1',
        max_retries: 3,
        model_info: {
          vision: false,
          function_calling: true,
          json_output: true,
          family: 'unknown',
          structured_output: true,
          multiple_system_messages: true,
        },
      },
    }

    it('defaults both flags to enabled and stays on welcome when nothing is saved', async () => {
      ;(getOnboardingEndpoints as Mock).mockResolvedValue({
        orchestrator: null,
        web_surfer: null,
        agent_mode: 'omniagent_only',
      })
      await useOnboardingStore.getState().init()
      const state = useOnboardingStore.getState()
      expect(state.orchEnabled).toBe(true)
      expect(state.wsEnabled).toBe(true)
      expect(state.step).toBe('welcome')
    })

    it('jumps to custom_endpoint when at least one model is saved', async () => {
      ;(getOnboardingEndpoints as Mock).mockResolvedValue({
        orchestrator: SAVED_ENDPOINT,
        web_surfer: null,
        agent_mode: 'all',
      })
      await useOnboardingStore.getState().init()
      const state = useOnboardingStore.getState()
      expect(state.step).toBe('custom_endpoint')
      expect(state.orchEnabled).toBe(true)
      expect(state.wsEnabled).toBe(false)
      expect(state.orchestrator.endpointUrl).toBe('http://x/v1')
    })

    it('stays on welcome after reset (both saved configs cleared)', async () => {
      ;(getOnboardingEndpoints as Mock).mockResolvedValue({
        orchestrator: null,
        web_surfer: null,
        agent_mode: 'all',
      })
      await useOnboardingStore.getState().init()
      expect(useOnboardingStore.getState().step).toBe('welcome')
    })

    it('does not crash when API throws', async () => {
      ;(getOnboardingEndpoints as Mock).mockRejectedValue(new Error('boom'))
      await useOnboardingStore.getState().init()
      expect(useOnboardingStore.getState().step).toBe('welcome')
    })
  })

  // ---------------------------------------------------------------------------
  // verifyWithApi
  // ---------------------------------------------------------------------------

  describe('verifyWithApi', () => {
    it('sets step to ready and calls completeOnboarding on success', async () => {
      ;(verifyEndpoints as Mock).mockResolvedValue({
        orchestrator: { success: true },
        web_surfer: { success: true },
      })
      ;(completeOnboarding as Mock).mockResolvedValue(undefined)

      useOnboardingStore.setState({
        orchEnabled: true,
        wsEnabled: true,
        orchestrator: { endpointUrl: 'http://a/v1', modelName: 'ma', apiKey: 'ka' },
        webSurfer: { endpointUrl: 'http://b/v1', modelName: 'mb', apiKey: 'kb' },
      })

      await useOnboardingStore.getState().verifyWithApi()

      const state = useOnboardingStore.getState()
      expect(state.step).toBe('ready')
      expect(state.verifyState.overall).toBe('success')
      expect(state.verifyState.orchestrator.status).toBe('success')
      expect(state.verifyState.webSurfer.status).toBe('success')
      expect(completeOnboarding).toHaveBeenCalledOnce()
    })

    it('sets step to custom_endpoint on partial failure', async () => {
      ;(verifyEndpoints as Mock).mockResolvedValue({
        orchestrator: { success: true },
        web_surfer: { success: false, error: 'Connection refused' },
      })

      useOnboardingStore.setState({
        orchEnabled: true,
        wsEnabled: true,
        orchestrator: { endpointUrl: 'http://a/v1', modelName: 'ma', apiKey: '' },
        webSurfer: { endpointUrl: 'http://b/v1', modelName: 'mb', apiKey: '' },
      })

      await useOnboardingStore.getState().verifyWithApi()

      const state = useOnboardingStore.getState()
      expect(state.step).toBe('custom_endpoint')
      expect(state.verifyState.overall).toBe('error')
      expect(state.verifyState.orchestrator.status).toBe('success')
      expect(state.verifyState.webSurfer.status).toBe('error')
      expect(state.verifyState.webSurfer.error).toBe('Connection refused')
      expect(completeOnboarding).not.toHaveBeenCalled()
    })

    it('handles API exception gracefully', async () => {
      ;(verifyEndpoints as Mock).mockRejectedValue(new Error('Network error'))

      useOnboardingStore.setState({
        orchEnabled: true,
        wsEnabled: true,
        orchestrator: { endpointUrl: 'http://a/v1', modelName: 'ma', apiKey: '' },
        webSurfer: { endpointUrl: 'http://b/v1', modelName: 'mb', apiKey: '' },
      })

      await useOnboardingStore.getState().verifyWithApi()

      const state = useOnboardingStore.getState()
      expect(state.step).toBe('custom_endpoint')
      expect(state.verifyState.overall).toBe('error')
      expect(state.verifyState.overallError).toBe('Network error')
    })

    it('trims input before sending', async () => {
      ;(verifyEndpoints as Mock).mockResolvedValue({
        orchestrator: { success: true },
        web_surfer: { success: true },
      })
      ;(completeOnboarding as Mock).mockResolvedValue(undefined)

      useOnboardingStore.setState({
        orchEnabled: true,
        wsEnabled: true,
        orchestrator: { endpointUrl: '  http://a/v1  ', modelName: '  ma  ', apiKey: '  ka  ' },
        webSurfer: { endpointUrl: '  http://b/v1  ', modelName: '  mb  ', apiKey: '' },
      })

      await useOnboardingStore.getState().verifyWithApi()

      expect(verifyEndpoints).toHaveBeenCalledWith({
        agent_mode: 'all',
        orchestrator: { base_url: 'http://a/v1', model: 'ma', api_key: 'ka' },
        web_surfer: { base_url: 'http://b/v1', model: 'mb', api_key: '' },
      })
      // Store should also have trimmed values
      expect(useOnboardingStore.getState().orchestrator.endpointUrl).toBe('http://a/v1')
    })

    it('only sends required side when only orchestrator is enabled', async () => {
      ;(verifyEndpoints as Mock).mockResolvedValue({
        orchestrator: { success: true },
      })
      ;(completeOnboarding as Mock).mockResolvedValue(undefined)

      useOnboardingStore.setState({
        orchEnabled: true,
        wsEnabled: false,
        orchestrator: { endpointUrl: 'http://a/v1', modelName: 'ma', apiKey: '' },
        webSurfer: { endpointUrl: 'http://b/v1', modelName: 'mb', apiKey: '' },
      })

      await useOnboardingStore.getState().verifyWithApi()

      expect(verifyEndpoints).toHaveBeenCalledWith({
        agent_mode: 'omniagent_only',
        orchestrator: { base_url: 'http://a/v1', model: 'ma', api_key: '' },
      })
      const state = useOnboardingStore.getState()
      expect(state.step).toBe('ready')
      expect(state.verifyState.webSurfer.status).toBe('idle')
    })

    it('only sends required side when only web-surfer is enabled', async () => {
      ;(verifyEndpoints as Mock).mockResolvedValue({
        web_surfer: { success: true },
      })
      ;(completeOnboarding as Mock).mockResolvedValue(undefined)

      useOnboardingStore.setState({
        orchEnabled: false,
        wsEnabled: true,
        orchestrator: { endpointUrl: '', modelName: '', apiKey: '' },
        webSurfer: { endpointUrl: 'http://b/v1', modelName: 'mb', apiKey: '' },
      })

      await useOnboardingStore.getState().verifyWithApi()

      expect(verifyEndpoints).toHaveBeenCalledWith({
        agent_mode: 'websurfer_only',
        web_surfer: { base_url: 'http://b/v1', model: 'mb', api_key: '' },
      })
      expect(useOnboardingStore.getState().step).toBe('ready')
    })

    it('no-ops when neither flag is enabled', async () => {
      useOnboardingStore.setState({ orchEnabled: false, wsEnabled: false })
      await useOnboardingStore.getState().verifyWithApi()
      expect(verifyEndpoints).not.toHaveBeenCalled()
      expect(useOnboardingStore.getState().step).toBe('welcome')
    })
  })

  // ---------------------------------------------------------------------------
  // reset
  // ---------------------------------------------------------------------------

  describe('reset', () => {
    it('resets to initial state', () => {
      useOnboardingStore.setState({
        step: 'ready',
        orchestrator: { endpointUrl: 'http://x', modelName: 'm', apiKey: 'k' },
        orchEnabled: true,
        wsEnabled: true,
        verifyState: {
          orchestrator: { status: 'success' },
          webSurfer: { status: 'success' },
          overall: 'success',
        },
      })

      useOnboardingStore.getState().reset()

      const state = useOnboardingStore.getState()
      expect(state.step).toBe('welcome')
      expect(state.orchestrator.endpointUrl).toBe('')
      expect(state.orchEnabled).toBe(true)
      expect(state.wsEnabled).toBe(true)
      expect(state.verifyState.overall).toBe('idle')
    })
  })
})
