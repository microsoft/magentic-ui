import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOnboardingStore } from '@/stores'
import { OnboardingLayout, WelcomeStep, CustomEndpointStep } from '@/components/onboarding'

/** Onboarding page — full-screen, no Header/Sidebar shell */
export function OnboardingPage() {
  const step = useOnboardingStore((s) => s.step)
  const init = useOnboardingStore((s) => s.init)
  const navigate = useNavigate()

  // Hydrate from backend on mount. If a model config was previously saved,
  // bounce-back logic in init() jumps straight to the model-card step.
  useEffect(() => {
    void init()
  }, [init])

  // If step is 'ready' (verification passed, navigation pending), redirect
  useEffect(() => {
    if (step === 'ready') {
      navigate('/sample-tasks', { replace: true })
    }
  }, [step, navigate])

  return (
    <OnboardingLayout>
      {step === 'welcome' && <WelcomeStep />}
      {(step === 'custom_endpoint' || step === 'verifying' || step === 'verified') && (
        <CustomEndpointStep />
      )}
      {step === 'ready' && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-muted-foreground text-lg">Redirecting...</p>
        </div>
      )}
    </OnboardingLayout>
  )
}
