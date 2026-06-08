/**
 * Model Settings
 *
 * Per-card checkboxes (which derive `agent_mode`) + model endpoint cards
 * with verify & save, dirty-check, and discard. Exposes isDirty via callback
 * so SettingsDialog can block close/tab-switch.
 *
 * State machine lives in `./modelSettingsReducer` so unit tests can target it
 * without rendering the component.
 */
import { useCallback, useEffect, useMemo, useReducer, useRef } from 'react'
import { ArrowRight, CheckCircle2, ExternalLink, Loader2, RotateCcw } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { useBackendHealthStore } from '@/stores'
import {
  ModelConfigCard,
  RecommendedModel,
  VerificationAlert,
} from '@/components/common/ModelConfigCard'
import { cn } from '@/lib/utils'
import { FARA_DOC_URL, MODEL_HOSTING_GUIDE_URL, ORCHESTRATOR_DOC_URL } from '@/lib/constants'
import {
  getOnboardingEndpoints,
  invalidateOnboardingEndpoints,
  setAgentMode as apiSetAgentMode,
  verifyEndpoints,
  type VerifyEndpointsPayload,
} from '@/api/onboarding'
import {
  EMPTY_FORM,
  configEqual,
  deriveAgentMode,
  isFormFilled,
  modelSettingsInitialState,
  modelSettingsReducer,
  toForm,
} from './modelSettingsReducer'

// =============================================================================
// Component
// =============================================================================

interface ModelSettingsProps {
  onDirtyChange?: (dirty: boolean) => void
}

