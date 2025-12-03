import { useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, LayoutGrid } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SampleTaskCards } from '@/components/common'
import { OnboardingLayout } from '@/components/onboarding'
import { useUIStore } from '@/stores'
import { DRAFT_SESSION_ID } from '@/lib/constants'
import { setInputDraft } from '@/lib/inputDrafts'
import type { SampleTask } from '@/lib/sampleTasks'
import { setPendingSampleTask } from '@/lib/sampleTasks'

/**
 * Standalone sample tasks page.
 * Shown after onboarding completes, but accessible anytime at /sample-tasks.
 * Uses OnboardingLayout for visual consistency with the onboarding flow.
 */
export function SampleTasksPage() {
  const navigate = useNavigate()
  const createDraftSession = useUIStore((s) => s.createDraftSession)
  const draftSession = useUIStore((s) => s.draftSession)

  const startNewSession = useCallback(
    (initialTask?: string) => {
      if (!draftSession) {
        createDraftSession()
      }
      if (initialTask) {
        setInputDraft(DRAFT_SESSION_ID, initialTask)
      }
      navigate(`/sessions/${DRAFT_SESSION_ID}`)
    },
    [createDraftSession, draftSession, navigate]
  )

  const navigatingRef = useRef(false)

  const handleTaskSelect = useCallback(
    (task: SampleTask) => {
      if (navigatingRef.current) return
      navigatingRef.current = true
      setPendingSampleTask(task)
      startNewSession(task.prompt)
    },
    [startNewSession]
  )

  return (
    <OnboardingLayout>
      <div className="flex flex-col gap-6">
        {/* Title */}
        <div className="flex flex-col gap-4">
          <h2 className="text-foreground text-2xl font-bold tracking-tight">Setup is complete!</h2>
          <p className="text-muted-foreground text-sm leading-relaxed">
            MagenticLite is ready — give your agent something to do.
            <br />
            <span className="text-foreground font-bold">Try a sample task:</span>
          </p>
        </div>

        {/* Sample tasks */}
        <SampleTaskCards title={null} onTaskSelect={handleTaskSelect} />

        <div className="flex items-center justify-between">
          <Button variant="secondary" className="rounded-full" onClick={() => navigate('/')}>
            <LayoutGrid className="size-4" />
            Go to Dashboard
          </Button>
          <Button className="rounded-full" onClick={() => startNewSession()}>
            <ArrowRight className="size-4" />
            Run Your Own Task
          </Button>
        </div>
      </div>
    </OnboardingLayout>
  )
}
