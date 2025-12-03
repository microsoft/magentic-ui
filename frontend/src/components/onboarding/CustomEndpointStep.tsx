import { useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ExternalLink, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useOnboardingStore } from '@/stores'
import {
  ModelConfigCard,
  RecommendedModel,
  VerificationAlert,
} from '@/components/common/ModelConfigCard'
import { FARA_DOC_URL, MODEL_HOSTING_GUIDE_URL, ORCHESTRATOR_DOC_URL } from '@/lib/constants'

export function CustomEndpointStep() {
  const navigate = useNavigate()
  const {
    step,
    orchestrator,
    webSurfer,
    orchEnabled,
    wsEnabled,
    setOrchestrator,
    setWebSurfer,
    setOrchEnabled,
    setWsEnabled,
    setStep,
    verifyWithApi,
    verifyState,
  } = useOnboardingStore()

  const isVerifying = step === 'verifying'
  const hasError = verifyState.overall === 'error'

  // Disable verify when nothing is selected or any selected side is incomplete.
  const canVerify = useMemo(() => {
    if (!orchEnabled && !wsEnabled) return false
    if (orchEnabled) {
      if (!orchestrator.endpointUrl.trim() || !orchestrator.modelName.trim()) return false
    }
    if (wsEnabled) {
      if (!webSurfer.endpointUrl.trim() || !webSurfer.modelName.trim()) return false
    }
    return true
  }, [orchEnabled, wsEnabled, orchestrator, webSurfer])

  const handleVerify = useCallback(async () => {
    await verifyWithApi()
    // If verification succeeded, navigate to sample tasks page.
    // The store sets step='ready' and calls completeOnboarding() on success.
    const { verifyState: result } = useOnboardingStore.getState()
    if (result.overall === 'success') {
      navigate('/sample-tasks')
    }
  }, [verifyWithApi, navigate])

  return (
    <div className="flex flex-col gap-6">
      {/* Title */}
      <div className="flex flex-col gap-4">
        <h2 className="text-foreground text-2xl font-bold tracking-tight">
          Connect your AI models
        </h2>
        <p className="text-muted-foreground text-sm leading-relaxed">
          MagenticLite runs on two models to unlock all features.
          <br />
          <span className="text-foreground font-bold">
            You can use both models, or just one. If you only want to use one, uncheck the other.
          </span>
        </p>
      </div>

      {/* Model cards — two columns */}
      <div className="flex gap-4">
        <div className="flex-1">
          <ModelConfigCard
            name="Orchestrator model"
            config={orchestrator}
            onChange={setOrchestrator}
            state={verifyState.orchestrator.status === 'error' ? 'error' : 'default'}
            disabled={isVerifying}
            enabled={orchEnabled}
            onEnabledChange={setOrchEnabled}
            description="Powers reasoning, coding, and tool calling — the brain behind every task."
            recommendation={<RecommendedModel name="MagenticBrain" url={ORCHESTRATOR_DOC_URL} />}
          />
        </div>
        <div className="flex-1">
          <ModelConfigCard
            name="Browser use model"
            config={webSurfer}
            onChange={setWebSurfer}
            state={verifyState.webSurfer.status === 'error' ? 'error' : 'default'}
            disabled={isVerifying}
            enabled={wsEnabled}
            onEnabledChange={setWsEnabled}
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
      {hasError && verifyState.overallError && (
        <VerificationAlert errors={verifyState.overallError.split('\n')} />
      )}

      {/* Button row */}
      <div className="flex items-center justify-between">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="secondary"
              size="icon"
              className="rounded-full"
              onClick={() => setStep('welcome')}
              disabled={isVerifying}
              aria-label="Go back"
            >
              <ArrowLeft className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Go back</TooltipContent>
        </Tooltip>

        <div className="flex gap-2">
          <Button variant="secondary" className="rounded-full" asChild>
            <a href={MODEL_HOSTING_GUIDE_URL} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-4" />
              Model Hosting Guide
            </a>
          </Button>
          <Button
            className="rounded-full"
            onClick={handleVerify}
            disabled={isVerifying || !canVerify}
          >
            {isVerifying ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowRight className="size-4" />
            )}
            {isVerifying ? 'Verifying...' : hasError ? 'Verify Again' : 'Verify Connection'}
          </Button>
        </div>
      </div>
    </div>
  )
}