export function ModelSettings({ onDirtyChange }: ModelSettingsProps) {
  const [state, dispatch] = useReducer(modelSettingsReducer, modelSettingsInitialState)
  const { saved, draft, loading, verifying, verified, errors, orchError, wsError } = state
  // Freeze controls while verifying, during initial load, or when the
  // backend is unreachable. Banner explains the disconnected case.
  const reachable = useBackendHealthStore((s) => s.reachable)
  const frozen = verifying || loading || !reachable
  const queryClient = useQueryClient()

  // ── Derived ────────────────────────────────────────────────────
  const orchEnabled = draft.orchEnabled
  const wsEnabled = draft.wsEnabled

  const orchEdited = !configEqual(draft.orchestrator, saved.orchestrator)
  const wsEdited = !configEqual(draft.webSurfer, saved.webSurfer)
  const selectionChanged =
    draft.orchEnabled !== saved.orchEnabled || draft.wsEnabled !== saved.wsEnabled

  const isDirty = orchEdited || wsEdited || selectionChanged

  const canSubmit = useMemo(() => {
    if (!orchEnabled && !wsEnabled) return false
    if (orchEnabled && !isFormFilled(draft.orchestrator)) return false
    if (wsEnabled && !isFormFilled(draft.webSurfer)) return false
    return true
  }, [orchEnabled, wsEnabled, draft])

  /**
   * Decide submit mode:
   * - 'mode-only': only the checkbox selection changed; no enabled-side card
   *   was edited and every newly-enabled side already has a saved config →
   *   call setAgentMode silently.
   * - 'verify': any enabled-side card was edited or is missing a saved
   *   config → caller must verify against the LLM endpoints.
   */
  const submitMode: 'mode-only' | 'verify' = useMemo(() => {
    const mode = deriveAgentMode(orchEnabled, wsEnabled)
    if (!mode) return 'verify' // neither enabled — nothing to auto-save
    const enabledEdited = (orchEnabled && orchEdited) || (wsEnabled && wsEdited)
    const enabledSavedAll =
      (!orchEnabled || isFormFilled(saved.orchestrator)) &&
      (!wsEnabled || isFormFilled(saved.webSurfer))
    if (selectionChanged && !enabledEdited && enabledSavedAll) return 'mode-only'
    return 'verify'
  }, [selectionChanged, orchEnabled, wsEnabled, orchEdited, wsEdited, saved])

  // ── Effects ────────────────────────────────────────────────────
  useEffect(() => {
    onDirtyChange?.(isDirty)
  }, [isDirty, onDirtyChange])

  // Use react-query so backend-recovery refetch picks it up. Falls back
  // to empty form on failure.
  const endpointsQuery = useQuery({
    queryKey: ['onboarding', 'endpoints'],
    queryFn: getOnboardingEndpoints,
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  })

  // Apply loaded data to the reducer. Skip when dirty so a background
  // refetch on recovery doesn't blow away in-progress edits.
  useEffect(() => {
    if (isDirty) return
    if (endpointsQuery.data) {
      const data = endpointsQuery.data
      dispatch({
        type: 'loaded',
        orchestrator: toForm(data.orchestrator),
        webSurfer: toForm(data.web_surfer),
        agentMode: data.agent_mode ?? 'all',
      })
    } else if (endpointsQuery.isError) {
      dispatch({
        type: 'loaded',
        orchestrator: { ...EMPTY_FORM },
        webSurfer: { ...EMPTY_FORM },
        agentMode: 'all',
      })
    }
    // isDirty is read as a value, not a dep — a transition to dirty
    // shouldn't re-fire this; the next refetch will re-apply when clean.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpointsQuery.data, endpointsQuery.isError])

  // ── Handlers ───────────────────────────────────────────────────
  const handleVerify = useCallback(async () => {
    const agentMode = deriveAgentMode(orchEnabled, wsEnabled)
    if (!agentMode) return // safety net — UI should already disable submit

    dispatch({ type: 'trim' })
    dispatch({ type: 'verify-start' })
    try {
      const payload: VerifyEndpointsPayload = { agent_mode: agentMode }
      if (orchEnabled) {
        payload.orchestrator = {
          base_url: draft.orchestrator.endpointUrl.trim(),
          model: draft.orchestrator.modelName.trim(),
          api_key: draft.orchestrator.apiKey.trim(),
        }
      }
      if (wsEnabled) {
        payload.web_surfer = {
          base_url: draft.webSurfer.endpointUrl.trim(),
          model: draft.webSurfer.modelName.trim(),
          api_key: draft.webSurfer.apiKey.trim(),
        }
      }

      const result = await verifyEndpoints(payload)

      const orchOk = !orchEnabled || !!result.orchestrator?.success
      const wsOk = !wsEnabled || !!result.web_surfer?.success

      if (orchOk && wsOk) {
        void invalidateOnboardingEndpoints(queryClient)
        dispatch({ type: 'verify-success' })
      } else {
        const errs: string[] = []
        if (orchEnabled && !result.orchestrator?.success) {
          errs.push(`Orchestrator model: ${result.orchestrator?.error ?? 'Verification failed'}`)
        }
        if (wsEnabled && !result.web_surfer?.success) {
          errs.push(`Browser use model: ${result.web_surfer?.error ?? 'Verification failed'}`)
        }
        dispatch({
          type: 'verify-fail',
          errors: errs,
          orchError: orchEnabled && !orchOk,
          wsError: wsEnabled && !wsOk,
        })
      }
    } catch (err) {
      dispatch({
        type: 'verify-fail',
        errors: [err instanceof Error ? err.message : 'Verification failed'],
        orchError: orchEnabled,
        wsError: wsEnabled,
      })
    }
  }, [draft, orchEnabled, wsEnabled, queryClient])

  // Track in-flight mode-only saves so rapid checkbox toggles don't fire
  // overlapping POST /agent-mode requests, and so a stale response can't
  // overwrite a newer selection.
  const modeSaveInFlightRef = useRef(false)

  const handleSaveModeOnly = useCallback(async () => {
    // Silent save — do NOT dispatch verify-start. UI stays on "Connection
    // Verified" the whole time.
    if (modeSaveInFlightRef.current) return
    const requestedMode = deriveAgentMode(orchEnabled, wsEnabled)
    if (!requestedMode) return
    modeSaveInFlightRef.current = true
    try {
      await apiSetAgentMode(requestedMode)
      void invalidateOnboardingEndpoints(queryClient)
      dispatch({
        type: 'mode-save-success',
        orchEnabled,
        wsEnabled,
      })
    } catch (err) {
      dispatch({
        type: 'mode-save-fail',
        errors: [err instanceof Error ? err.message : 'Failed to update use-models setting'],
      })
    } finally {
      modeSaveInFlightRef.current = false
    }
  }, [orchEnabled, wsEnabled, queryClient])

  // Auto-save when only the checkbox selection changed and the new selection's
  // required models are already verified in DB. No user click needed — there's
  // nothing to confirm and the API call is instant.
  useEffect(() => {
    if (submitMode === 'mode-only' && isDirty && !verifying && !loading) {
      void handleSaveModeOnly()
    }
  }, [submitMode, isDirty, verifying, loading, handleSaveModeOnly])

  const handleSubmit = handleVerify

  // ── Render ─────────────────────────────────────────────────────

  // The silent auto-save path never sets `verifying`, so the button stays on
  // "Connection Verified" the whole time and only flips to "Verifying..." when
  // a real verify-against-LLM call is in flight.
  const submitLabel = verifying
    ? 'Verifying...'
    : verified && !isDirty
      ? 'Connection Verified'
      : 'Verify & Save'

  const SubmitIcon = verifying ? Loader2 : verified && !isDirty ? CheckCircle2 : ArrowRight

  return (
    <div className="flex flex-col gap-4">
      {/* Heading */}
      <div className="flex flex-col gap-1">
        <h3 className="text-foreground text-base font-bold">Connect your AI models</h3>
        <p className="text-muted-foreground text-xs leading-relaxed">
          MagenticLite runs on two models to unlock all features.
          <br />
          <span className="text-foreground font-bold">
            You can use both models, or just one. If you only want to use one, uncheck the other.
          </span>
        </p>
      </div>

      <div className="flex gap-4">
        <div className="flex-1">
          <ModelConfigCard
            name="Orchestrator model"
            config={draft.orchestrator}
            onChange={(partial) => dispatch({ type: 'edit-orch', partial })}
            state={orchError ? 'error' : 'default'}
            disabled={frozen}
            enabled={orchEnabled}
            onEnabledChange={(enabled) => dispatch({ type: 'set-orch-enabled', enabled })}
            description="Powers reasoning, coding, and tool calling — the brain behind every task."
            recommendation={<RecommendedModel name="MagenticBrain" url={ORCHESTRATOR_DOC_URL} />}
          />
        </div>
        <div className="flex-1">
          <ModelConfigCard
            name="Browser use model"
            config={draft.webSurfer}
            onChange={(partial) => dispatch({ type: 'edit-ws', partial })}
            state={wsError ? 'error' : 'default'}
            disabled={frozen}
            enabled={wsEnabled}
            onEnabledChange={(enabled) => dispatch({ type: 'set-ws-enabled', enabled })}
            description="Required to unlock browser navigation and web tasks."
            recommendation={<RecommendedModel name="Fara 1.5" url={FARA_DOC_URL} />}
            placeholders={{
              endpointUrl: 'e.g. http://localhost:5000/v1',
              modelName: 'e.g. fara-v1',
            }}
          />
        </div>
      </div>

      {/* Error alert */}
      <VerificationAlert errors={errors} />

      {/* Button row */}
      <div className="flex items-center justify-between">
        <Button variant="secondary" className="rounded-full" asChild>
          <a href={MODEL_HOSTING_GUIDE_URL} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="size-4" />
            Model Hosting Guide
          </a>
        </Button>

        <div className="flex gap-2">
          <Button
            variant="destructive"
            className="rounded-full"
            onClick={() => dispatch({ type: 'discard' })}
            disabled={frozen || !isDirty}
          >
            <RotateCcw className="size-4" />
            Discard Changes
          </Button>
          <Button
            className="rounded-full"
            onClick={handleSubmit}
            disabled={frozen || !canSubmit || (!isDirty && verified)}
          >
            <SubmitIcon className={cn('size-4', verifying && 'animate-spin')} />
            {submitLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
